"""Scanner, rules, setup lifecycle and MARKET WATCH on SYNTHETIC FIXTURES (labelled tests; never live results).
Acceptance tests A, B, C, F, G and the watch conditions."""
import copy
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest
import yaml

from src import PROJECT_ROOT
from src.live_usdjpy import lifecycle as LC
from src.live_usdjpy import rules as RL
from src.live_usdjpy import scanner as S
from src.live_usdjpy import watch as W
from src.live_usdjpy.registry import Registry

CFG = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text())["live_usdjpy"]
NOW = datetime(2026, 11, 10, 20, 50, tzinfo=timezone.utc)                    # Tue 15:50 ET (no guard window)


def series(last_day, n=420, shock=0.0, seed=1, start=150.0):
    idx = pd.bdate_range(end=last_day, periods=n)
    r = np.random.default_rng(seed).normal(0, 0.004, n)
    r[-1] = shock
    return pd.Series(start * np.exp(np.cumsum(r)), index=idx)


def snap(price=150.0, fresh="LIVE", status="DATA OK"):
    obs = [{"specialist": s, "role": "primary", "symbol": sym, "last": price if s == "usdjpy" else 100.0,
            "source_ts_utc": NOW.isoformat(), "freshness": fresh if s == "usdjpy" else "LIVE", "age_s": 5,
            "session_open": True} for s, sym in (("usdjpy", "JPY=X"), ("gbpusd", "GBPUSD=X"), ("gold", "GLD"))]
    return {"generated_utc": NOW.isoformat(), "observations": obs, "clock": {"active_sessions": ["New York"]},
            "status": {"usdjpy": status, "gbpusd": "DATA OK", "gold": "DATA OK"}}


def inputs(fx_shock=0.0, spy_shock=0.0, price=150.0, fresh="LIVE", status="DATA OK", events=None, mof=None,
           last="2026-11-09", gld_shock=0.0):
    bars = {"JPY=X": series(last, shock=fx_shock, seed=1), "SPY": series(last, shock=spy_shock, seed=2, start=600.0),
            "GLD": series(last, shock=gld_shock, seed=3, start=370.0), "GBPUSD=X": series(last, seed=4, start=1.33)}
    return S.ScanInputs(snapshot=snap(price, fresh, status), bars=bars,
                        events_store={"events": events or {}, "mof_intervention": mof or {}, "generated_utc": NOW.isoformat()},
                        mode="demo")


@pytest.fixture
def reg(tmp_path):
    r = Registry(tmp_path / "demo.sqlite")
    yield r
    r.close()


def kinds(reg, kind):
    return [r["payload"] for r in reg.records(kind)]


def test_A_and_C_calm_data_records_no_trade_with_inputs(reg, tmp_path):
    S.run_scan(reg, NOW, inputs(), CFG, tmp_path)
    ev = [e for e in kinds(reg, "evaluation") if e["type"] == "rule_signal"]
    assert {e["rule_id"] for e in ev} == {"F001", "F002"}
    f1 = next(e for e in ev if e["rule_id"] == "F001")
    assert f1["kind"] == "NO_TRADE" and f1["inputs_sha256"] and "z_usdjpy" in f1["values"]
    assert kinds(reg, "market_state")[0]["bars"]["JPY=X"]["last_date"] == "2026-11-09"
    assert reg.verify() is None


def test_trigger_creates_one_setup_and_one_complete_alert(reg, tmp_path):
    S.run_scan(reg, NOW, inputs(fx_shock=-0.02, spy_shock=-0.05), CFG, tmp_path)
    tr = kinds(reg, "setup_transition")
    assert [(t["setup_id"], t["state"]) for t in tr] == [("F001-2026-11-09", "triggered"), ("F001-2026-11-09", "entered")]
    alerts = [n for n in kinds(reg, "notification") if n["fields"]["setup_id"] == "F001-2026-11-09"]
    assert [a["priority"] for a in alerts] == ["NORMAL", "NORMAL"]
    f = alerts[0]["fields"]
    assert set(f) == set(LC.ALERT_FIELDS)
    assert f["class"] == "EXPERIMENTAL IDEA (shadow ledger)" and "NOT VALIDATED" in f["validation_status"]
    assert f["reference_price"] == 150.0 and f["invalidation"] < 150.0
    assert f["target_or_exit"].startswith("target 15") and f["direction"] == "LONG USD/JPY"
    gate = [e for e in kinds(reg, "evaluation") if e["type"] == "gate_decision"]
    assert gate and gate[0]["status"] in ("APPROVED", "SHRUNK") and gate[0]["entry_status"].startswith("entered: order")
    fill = [f for f in kinds(reg, "fill") if f["type"] == "trade"][0]
    assert fill["price"] == pytest.approx(150.0 * 1.00015) and fill["notional_usd"] == pytest.approx(2500.0)


