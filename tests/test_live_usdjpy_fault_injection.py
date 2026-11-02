"""Fault injection (audit item 5, owner approval 2026-11-02): deliberately wrong accounting must end in
reconciliation failure -> HALTED -> a HIGH alert. Every test runs on a temporary, SYNTHETIC registry (never the live
database).

Faults that keep the ledger internally CONSISTENT (the snapshot agrees with the fills) are invisible to the exact
recomputation, and at small sizes they are below the $2 per $10,000 parity tolerance. Those tests are marked
xfail(strict=True): they document today's detection gap and MUST start passing when the zero-tolerance invariants
(one financing record per roll per position; fill = mid x (1 +/- cost) to 1e-9) ship in the 2026-11-06 batch."""
from datetime import datetime, timedelta, timezone

import pytest

from src.live_usdjpy import lifecycle as LC
from src.live_usdjpy import paper as PP
from src.live_usdjpy.registry import Registry
from tests.test_live_usdjpy_financing import CFG

GAP = pytest.mark.xfail(strict=True, reason="consistent-ledger fault below the $2 tolerance; zero-tolerance invariants ship in the 2026-11-06 batch (audit item 5)")
RATES = {"usd": {"history": [{"obs_date": "2026-11-20", "value": 0.04, "raw": "4.00", "first_seen_utc": "2026-11-21T00:00:00+00:00"}]},
         "jpy": {"history": [{"obs_date": "2026-10-01", "value": 0.01, "raw": "1.00", "first_seen_utc": "2026-11-01T00:00:00+00:00"}]}}
T0 = datetime(2026, 11, 23, 21, 0, tzinfo=timezone.utc)                   # Mon 16:00 EST
SIG = {"direction": 1, "invalidation": 120.0, "target": None, "bar_date": "2026-10-30", "version": "0.3", "expiry_rule": "x"}


@pytest.fixture
def reg(tmp_path):
    r = Registry(tmp_path / "isolated.sqlite")
    yield r
    r.close()


def open_and_roll(reg, days=3, size_x=0.5):
    LC.transition(reg, "F002-T", "triggered", {"bar_date": "2026-10-30"}, None, T0)
    PP.enter(reg, CFG, "F002", "F002-T", SIG, size_x, 150.0, T0, "s0", {"setup_id": "F002-T"})
    t = T0
    for k in range(days):
        t = t + timedelta(days=1, minutes=2)
        PP.manage(reg, CFG, t, 150.0 + 0.1 * k, RATES, "m%d" % k)
    return t


def halted_and_alerted(reg, t, S):
    ok, rep = PP.reconcile(reg, CFG, t + timedelta(minutes=1), S)
    return (not ok and reg.records("risk_state") and reg.records("risk_state")[-1]["payload"]["state"] == "HALTED"
            and any(r["payload"].get("priority") == "HIGH" or "RECONCILIATION MISMATCH" in r["payload"].get("title", "")
                    for r in reg.records("notification")))


def test_control_clean_path_reconciles(reg):
    t = open_and_roll(reg)
    ok, rep = PP.reconcile(reg, CFG, t + timedelta(minutes=1), 150.2)
    assert ok, rep


@GAP
def test_wrong_fill_price_consistent_in_fill_and_snapshot(reg, monkeypatch):
    real = PP._fill

    def bad(registry, st, oid, side_usd, notional, S, c, now, kind):
        return real(registry, st, oid, side_usd, notional, S * 1.0005, c, now, kind)   # 0.05% off the mid
    monkeypatch.setattr(PP, "_fill", bad)
    t = open_and_roll(reg)
    assert halted_and_alerted(reg, t, 150.2)


@GAP
def test_double_accrual_consistent(reg):
    t = open_and_roll(reg, days=1)
    st = PP.state(reg, "F002", CFG)
    f = [r["payload"] for r in reg.records("fill") if r["payload"]["type"] == "financing"][-1]
    st["usd_pos"] += f["usd_interest"]; st["jpy"] += f["jpy_interest"]; st["cash"] -= f["admin_fee_usd"]
    reg.append("fill", dict(f), idem_key="injected-double:%s" % f["roll_et"], now=t)          # same roll booked twice
    PP.snapshot(reg, st, t, "injected")
    assert halted_and_alerted(reg, t, 150.0)


@GAP
def test_missing_roll_consistent(reg, monkeypatch):
    real = PP.rolls_between
    monkeypatch.setattr(PP, "rolls_between", lambda a, b: [x for x in real(a, b) if x[0].weekday() != 1])   # Tuesday dropped
    t = open_and_roll(reg)
    assert halted_and_alerted(reg, t, 150.2)


def test_tampered_snapshot_is_detected(reg):
    t = open_and_roll(reg)
    st = PP.state(reg, "F002", CFG)
    st["jpy"] -= 100.0
    PP.snapshot(reg, st, t, "tampered (test)")
    assert halted_and_alerted(reg, t, 150.2)


def test_offsetting_errors_with_zero_net_equity_are_detected(reg):
    t = open_and_roll(reg)
    st = PP.state(reg, "F002", CFG)
    st["cash"] += 5.0
    st["usd_pos"] -= 5.0                                                   # equity unchanged at any mark
    PP.snapshot(reg, st, t, "offsetting (test)")
    assert halted_and_alerted(reg, t, 150.2)


@GAP
def test_true_up_applied_twice_consistent(reg):
    t = open_and_roll(reg, days=1)
    st = PP.state(reg, "F002", CFG)
    f = [r["payload"] for r in reg.records("fill") if r["payload"]["type"] == "financing"][-1]
    tu = dict(f, type="financing_trueup", conversion_mid=None, applied_to="position legs")
    for k in range(2):
        st["usd_pos"] += f["usd_interest"]; st["jpy"] += f["jpy_interest"]; st["cash"] -= f["admin_fee_usd"]
        reg.append("fill", tu, idem_key="injected-trueup-%d" % k, now=t)
    PP.snapshot(reg, st, t, "injected")
    assert halted_and_alerted(reg, t, 150.0)
