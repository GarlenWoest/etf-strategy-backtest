"""Paper order manager, internal simulator and reconciliation (acceptance E and F). SYNTHETIC values only; every
expected number is computed by hand in the test, not by the module."""
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from src import PROJECT_ROOT
from src.live_usdjpy import lifecycle as LC
from src.live_usdjpy import paper as PP
from src.live_usdjpy.registry import Registry

CFG = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text())["live_usdjpy"]
C = CFG["costs"]["base"]["one_way"]                     # 0.00015
FEE = CFG["costs"]["base"]["financing_admin_fee_annual"]  # 0.01
MON = datetime(2026, 11, 9, 21, 0, tzinfo=timezone.utc)   # Mon 16:00 ET
SIG = {"direction": 1, "invalidation": 147.0, "target": 151.5, "bar_date": "2026-11-06", "version": "0.2"}
RATES = {"usd": (0.04, "test"), "jpy": (0.005, "test")}


@pytest.fixture
def reg(tmp_path):
    r = Registry(tmp_path / "r.sqlite")
    yield r
    r.close()


def enter(reg, size_x=0.25, S=150.0, now=MON, rule="F001", setup="F001-2026-11-06", sig=SIG):
    if LC.current(reg, setup) is None:
        LC.transition(reg, setup, "triggered", {"bar_date": sig["bar_date"]}, None, now)
    return PP.enter(reg, CFG, rule, setup, sig, size_x, S, now, "slot1", {"setup_id": setup})


def test_E_entry_fill_and_balances_match_hand_arithmetic(reg):
    oid = enter(reg)
    st = PP.state(reg, "F001", CFG)
    N = 0.25 * 10000.0
    assert st["usd_pos"] == pytest.approx(N) and st["jpy"] == pytest.approx(-N * 150.0 * (1 + C))
    assert PP.equity(st, 150.0) == pytest.approx(10000.0 - N * C)          # only the entry cost is lost at the same mark
    states = [r["payload"]["state"] for r in reg.records("order_event")]
    assert states == ["CREATED", "RELEASED", "SUBMITTED", "FILLED"] and len(oid) == 16
    assert enter(reg) is None                                                # same setup: never a second order
    assert len([r for r in reg.records("fill") if r["payload"]["type"] == "trade"]) == 1


def test_exit_at_target_pnl_matches_hand_arithmetic(reg):
    enter(reg)
    t = MON + timedelta(minutes=30)                                           # 16:30 ET, before the 17:00 roll: no financing
    PP.manage(reg, CFG, t, 151.6, RATES, "slot2")
    N, S1, S2 = 2500.0, 150.0, 151.6
    jpy = -N * S1 * (1 + C) + N * S2 * (1 - C)
    expected = 10000.0 + jpy / S2
    st = PP.state(reg, "F001", CFG)
    assert st["position"] is None and st["cash"] == pytest.approx(expected)
    out = [r["payload"] for r in reg.records("outcome")][0]
    assert out["exit_reason"].startswith("target reached")
    assert [r["payload"]["state"] for r in reg.records("setup_transition")] == ["triggered", "entered", "exited"]


def test_financing_over_a_wednesday_triple_roll(reg):
    enter(reg, now=datetime(2026, 11, 11, 20, 0, tzinfo=timezone.utc))      # Wed 15:00 ET
    PP.manage(reg, CFG, datetime(2026, 11, 11, 23, 0, tzinfo=timezone.utc), 150.0, RATES, "s2")   # Wed 18:00 ET: one roll
    acc = [r["payload"] for r in reg.records("fill") if r["payload"]["type"] == "financing"]
    assert len(acc) == 1 and acc[0]["days"] == 3
    N, jpy0 = 2500.0, -2500.0 * 150.0 * (1 + C)
    assert acc[0]["usd_interest"] == pytest.approx(N * 0.04 * 3 / 360)
    assert acc[0]["jpy_interest"] == pytest.approx(jpy0 * 0.005 * 3 / 365)
    assert acc[0]["admin_fee_usd"] == pytest.approx(N * FEE * 3 / 365)
    assert acc[0]["label"] == "estimated, unverified"
    PP.manage(reg, CFG, datetime(2026, 11, 11, 23, 30, tzinfo=timezone.utc), 150.0, RATES, "s3")  # no new roll
    assert len([r for r in reg.records("fill") if r["payload"]["type"] == "financing"]) == 1