def test_B_and_G_reruns_and_later_scans_do_not_duplicate_or_spam(reg, tmp_path):
    inp = inputs(fx_shock=-0.02, spy_shock=-0.05)
    S.run_scan(reg, NOW, inp, CFG, tmp_path)
    n = reg.count()
    assert S.run_scan(reg, NOW, inp, CFG, tmp_path) == {"duplicate": True, "key": "scan:demo:20261110T2050Z"}
    assert reg.count() == n
    S.run_scan(reg, NOW + timedelta(minutes=30), inp, CFG, tmp_path)               # a later scan, same bar
    assert [t["state"] for t in kinds(reg, "setup_transition")] == ["triggered", "entered"]
    assert len([x for x in kinds(reg, "notification") if x["fields"]["setup_id"] == "F001-2026-11-09"]) == 2
    assert len([f for f in kinds(reg, "fill") if f["type"] == "trade"]) == 1                 # exactly one order filled


def test_G_blocked_once_then_expired_without_spam(reg, tmp_path):
    S.run_scan(reg, NOW, inputs(fx_shock=-0.02, spy_shock=-0.05, fresh="STALE"), CFG, tmp_path)
    S.run_scan(reg, NOW + timedelta(hours=1), inputs(fx_shock=-0.02, spy_shock=-0.05, fresh="STALE"), CFG, tmp_path)
    states = [t["state"] for t in kinds(reg, "setup_transition")]
    assert states == ["triggered", "blocked"]
    later = NOW + timedelta(days=2)                                              # Thu: entry window (1 FX day) passed
    S.run_scan(reg, later, inputs(fx_shock=-0.02, spy_shock=-0.05, fresh="STALE"), CFG, tmp_path)
    assert [t["state"] for t in kinds(reg, "setup_transition")] == ["triggered", "blocked", "expired"]
    notifs = [n for n in kinds(reg, "notification") if n["fields"]["setup_id"] == "F001-2026-11-09"]
    assert [n["priority"] for n in notifs] == ["NORMAL", "LOW", "LOW"]


def test_G_invalidated_before_entry(reg, tmp_path):
    S.run_scan(reg, NOW, inputs(fx_shock=-0.02, spy_shock=-0.05, fresh="STALE"), CFG, tmp_path)
    S.run_scan(reg, NOW + timedelta(hours=1), inputs(fx_shock=-0.02, spy_shock=-0.05, price=140.0), CFG, tmp_path)
    assert kinds(reg, "setup_transition")[-1]["state"] == "invalidated"


def test_excluded_trigger_on_japanese_holiday_is_no_trade(reg, tmp_path):
    jp_holiday = "2026-11-03"                                                   # Culture Day
    S.run_scan(reg, datetime(2026, 11, 4, 20, 50, tzinfo=timezone.utc), inputs(fx_shock=-0.02, spy_shock=-0.05, last=jp_holiday), CFG, tmp_path)
    f1 = next(e for e in kinds(reg, "evaluation") if e.get("rule_id") == "F001")
    assert f1["kind"] == "NO_TRADE" and "excluded by the pre-registration" in f1["reason"]
    assert kinds(reg, "setup_transition") == []


