"""Phase D wiring and Phase E presentation (2026-10-30): short phone text, copy-ready versioned tickets, notification
policy (phone vs digest, dedup, daily cap, expiry, HIGH never suppressed), preflight blocks in the scanner and the
persistence-based preflight alerts. SYNTHETIC fixtures only (tests, never live results)."""
from datetime import datetime, timedelta, timezone

import pytest

from src.live_usdjpy import alerts as AL
from src.live_usdjpy import lifecycle as LC
from src.live_usdjpy import notify as N
from src.live_usdjpy import preflight as PF
from src.live_usdjpy import scanner as S
from src.live_usdjpy.registry import Registry

from test_live_usdjpy_scanner import CFG, NOW, inputs, kinds
from test_live_usdjpy_notify import CFG as NCFG, Fake

POLICY = dict(NCFG, policy={"max_phone_alerts_per_day": 3, "dedup_hours": 6, "expire_unsent_hours": 12})


@pytest.fixture
def reg(tmp_path):
    r = Registry(tmp_path / "r.sqlite")
    yield r
    r.close()


def test_trigger_produces_a_short_phone_alert_pointing_to_a_full_versioned_ticket(reg, tmp_path):
    S.run_scan(reg, NOW, inputs(fx_shock=-0.02, spy_shock=-0.05), CFG, tmp_path)       # triggers and enters (shadow)
    tk = kinds(reg, "ticket")
    assert [(t["setup_id"], t["version"]) for t in tk] == [("F001-2026-11-09", 1)]
    text = tk[0]["text"]
    for f in AL.TICKET_FIELDS:
        assert "\n%s: " % f in text
    assert "NOT an executable price" in text and "not a stop order" in text and "No real-money trading is authorized" in text
    assert "EXPERIMENTAL" in text and "WATCH ONLY" in text
    p = Fake("pushover")
    N.dispatch(reg, NOW, [p], POLICY)
    title, body = p.sent[0]
    assert title == "USD/JPY | EXPERIMENTAL SETUP"
    lines = body.splitlines()
    assert lines[0] == "DETECTED LATE: F001-2026-11-09 TRIGGERED" and "Direction: LONG USD/JPY" in lines
    assert "WATCH ONLY. NOT VALIDATED. No real-money trade." in lines
    assert lines[-1] == "Ticket: F001-2026-11-09 v1 in STATUS.md" and len(lines) <= 7 and len(body) < 600
    assert "evidence" not in body.lower()                                              # no field dump on the phone


def test_ticket_versions_only_on_change_and_history_is_kept(reg, tmp_path):
    S.run_scan(reg, NOW, inputs(fx_shock=-0.02, spy_shock=-0.05), CFG, tmp_path)
    S.run_scan(reg, NOW + timedelta(minutes=15), inputs(fx_shock=-0.02, spy_shock=-0.05), CFG, tmp_path)   # nothing new
    assert len(kinds(reg, "ticket")) == 1
    later = NOW + timedelta(days=1)
    S.run_scan(reg, later, inputs(price=140.0, last="2026-11-10"), CFG, tmp_path)       # below invalidation -> exit
    tk = kinds(reg, "ticket")
    assert [t["version"] for t in tk] == [1, 2] and tk[0]["text"] != tk[1]["text"]
    assert "exit fill" in tk[1]["fields"]["CURRENT STATUS"]


def note(reg, title, cls="MARKET WATCH", trigger="W003 v1.0", market="USDJPY", prio="LOW", at=NOW):
    return reg.append("notification", LC.alert(prio, title, **{"class": cls, "trigger": trigger, "market": market,
                                                              "event_time_et": "x"}), now=at)


def test_policy_routes_low_value_items_to_the_digest_and_records_why(reg):
    note(reg, "event within 24 h")                                                     # W003 -> digest
    note(reg, "gold big move", trigger="W001 v1.0", market="GOLD")                    # gold W001 -> digest
    note(reg, "MoF release", trigger="W004 v1.0", prio="NORMAL")                       # -> phone
    p = Fake("pushover")
    out = N.dispatch(reg, NOW, [p], POLICY)
    assert [b.splitlines()[0] for _, b in p.sent] == ["MoF release"]
    st = [N.provider_status(reg, r["record_id"]) for r in reg.records("notification")]
    assert st == ["LOGGED FOR DIGEST", "LOGGED FOR DIGEST", "ACCEPTED BY PROVIDER"]
    assert sum("routed_to_digest" in o for _, o in out) == 2


