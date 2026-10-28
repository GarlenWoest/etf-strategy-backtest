"""Heartbeat: start/finish records, the Sunday status line (trading days, missed, late, errors), the 3-day gap alert."""
import importlib.util
from datetime import datetime

import pytest

from src import PROJECT_ROOT

spec = importlib.util.spec_from_file_location("hb", PROJECT_ROOT / "tools" / "heartbeat.py")
HB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(HB)
F = PROJECT_ROOT / "tmp" / "test_heartbeat.json"


def at(s):
    return datetime.fromisoformat(s).replace(tzinfo=HB.ET)


@pytest.fixture(autouse=True)
def clean():
    F.unlink(missing_ok=True)
    yield
    F.unlink(missing_ok=True)


def run(when, status="ok", note="", kind="weekday"):
    rid = HB.start(F, kind, at(when))
    HB.finish(F, rid, status, note, at(when))
    return rid


def test_status_counts_trading_days_missed_late_and_errors():
    # week of Mon 2026-11-23: Thanksgiving Thu 11-26 is closed -> 4 trading days
    run("2026-11-23T16:50")
    run("2026-11-24T19:30")                       # late (after 18:00)
    run("2026-11-25T16:50", status="error", note="yfinance timeout")
    run("2026-11-28T10:00")                       # Saturday catch-up covers the missed Wednesday and Friday
    line = HB.week_status(F, at("2026-11-29T18:05"))
    assert "weekday runs this week 2 of 4 trading days" in line
    assert "late: Tue (ran 19:30 ET)" in line
    assert "Wed (caught up Sat 11-28)" in line and "Fri (caught up Sat 11-28)" in line
    assert "yfinance timeout" in line
    assert "last successful weekday run Sat 11-28 10:00 ET" in line


def test_full_week_is_clean():
    for d in ("02", "03", "04", "05", "06"):
        run("2026-11-%sT16:50" % d)
    line = HB.week_status(F, at("2026-11-08T18:00"))
    assert "5 of 5 trading days; missed: none; late: none; errors: none" in line


def test_gap_alert_fires_once_then_resets():
    run("2026-11-02T16:50")                       # Monday
    HB.start(F, "weekday", at("2026-11-05T16:50"))
    assert HB.check_gap(F, at("2026-11-05T16:50")) is None          # 3 trading days: not more than 3
    F.unlink()
    run("2026-11-02T16:50")
    rid = HB.start(F, "weekday", at("2026-11-06T16:50"))            # Friday: 4 trading days
    msg = HB.check_gap(F, at("2026-11-06T16:50"))
    assert msg and msg.startswith("NOTIFY: [HEARTBEAT]")
    assert HB.check_gap(F, at("2026-11-06T17:00")) is None          # same gap again: no second notification
    HB.finish(F, rid, "ok", "", at("2026-11-06T16:55"))
    HB.start(F, "weekday", at("2026-11-09T16:50"))
    assert HB.check_gap(F, at("2026-11-09T16:50")) is None          # 1 day after the last ok run: back to normal
    assert HB.load(F)["gap_alerted"] is False


def test_unfinished_run_counts_as_error():
    HB.start(F, "weekday", at("2026-11-03T16:50"))                  # crashed, never finished
    run("2026-11-04T16:50")
    line = HB.week_status(F, at("2026-11-08T18:00"))
    assert "did not finish" in line
    assert "Tue (caught up Wed 11-04)" in line                      # an unfinished run does not count as a run


def test_days_before_monitoring_start_are_not_missed():
    # week of Mon 2026-10-19; monitoring starts Fri 2026-10-23, the first scheduled weekday run
    run("2026-10-23T16:55")
    line = HB.week_status(F, at("2026-10-25T18:35"))
    assert "1 of 1 trading days (monitoring started 2026-10-23" in line
    assert "missed: none" in line


