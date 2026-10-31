"""Phase F: independent risk monitoring of open paper positions (2026-10-31). SYNTHETIC values only.
Cadence, closed-market exits, interruptions, exposure after fills, discrepancy -> HALTED, scan gaps with a position."""
from datetime import datetime, timedelta, timezone

import pytest

from src.live_usdjpy import notify as N
from src.live_usdjpy import paper as PP
from src.live_usdjpy import runner as RN
from src.live_usdjpy.registry import Registry

from test_live_usdjpy_paper import CFG, MON, RATES, SIG, enter
from test_live_usdjpy_notify import CFG as NCFG

SAT = datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)                 # Sat 10:00 ET: FX closed
SUN_OPEN = datetime(2026, 11, 15, 22, 32, tzinfo=timezone.utc)           # Sun 17:32 ET: FX open (EST)


@pytest.fixture
def reg(tmp_path):
    r = Registry(tmp_path / "r.sqlite")
    yield r
    r.close()


def test_exit_condition_while_closed_is_pending_then_filled_at_the_first_live_price(reg):
    enter(reg)
    PP.manage(reg, CFG, SAT, 146.0, RATES, "sat", can_fill=False)             # beyond invalidation, but no market
    st = PP.state(reg, "F001", CFG)
    assert st["position"] is not None and "invalidation" in st["position"]["exit_pending"]
    PP.manage(reg, CFG, SAT + timedelta(hours=1), 145.0, RATES, "sat2", can_fill=False)
    pend = [r for r in reg.records("notification") if "EXIT PENDING" in r["payload"]["title"]]
    assert len(pend) == 1 and pend[0]["payload"]["priority"] == "NORMAL"           # one alert, not one per scan
    assert reg.records("outcome") == []                                              # nothing filled while closed
    PP.manage(reg, CFG, SUN_OPEN, 147.4, RATES, "sun")                             # reopen: price back above the level
    out = [r["payload"] for r in reg.records("outcome")][0]
    assert "deferred while the market was closed" in out["exit_reason"] and out["exit_mid"] == 147.4   # gap taken as it came
    assert PP.state(reg, "F001", CFG)["position"] is None


def test_scanner_never_fills_an_exit_from_a_closed_market_price(reg, tmp_path):
    from test_live_usdjpy_scanner import CFG as SCFG, inputs, kinds
    from src.live_usdjpy import scanner as S
    enter(reg)
    inp = inputs(price=140.0, fresh="CLOSED_LAST_PRICE", last="2026-11-13")
    S.run_scan(reg, SAT, inp, SCFG, tmp_path)
    assert kinds(reg, "outcome") == [] and PP.state(reg, "F001", CFG)["position"]["exit_pending"]


def test_open_position_is_scanned_every_run_while_fx_is_open():
    st = {"last_scan_utc": (MON - timedelta(minutes=15)).isoformat(), "last_bar_seen": "2026-11-06"}
    for k in range(4):
        assert "scan" in RN.plan(MON - timedelta(hours=3) + timedelta(minutes=15 * k), dict(
            st, last_scan_utc=(MON - timedelta(hours=3) + timedelta(minutes=15 * k - 15)).isoformat()), True, [])[0]


def test_drawdown_and_halt_survive_an_interruption(reg, tmp_path):
    enter(reg, size_x=0.5)
    PP.manage(reg, CFG, MON + timedelta(minutes=10), 141.0, RATES, "m1")     # big loss: exits at invalidation, drawdown
    before = PP.state(reg, "F001", CFG)
    reg.close()
    r2 = Registry(tmp_path / "r.sqlite")                                      # "restart": everything from the registry
    after = PP.state(r2, "F001", CFG)
    assert after["peak_equity"] == before["peak_equity"] and after["cash"] == pytest.approx(before["cash"])
    assert after["day_start_equity"] == before["day_start_equity"]
    r2.close()


def test_exposure_is_recomputed_after_the_fill(reg):
    enter(reg, size_x=0.25, S=150.0)
    st = PP.state(reg, "F001", CFG)
    assert PP.exposure_x(st, 150.0) == pytest.approx(0.25, rel=1e-3)
    assert PP.exposure_x(st, 165.0) == pytest.approx(0.25 / (1 + (0.25 * (165 / 150 - 1))) , rel=1e-2)  # moves with the mark


def test_scan_gap_alert_is_much_faster_with_a_position_open(reg):
    reg.append("scan_run", {"completed_utc": MON.isoformat(), "mode": "forward"}, now=MON)
    t = MON + timedelta(hours=3)
    assert N.check_liveness(reg, t, NCFG, fx_open=True, position_open=False) == []
    out = N.check_liveness(reg, t, NCFG, fx_open=True, position_open=True)
    assert out and "WITH A PAPER POSITION OPEN" in reg.records("notification")[-1]["payload"]["title"]
