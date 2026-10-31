"""Notification engine (acceptance tests B, K, L and retries/fallback/quiet hours/crash handling).
Fake channels only: nothing is sent anywhere. Synthetic records (tests, not live results)."""
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from src import PROJECT_ROOT
from src.live_usdjpy import gate as G
from src.live_usdjpy import lifecycle as LC
from src.live_usdjpy import notify as N
from src.live_usdjpy.registry import Registry

CFG = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text())["live_usdjpy"]["notifications"]
DAY = datetime(2026, 11, 10, 20, 0, tzinfo=timezone.utc)               # Tue 15:00 ET, outside quiet hours


class Fake:
    def __init__(self, name, results=("sent",), configured=True):
        self.name, self.results, self._cfg, self.sent = name, list(results), configured, []

    def configured(self):
        return self._cfg

    def send(self, payload, title, body):
        res = self.results.pop(0) if self.results else "sent"
        self.sent.append((title, body))
        return {"result": res, "http_status": 200 if res == "sent" else 503, "info": "fake"}


@pytest.fixture
def reg(tmp_path):
    r = Registry(tmp_path / "r.sqlite")
    yield r
    r.close()


def queue(reg, prio="NORMAL", cls="EXPERIMENTAL IDEA (shadow ledger)", key=None, now=DAY):
    return reg.append("notification", LC.alert(prio, "T %s" % prio, **{"class": cls, "setup_id": "S1"}), idem_key=key, now=now)


def test_B_one_notification_per_setup_and_delivery_recorded(reg):
    LC.transition(reg, "F001-2026-11-09", "triggered", {}, {"setup_id": "F001-2026-11-09"}, DAY)
    LC.transition(reg, "F001-2026-11-09", "triggered", {}, {"setup_id": "F001-2026-11-09"}, DAY)   # re-run
    p = Fake("pushover")
    N.dispatch(reg, DAY, [p], CFG)
    N.dispatch(reg, DAY + timedelta(minutes=5), [p], CFG)                                        # re-run dispatch
    assert len(p.sent) == 1
    nid = reg.records("notification")[0]["record_id"]
    assert N.status_of(reg, nid) == "delivered"
    assert [d["result"] for d in N.deliveries(reg, nid)] == ["attempting", "sent"]


def test_message_format_full_list_only_for_ideas_and_candidates_summary_first():
    idea = LC.alert("NORMAL", "F001-2026-11-09 TRIGGERED", **{"class": "EXPERIMENTAL IDEA (shadow ledger)", "market": "USDJPY",
                                                             "reference_price": 150.123456, "invalidation": 147.0})
    title, body = N.render(idea)
    lines = body.splitlines()
    assert lines[0].startswith("NORMAL EXPERIMENTAL IDEA | USDJPY | F001-2026-11-09 TRIGGERED") and "NOT VALIDATED" in lines[0]
    assert len(lines[0]) <= 200                                         # one line for the lock screen
    assert "reference price: 150.123" in body and "evidence against: UNKNOWN" in body   # full list; applies but unknown
    assert len(body) <= N.MAX_LEN and "Not financial advice" in body
    for cls in ("RISK/SYSTEM ALERT", "MARKET WATCH", "TEST", "PAPER POSITION UPDATE"):
        a = LC.alert("HIGH", "x", **{"class": cls, "market": "USDJPY", "event_time_et": "2026-11-10 16:45 ET",
                                     "size": "not applicable (information only)", "why_sent": "y"})
        t, b = N.render(a)
        assert "size:" not in b and "invalidation" not in b and "evidence for" not in b, cls      # omitted, not UNKNOWN
        assert "UNKNOWN" not in b and "why sent: y" in b
    sysal = LC.alert("HIGH", "data outage", **{"class": "RISK/SYSTEM ALERT", "quote_time_et": None})
    assert "quote time et: UNKNOWN" in N.render(sysal)[1]            # applies (passed) but not known -> UNKNOWN
    test = LC.alert("NORMAL", "TEST", summary="TEST | pushover channel works | no action needed", **{"class": "TEST"})
    assert N.render(test)[1].splitlines()[0] == "TEST | pushover channel works | no action needed"