def test_full_weeks_after_start_unchanged():
    for d in ("02", "03", "04", "05", "06"):
        run("2026-11-%sT16:50" % d)
    assert "5 of 5 trading days; missed: none" in HB.week_status(F, at("2026-11-08T18:00"))


def test_run_states_completed_partial_failed():
    a = HB.start(F, "weekday", at("2026-11-02T16:50"))
    for s in ("watchlist", "paper", "snapshot", "events"):
        HB.step(F, a, s, "ok", "", at("2026-11-02T16:51"))
    HB.finish(F, a, "ok", "", at("2026-11-02T16:52"))
    b = HB.start(F, "weekday", at("2026-11-03T16:50"))
    HB.step(F, b, "watchlist", "ok", "", at("2026-11-03T16:51"))
    HB.step(F, b, "events", "error", "HTTP 503", at("2026-11-03T16:52"))
    HB.finish(F, b, "ok", "", at("2026-11-03T16:53"))
    c = HB.start(F, "weekday", at("2026-11-04T16:50"))
    HB.step(F, c, "watchlist", "error", "timeout", at("2026-11-04T16:51"))
    HB.finish(F, c, "error", "watchlist failed", at("2026-11-04T16:52"))
    states = {r["id"]: (r["state"], r["status"]) for r in HB.load(F)["runs"]}
    assert states[a] == ("completed", "ok") and states[b] == ("partial", "ok") and states[c] == ("failed", "error")
    line = HB.week_status(F, at("2026-11-08T18:00"))
    assert "partial: weekday 2026-11-03 (failed steps: events)" in line
    assert "Wed (caught up" not in line and "missed: Wed" in line           # a failed run is not a run
    assert "watchlist failed" in line


def test_undelivered_notification_raises_alert():
    rid = HB.start(F, "weekday", at("2026-11-02T16:50"))
    HB.notify(F, rid, "[PAPER, FICTIONAL MONEY] Book B trades", "no", "terminal is active", at("2026-11-02T16:51"))
    HB.notify(F, rid, "[WATCHLIST, NOT VALIDATED] signal", "yes", "", at("2026-11-02T16:51"))
    HB.finish(F, rid, "ok", "", at("2026-11-02T16:52"))
    line = HB.week_status(F, at("2026-11-08T18:00"))
    assert "notifications: 2 recorded, 1 not confirmed delivered" in line
    assert "ALERT: notifications NOT DELIVERED: 2026-11-02 16:51 [PAPER, FICTIONAL MONEY] Book B trades (no: terminal is active)" in line
    clean_week = HB.week_status(F, at("2026-11-15T18:00"))
    assert "ALERT" not in clean_week                                          # only the week's notifications count


def test_step_and_notify_validation():
    rid = HB.start(F, "weekday", at("2026-11-02T16:50"))
    with pytest.raises(ValueError):
        HB.step(F, rid, "orders", "ok", "", at("2026-11-02T16:51"))
    with pytest.raises(ValueError):
        HB.notify(F, rid, "x", "maybe", "", at("2026-11-02T16:51"))
    with pytest.raises(ValueError):
        HB.step(F, "weekday-19990101T000000", "paper", "ok", "", at("2026-11-02T16:51"))


def test_next_scheduled_and_runs_table_and_legacy_records():
    assert HB.next_scheduled(at("2026-10-30T17:00")) == at("2026-11-02T16:45")   # Fri after the run -> Monday
    assert HB.next_scheduled(at("2026-10-28T09:00")) == at("2026-10-28T16:45")
    import json
    F.parent.mkdir(parents=True, exist_ok=True)
    F.write_text(json.dumps({"runs": [{"id": "weekday-20261023T165513", "kind": "weekday", "started": "2026-10-23T16:55:13-04:00",
                                       "finished": "2026-10-23T17:01:45-04:00", "status": "ok", "note": ""}], "gap_alerted": False}))
    assert "1 of 1 trading days" in HB.week_status(F, at("2026-10-25T18:35"))       # pre-Phase-H record still works
    assert "state ok" in HB.runs_table(F)
