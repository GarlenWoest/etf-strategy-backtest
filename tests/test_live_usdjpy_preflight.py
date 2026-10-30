"""Preflight / readiness (Phase D, 2026-10-30): READY / DEGRADED / BLOCKED with exact reasons and fail-closed
capabilities. Synthetic snapshots, bars and registries only."""
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
import yaml

from src import PROJECT_ROOT
from src.live_usdjpy import preflight as PF
from src.live_usdjpy.registry import Registry

CFG = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text())["live_usdjpy"]["preflight"]
NOW = datetime(2026, 11, 4, 15, 2, tzinfo=timezone.utc)          # Wed 10:02 ET: FX and NYSE open


def snap(fr="LIVE", problems=(), offset=0.1, gold="DATA OK", clock_note=None):
    return {"observations": [
        {"specialist": "usdjpy", "role": "primary", "freshness": fr, "quote_problems": list(problems), "age_s": 0.4,
         "spread_pips": 1.5, "server_clock_offset_s": offset, "clock_note": clock_note, "session_open": True},
        {"specialist": "gbpusd", "role": "primary", "freshness": "LIVE", "quote_problems": [], "session_open": True},
        {"specialist": "gold", "role": "primary", "freshness": "LIVE", "quote_problems": [], "session_open": True}],
        "status": {"usdjpy": "DATA OK", "gbpusd": "DATA OK", "gold": gold}}


def bars(last_fx="2026-11-03", last_spy="2026-11-03"):
    return {"USD_JPY": pd.Series([150.0], index=[pd.Timestamp(last_fx)]),
            "SPY": pd.Series([600.0], index=[pd.Timestamp(last_spy)])}


EVENTS = {"generated_utc": (NOW - timedelta(hours=1)).isoformat(), "events": {}}


@pytest.fixture
def reg(tmp_path):
    r = Registry(tmp_path / "r.sqlite")
    yield r
    r.close()


def run(reg, **kw):
    args = dict(now=NOW, registry=reg, snapshot=snap(), bars=bars(), events_store=EVENTS, state={}, cfg=CFG)
    args.update(kw)
    return PF.check(**args)


def by(pf, name):
    return [c for c in pf["checks"] if c["check"] == name][0]


def test_ready_when_everything_is_present(reg):
    pf = run(reg)
    assert pf["verdict"] == "READY" and pf["blocks"] == []
    assert PF.summary(pf) == "READY"


def test_failed_fetch_blocks_evaluation_entries_and_position_monitoring(reg):
    pf = run(reg, snapshot=None, bars=None, fetch_error="OANDA returned HTTP 503")
    assert pf["verdict"] == "BLOCKED" and pf["blocks"] == ["paper_entries", "position_monitoring", "rule_evaluation"]
    assert "HTTP 503" in PF.summary(pf)


def test_stale_or_invalid_usdjpy_price_blocks_entries_and_exits_but_not_evaluation(reg):
    for s_ in (snap(fr="STALE"), snap(problems=["crossed quote (bid > ask)"])):
        pf = run(reg, snapshot=s_)
        assert pf["verdict"] == "BLOCKED" and pf["blocks"] == ["paper_entries", "position_monitoring"]


def test_market_closed_is_information_not_a_fault(reg):
    sat = datetime(2026, 11, 7, 15, 2, tzinfo=timezone.utc)
    pf = run(reg, now=sat, snapshot=snap(fr="CLOSED_LAST_PRICE"), bars=bars("2026-11-06", "2026-11-06"),
             events_store={"generated_utc": sat.isoformat(), "events": {}})
    assert by(pf, "USD/JPY quote")["status"] == "INFO" and pf["verdict"] == "READY"


def test_missing_spy_bar_on_an_nyse_trading_day_defers_rule_evaluation(reg):
    pf = run(reg, bars=bars(last_spy="2026-11-02"))
    c = by(pf, "SPY daily bars")
    assert c["status"] == "BLOCKED" and "rule_evaluation" in pf["blocks"] and "data gap" in c["detail"]


def test_no_spy_requirement_on_an_nyse_holiday(reg):
    thanks = datetime(2026, 11, 27, 15, 2, tzinfo=timezone.utc)      # Fri after Thanksgiving; bar of Thu 11-26
    pf = run(reg, now=thanks, bars=bars("2026-11-26", "2026-11-25"),
             events_store={"generated_utc": thanks.isoformat(), "events": {}})
    assert [c for c in pf["checks"] if c["check"] == "SPY daily bars"] == []


def test_waiting_for_the_daily_bar_is_degraded_then_blocked(reg):
    after_bar = datetime(2026, 11, 4, 22, 2, tzinfo=timezone.utc)    # Wed 17:02 ET: Wednesday's bar just completed
    ev = {"generated_utc": after_bar.isoformat(), "events": {}}
    assert by(run(reg, now=after_bar, events_store=ev), "USD/JPY daily bars")["status"] == "DEGRADED"
    late = after_bar + timedelta(hours=7)
    pf = run(reg, now=late, events_store={"generated_utc": late.isoformat(), "events": {}})
    assert by(pf, "USD/JPY daily bars")["status"] == "BLOCKED" and "rule_evaluation" in pf["blocks"]


def test_stale_event_store_blocks_entries_only(reg):
    pf = run(reg, events_store={"generated_utc": (NOW - timedelta(hours=30)).isoformat(), "events": {}})
    assert pf["blocks"] == ["paper_entries"] and "blackout" in by(pf, "event monitor")["detail"]


def test_kill_switch_and_halted_state_block_entries(reg):
    assert run(reg, kill_on=True)["blocks"] == ["paper_entries"]
    reg.append("risk_state", {"state": "HALTED", "why": ["drawdown -3%"]}, now=NOW)
    pf = run(reg)
    assert by(pf, "risk engine")["status"] == "BLOCKED" and "drawdown" in by(pf, "risk engine")["detail"]


def test_degraded_items_do_not_block_anything(reg):
    pf = run(reg, snapshot=snap(gold="STALE MARKET DATA", offset=8.0), state={"last_error": "ReadTimeout: x"},
             backup_problems=[("stale", "newest verified registry snapshot is 40 h old")])
    assert pf["verdict"] == "DEGRADED" and pf["blocks"] == []
    names = {c["check"] for c in pf["checks"] if c["status"] == "DEGRADED"}
    assert names == {"Gold (GLD) data", "clock", "previous run", "backup"}


def test_unaccepted_high_alert_degrades_notification_status_but_quiet_hours_holds_do_not(reg):
    reg.append("notification", {"status": "queued", "priority": "LOW", "title": "x"}, now=NOW.replace(hour=3))   # 22:00 ET hold
    assert by(run(reg, now=NOW.replace(hour=11, minute=10)), "notifications")["status"] == "OK"   # 06:10 ET: still quiet
    reg.append("notification", {"status": "queued", "priority": "HIGH", "title": "y"}, now=NOW - timedelta(hours=1))
    assert by(run(reg), "notifications")["status"] == "DEGRADED"