def test_retry_with_backoff_then_fallback_without_duplicates(reg):
    queue(reg)
    p, f = Fake("pushover", ["failed", "failed", "failed"]), Fake("ntfy")
    N.dispatch(reg, DAY, [p, f], CFG)                                    # primary fails once: wait (no fallback yet)
    assert len(p.sent) == 1 and len(f.sent) == 0
    N.dispatch(reg, DAY + timedelta(seconds=30), [p, f], CFG)            # inside backoff: nothing sent
    assert len(p.sent) == 1 and len(f.sent) == 0
    N.dispatch(reg, DAY + timedelta(minutes=2), [p, f], CFG)             # second primary failure -> fallback now
    assert len(p.sent) == 2 and len(f.sent) == 1
    N.dispatch(reg, DAY + timedelta(minutes=30), [p, f], CFG)            # delivered: nothing more
    assert len(p.sent) == 2 and len(f.sent) == 1 and reg.verify() is None


def test_rejected_primary_goes_straight_to_fallback(reg):
    queue(reg)
    p, f = Fake("pushover", ["rejected"]), Fake("ntfy")
    N.dispatch(reg, DAY, [p, f], CFG)
    assert len(p.sent) == 1 and len(f.sent) == 1


def test_quiet_hours_hold_low_and_normal_but_never_high_or_system(reg):
    night = datetime(2026, 11, 11, 4, 0, tzinfo=timezone.utc)              # 23:00 ET
    queue(reg, "LOW", now=night)
    queue(reg, "NORMAL", now=night)
    queue(reg, "HIGH", now=night)
    queue(reg, "NORMAL", cls="RISK/SYSTEM ALERT", now=night)
    p = Fake("pushover")
    N.dispatch(reg, night, [p], CFG)
    assert sorted(b.splitlines()[0] for _, b in p.sent) == ["T HIGH", "T NORMAL"] and any(t == "SYSTEM ALERT" for t, _ in p.sent)
    N.dispatch(reg, datetime(2026, 11, 11, 12, 30, tzinfo=timezone.utc), [p], CFG)   # 07:30 ET: held ones go out
    assert len(p.sent) == 4


def test_crash_between_send_and_record_never_resends_normal_but_resends_high(reg):
    a, b = queue(reg, "NORMAL"), queue(reg, "HIGH")
    for n in (a, b):
        reg.append("delivery", {"notification_id": n["record_id"], "channel": "pushover", "attempt_id": n["record_id"] + "-1",
                                "result": "attempting", "at_utc": DAY.isoformat()})
    p = Fake("pushover")
    N.dispatch(reg, DAY + timedelta(minutes=10), [p], CFG)
    assert [b.splitlines()[0] for _, b in p.sent] == ["T HIGH"]
    assert any(d["result"] == "unknown" for d in N.deliveries(reg, a["record_id"]))


def test_unconfigured_channels_are_reported_not_faked(reg):
    queue(reg)
    out = N.dispatch(reg, DAY, [Fake("pushover", configured=False), Fake("ntfy", configured=False)], CFG)
    assert ("%s" % out).count("not configured") == 2
    assert N.status_of(reg, reg.records("notification")[0]["record_id"]) == "pending"


def test_K_kill_switch_alert_is_high_and_delivered_even_in_quiet_hours(reg, tmp_path):
    night = datetime(2026, 11, 11, 4, 0, tzinfo=timezone.utc)
    G.kill(reg, tmp_path, "drill", now=night)
    p = Fake("pushover")
    N.dispatch(reg, night, [p], CFG)
    assert len(p.sent) == 1 and p.sent[0][0] == "SYSTEM ALERT" and p.sent[0][1].startswith("KILL SWITCH ON")


def test_daily_digest_once_per_day(reg):
    eve = datetime(2026, 11, 10, 23, 5, tzinfo=timezone.utc)                # 18:05 ET
    assert N.queue_digest(reg, eve - timedelta(hours=2), CFG) is False      # before 18:00 ET: not yet
    assert N.queue_digest(reg, eve, CFG) is True
    assert N.queue_digest(reg, eve + timedelta(minutes=30), CFG) is False   # once per day
    p = Fake("pushover")
    N.dispatch(reg, eve, [p], CFG)
    assert p.sent and p.sent[0][0] == "Daily digest 2026-11-10" and "NOT A TRADING SIGNAL" in p.sent[0][1]