def test_dedup_cap_and_expiry_but_high_is_never_suppressed(reg):
    for i in range(5):
        note(reg, "USDJPY big move %d" % i, trigger="W001 v1.0", prio="NORMAL")
    note(reg, "USDJPY big move 0", trigger="W001 v1.0", prio="NORMAL")                 # repeat of an earlier title
    note(reg, "old one", trigger="W004 v1.0", prio="NORMAL", at=NOW - timedelta(hours=13))
    for i in range(4):
        reg.append("notification", LC.alert("HIGH", "SYSTEM %d" % i, **{"class": "RISK/SYSTEM ALERT"}), now=NOW)
    p = Fake("pushover")
    N.dispatch(reg, NOW, [p], POLICY)
    firsts = [b.splitlines()[0] for _, b in p.sent]
    assert firsts[:3] == ["USDJPY big move 0", "USDJPY big move 1", "USDJPY big move 2"]      # cap of 3 non-HIGH
    assert sorted(f for f in firsts if f.startswith("SYSTEM")) == ["SYSTEM 0", "SYSTEM 1", "SYSTEM 2", "SYSTEM 3"]
    infos = [d["payload"]["info"] for d in reg.records("delivery") if d["payload"]["channel"] == "policy"]
    assert any("daily cap" in i for i in infos) and any("already sent" in i for i in infos) and any("never pushed stale" in i for i in infos)


def test_stale_price_blocks_entries_and_exits_and_defers_nothing_else(reg, tmp_path):
    S.run_scan(reg, NOW, inputs(fx_shock=-0.02, spy_shock=-0.05), CFG, tmp_path)       # entered
    later = NOW + timedelta(days=1)
    inp = inputs(price=140.0, last="2026-11-10")                                       # would exit at a "stale" price
    inp.blocks = ("paper_entries", "position_monitoring")
    inp.block_reasons = {"position_monitoring": ["USD/JPY quote: STALE"], "paper_entries": ["USD/JPY quote: STALE"]}
    out = S.run_scan(reg, later, inp, CFG, tmp_path)
    assert "BLOCKED" in out["position_monitoring"]
    assert [t["state"] for t in kinds(reg, "setup_transition")] == ["triggered", "entered"]      # no exit
    assert any(n["title"].startswith("PAPER POSITION UNMONITORED") and n["priority"] == "HIGH" for n in kinds(reg, "notification"))


def test_rule_evaluation_block_defers_instead_of_recording_no_trade(reg, tmp_path):
    inp = inputs()
    inp.blocks = ("rule_evaluation",)
    inp.block_reasons = {"rule_evaluation": ["SPY daily bars: no SPY bar"]}
    out = S.run_scan(reg, NOW, inp, CFG, tmp_path)
    assert out["deferred_evaluation"]["pairs"] and not [e for e in kinds(reg, "evaluation") if e["type"] == "rule_signal"]
    S.run_scan(reg, NOW + timedelta(minutes=10), inputs(), CFG, tmp_path)               # data back: evaluated then
    assert {e["rule_id"] for e in kinds(reg, "evaluation") if e["type"] == "rule_signal"} == {"F001", "F002"}


def test_preflight_alerts_only_when_a_problem_persists_and_announces_recovery(reg):
    cfg = {"alert_after_consecutive": 2}
    bad = {"verdict": "BLOCKED", "blocks": ["paper_entries"], "at_utc": NOW.isoformat(),
           "checks": [{"check": "event monitor", "status": "BLOCKED", "detail": "event store 30 h old", "blocks": ["paper_entries"]}]}
    ok = {"verdict": "READY", "blocks": [], "at_utc": NOW.isoformat(), "checks": [{"check": "event monitor", "status": "OK", "detail": "", "blocks": []}]}
    assert PF.record(reg, NOW, bad, cfg, "s1") is None                                 # first time: no alert
    assert PF.record(reg, NOW + timedelta(hours=1), bad, cfg, "s2").startswith("MONITORING BLOCKED")
    assert PF.record(reg, NOW + timedelta(hours=2), bad, cfg, "s3") is None             # same day: once
    assert PF.record(reg, NOW + timedelta(hours=3), ok, cfg, "s4").startswith("MONITORING RECOVERED")
    pr = [n["priority"] for n in kinds(reg, "notification")]
    assert pr == ["HIGH", "NORMAL"]