def test_F_interrupted_scan_leaves_nothing(reg, tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("simulated crash mid-scan")
    monkeypatch.setattr(W, "run", boom)
    with pytest.raises(OSError):
        S.run_scan(reg, NOW, inputs(fx_shock=-0.02, spy_shock=-0.05), CFG, tmp_path)
    assert reg.count() == 0
    monkeypatch.undo()
    S.run_scan(reg, NOW, inputs(fx_shock=-0.02, spy_shock=-0.05), CFG, tmp_path)   # restart: the same slot runs once
    assert len(kinds(reg, "scan_run")) == 1 and reg.verify() is None


def test_F002_month_end_signals_and_dead_band():
    p = CFG["rules"]["F002"]
    up = pd.Series(np.linspace(140, 150, 300), index=pd.bdate_range(end="2026-10-30", periods=300))
    s = RL.f002(RL.RuleInputs(fx=up, spy=up, live_price=150.0), p)
    assert s.kind == "CANDIDATE" and s.direction == 1 and s.setup_id == "F002-2026-10" and s.invalidation < 150
    flat = pd.Series(150 + np.sin(np.arange(300)) * 0.1, index=up.index)
    assert RL.f002(RL.RuleInputs(fx=flat, spy=flat, live_price=150.0), p).kind == "NO_TRADE"
    mid = up.loc[:"2026-10-20"]
    assert RL.f002(RL.RuleInputs(fx=mid, spy=mid, live_price=150.0), p).kind in ("NOT_DUE", "WATCHING")


def test_watch_big_move_cap_and_outage_recovery(reg, tmp_path):
    cfg = dict(CFG["market_watch"], max_per_market_per_day=1)
    bars = {"GOLD": series("2026-11-09", shock=0.05, seed=3, start=370.0)}
    W.run(reg, NOW, bars, snap(), {}, cfg)
    W.run(reg, NOW, {"GOLD": series("2026-11-10", shock=-0.06, seed=5, start=370.0)}, snap(), {}, cfg)
    gold = [w for w in kinds(reg, "market_watch") if w["market"] == "GOLD" and w["condition"] == "W001"]
    assert len(gold) == 2 and [g["alerted"] for g in gold] == [True, False]      # second one recorded, capped
    W.run(reg, NOW, {}, snap(fresh="STALE"), {}, cfg)
    W.run(reg, NOW + timedelta(minutes=5), {}, snap(), {}, cfg)
    w5 = [w["state"] for w in kinds(reg, "market_watch") if w["condition"] == "W005" and w["market"] == "USDJPY"]
    assert w5 == ["OUTAGE", "RECOVERED"]
    sysalerts = [n for n in kinds(reg, "notification") if n["fields"]["class"] == "RISK/SYSTEM ALERT"]
    assert len(sysalerts) == 2                                                   # system alerts are never capped


def test_watch_event_within_24h_and_mof_baseline_then_new_release(reg):
    ev = {"e1": {"title": "Employment Situation", "status": "SCHEDULED", "scheduled_time_utc": "2026-11-11T13:30:00+00:00",
                 "scheduled_date": "2026-11-11", "markets_affected": ["usdjpy", "gold"], "source": "BLS"}}
    mof = {"Monthly Release": {"period": "Sep", "published": "2026-09-30"}}
    W.run(reg, NOW, {}, snap(), {"events": ev, "mof_intervention": mof}, CFG["market_watch"])
    w = kinds(reg, "market_watch")
    assert sorted((x["condition"], x["market"]) for x in w if x["condition"] == "W003") == [("W003", "GOLD"), ("W003", "USDJPY")]
    assert [x.get("baseline") for x in w if x["condition"] == "W004"] == [True]    # existing release: silent baseline
    W.run(reg, NOW, {}, snap(), {"events": ev, "mof_intervention": {"Monthly Release": {"period": "Oct", "published": "2026-10-30"}}},
          CFG["market_watch"])
    new = [x for x in kinds(reg, "market_watch") if x["condition"] == "W004" and not x.get("baseline")]
    assert len(new) == 1 and new[0]["alerted"]
    W.run(reg, NOW, {}, snap(), {"events": ev, "mof_intervention": {"Monthly Release": {"period": "Oct", "published": "2026-10-30"}}},
          CFG["market_watch"])
    assert len([x for x in kinds(reg, "market_watch") if x["condition"] == "W004"]) == 2   # no duplicate


def test_watch_includes_date_only_events_like_boj(reg):
    ev = {"boj": {"title": "BoJ Monetary Policy Meeting statement (meeting Nov 10-11)", "status": "SCHEDULED",
                  "scheduled_time_utc": None, "scheduled_date": "2026-11-11", "markets_affected": ["usdjpy"], "source": "Bank of Japan"}}
    W.run(reg, NOW, {}, snap(), {"events": ev}, CFG["market_watch"])
    w3 = [x for x in kinds(reg, "market_watch") if x["condition"] == "W003"]
    assert len(w3) == 1 and w3[0]["date"] == "2026-11-11"
    n = [x for x in kinds(reg, "notification") if "BoJ" in x["title"]]
    assert n and "time not published" in n[0]["fields"]["event_time_et"]


def test_watch_alerts_mark_non_applicable_fields(reg):
    ev = {"e1": {"title": "Consumer Price Index", "status": "SCHEDULED", "scheduled_time_utc": "2026-11-11T13:30:00+00:00",
                 "scheduled_date": "2026-11-11", "markets_affected": ["usdjpy"], "source": "BLS"}}
    W.run(reg, NOW, {}, snap(), {"events": ev}, CFG["market_watch"])
    f = [n for n in kinds(reg, "notification") if "Consumer Price Index" in n["title"]][0]["fields"]
    assert f["size"].startswith("not applicable") and f["max_planned_loss"].startswith("not applicable")
    assert f["instrument"].startswith("JPY=X")