def test_L_missing_digest_and_scan_gap_raise_high_alerts_once(reg):
    late = datetime(2026, 11, 11, 1, 30, tzinfo=timezone.utc)               # 20:30 ET, past 18:00 + 120 min
    reg.append("scan_run", {"completed_utc": (late - timedelta(hours=40)).isoformat(), "mode": "forward"})
    a = N.check_liveness(reg, late, CFG, fx_open=True)
    assert ("scan_gap", True) in a and ("digest_missing", True) in a
    b = N.check_liveness(reg, late + timedelta(minutes=10), CFG, fx_open=True)
    assert all(new is False for _, new in b)                               # each alerts once
    highs = [r["payload"] for r in reg.records("notification") if r["payload"]["priority"] == "HIGH"]
    assert {h["title"].split(" ")[0] for h in highs} == {"NO", "DAILY"}


def test_no_scan_gap_alert_while_the_fx_market_is_closed(reg):
    sat = datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc)
    reg.append("scan_run", {"completed_utc": (sat - timedelta(hours=40)).isoformat(), "mode": "forward"})
    assert not [x for x in N.check_liveness(reg, sat, dict(CFG, digest_time_et="23:59"), fx_open=False) if x[0] == "scan_gap"]


class Resp:
    def __init__(self, code, j=None):
        self.status_code, self._j = code, j or {}

    def json(self):
        return self._j


def test_pushover_and_ntfy_adapters_map_status_codes_and_never_record_secrets(reg, monkeypatch):
    monkeypatch.setattr(N, "secret", lambda item: "SECRET-" + item)
    pcfg = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text())["live_usdjpy"]["notifications"]
    seen = []

    def post(url, data=None, headers=None, timeout=None):
        seen.append((url, data, headers))
        return Resp(codes.pop(0), {"status": 1, "receipt": "r123"})
    codes = [200]
    p = N.Pushover(pcfg["pushover"], post=post)
    q = queue(reg, "HIGH")
    N.dispatch(reg, DAY, [p], CFG)
    assert seen[0][1]["priority"] == 2 and seen[0][1]["retry"] == 300 and seen[0][1]["expire"] == 3600
    assert N.status_of(reg, q["record_id"]) == "delivered"
    codes[:] = [400]
    assert p.send({"priority": "NORMAL"}, "t", "b")["result"] == "rejected"
    codes[:] = [503]
    assert p.send({"priority": "NORMAL"}, "t", "b")["result"] == "failed"
    codes[:] = [200]
    n = N.Ntfy(pcfg["ntfy"], post=post)
    assert n.send({"priority": "LOW"}, "t", "b")["result"] == "sent" and seen[-1][2]["Priority"] == "2"
    assert seen[-1][0] == "https://ntfy.sh/SECRET-trading-research-ntfy-topic"
    dump = str([r for r in reg.records()])
    assert "SECRET-" not in dump                                     # credentials never reach any record


def test_digest_queued_late_then_delivered_does_not_raise_a_false_missing_alert(reg):
    """Regression 2026-10-29 20:07 ET: the first run queued the digest after 20:00 ET and the liveness check ran
    before dispatch, raising a false HIGH 'DAILY DIGEST MISSING'. Correct order: queue, deliver, then check."""
    late = datetime(2026, 10, 30, 0, 7, tzinfo=timezone.utc)                # Thu 20:07 ET, after 18:00 + 120 min
    reg.append("scan_run", {"completed_utc": late.isoformat(), "mode": "forward"})
    assert N.queue_digest(reg, late, CFG) is True
    N.dispatch(reg, late, [Fake("pushover")], CFG)
    assert N.check_liveness(reg, late, CFG, fx_open=True) == []
    assert not [r for r in reg.records("notification") if r["payload"]["priority"] == "HIGH"]


def test_digest_says_plainly_when_no_readiness_check_has_run(reg):
    """Owner request 2026-10-30: 'System: UNKNOWN (no preflight recorded)' replaced by plain wording."""
    reg.append("scan_run", {"completed_utc": DAY.isoformat(), "mode": "forward"}, now=DAY)
    t = DAY.replace(hour=23)                                                # 18:00 ET
    N.queue_digest(reg, t, CFG)
    body = reg.records("notification")[-1]["payload"]["body"]
    assert body.startswith("System: running; readiness not checked yet") and "UNKNOWN" not in body.splitlines()[0]