def test_unknown_rates_accrue_only_the_fee_and_say_unknown(reg):
    enter(reg, now=datetime(2026, 11, 10, 20, 0, tzinfo=timezone.utc))
    PP.manage(reg, CFG, datetime(2026, 11, 10, 23, 0, tzinfo=timezone.utc), 150.0, {}, "s2")
    a = [r["payload"] for r in reg.records("fill") if r["payload"]["type"] == "financing"][0]
    assert a["usd_interest"] == 0 and a["jpy_interest"] == 0 and a["r_usd_info"] == "UNKNOWN" and a["admin_fee_usd"] > 0


def test_invalidation_and_expiry_exits_are_scan_based(reg):
    enter(reg)
    PP.manage(reg, CFG, MON + timedelta(hours=2), 146.5, RATES, "s2")          # beyond invalidation at a scan
    out = [r["payload"] for r in reg.records("outcome")][0]
    assert "invalidation" in out["exit_reason"] and out["exit_mid"] == 146.5   # filled at the scan price, not the level
    enter(reg, setup="F001-2026-11-09", sig=dict(SIG, bar_date="2026-11-09"), now=MON + timedelta(hours=3))
    PP.manage(reg, CFG, MON + timedelta(days=1), 150.2, RATES, "s3")           # 1 FX day: still open
    assert PP.state(reg, "F001", CFG)["position"] is not None
    PP.manage(reg, CFG, MON + timedelta(days=2), 150.2, RATES, "s4")           # 2 FX days: expiry
    assert "expiry" in [r["payload"] for r in reg.records("outcome")][-1]["exit_reason"]


def test_close_all_at_minus_5_percent_stops_the_experiment(reg):
    enter(reg, size_x=0.5, sig=dict(SIG, invalidation=100.0))                 # far invalidation so only the drawdown acts
    PP.manage(reg, CFG, MON + timedelta(hours=1), 134.0, RATES, "s2")         # about -5.3% of equity
    st = PP.state(reg, "F001", CFG)
    assert st["position"] is None and st["experiment_stopped"]
    assert any(r["payload"]["priority"] == "HIGH" and "STOPPED" in r["payload"]["title"] for r in reg.records("notification"))
    assert enter(reg, setup="F001-2026-11-20") is None                        # no new entries after the stop


def test_F_interruption_inside_an_entry_leaves_no_order_and_restart_makes_exactly_one(reg, monkeypatch):
    real = PP._fill

    def boom(*a, **k):
        raise OSError("simulated crash between SUBMITTED and FILLED")
    monkeypatch.setattr(PP, "_fill", boom)
    with pytest.raises(OSError):
        with reg.transaction():
            enter(reg)
    assert reg.records("order_event") == [] and reg.records("fill") == []
    monkeypatch.setattr(PP, "_fill", real)
    with reg.transaction():
        enter(reg)
    assert [r["payload"]["state"] for r in reg.records("order_event")] == ["CREATED", "RELEASED", "SUBMITTED", "FILLED"]


def test_reconciliation_exact_and_v2_parity_pass_on_a_multi_day_path(reg):
    t = datetime(2026, 11, 9, 20, 30, tzinfo=timezone.utc)
    enter(reg, now=t, sig=dict(SIG, target=None, invalidation=140.0), rule="F002", setup="F002-2026-10")
    for k, S in enumerate([150.4, 150.9, 151.3, 150.8, 151.6]):
        t = t + timedelta(days=1 if (t + timedelta(days=1)).weekday() < 5 else 3)
        PP.manage(reg, CFG, t, S, RATES, "m%d" % k)
    ok, rep = PP.reconcile(reg, CFG, t, 151.6)
    r = rep["F002"]
    assert r["exact_ok"] and r["exact_max_diff"] < 1e-6
    assert r["v2_pnl"] is not None and r["parity_ok"], r
    assert ok


def test_reconciliation_detects_a_tampered_snapshot_and_halts(reg):
    enter(reg)
    st = PP.state(reg, "F001", CFG)
    st["cash"] += 5.0                                                          # a ledger that no longer matches its fills
    PP.snapshot(reg, st, MON + timedelta(minutes=1), "tampered (test)")
    ok, rep = PP.reconcile(reg, CFG, MON + timedelta(minutes=2), 150.0)
    assert not ok and not rep["F001"]["exact_ok"]
    assert reg.records("risk_state")[-1]["payload"]["state"] == "HALTED"
    assert any("RECONCILIATION MISMATCH" in r["payload"]["title"] for r in reg.records("notification"))
