"""FX engine v2 (future experiments): balance accounting vs closed-form broker P&L, no sizing ratchet, daily cap,
labelled trades for K4, carry, markup, costs, lag, no lookahead; v1 stays unchanged."""
import numpy as np
import pandas as pd
import pytest

from src.fx_engine import run_fx
from src.fx_engine_v2 import holding_days, position_changes, run_balance, trade_counts

IDX = pd.bdate_range("2010-01-04", periods=30)


def series(v):
    return pd.Series(v, index=IDX, dtype=float)


def zero():
    return series(0.0)


def decide(**at):
    t = series(np.nan)
    for i, v in at.items():
        t.iloc[int(i[1:])] = v
    return t


def test_static_long_usdjpy_matches_broker_formula():
    """Long N USD/JPY (USD account) held from S0: P&L = N x (1 - S0 / S_t), not N x sum of daily (1 - S[i-1]/S[i])."""
    s = series(np.linspace(100, 130, 30))
    r = run_balance(s, zero(), zero(), decide(d0=1.0), 0.0, 0.0, 10000, invert=True)
    S0 = s.iloc[1]                                                  # executed at day 1 (lag 1)
    for i in (5, 15, 29):
        assert abs(r.equity.iloc[i] - (10000 + 10000 * (1 - S0 / s.iloc[i]))) < 1e-6
    v1 = run_fx(s, zero(), zero(), decide(d0=1.0), 0.0, 0.0, 10000)
    assert v1.equity.iloc[-1] > r.equity.iloc[-1] + 1                 # v1's implicit daily re-sizing (D3) differs


def test_gbpusd_orientation():
    """Long GBP/USD (asset = GBP, not inverted): P&L = N x (S_t / S0 - 1)."""
    s = series(np.linspace(1.20, 1.32, 30))
    r = run_balance(s, zero(), zero(), decide(d0=1.0), 0.0, 0.0, 10000)
    assert abs(r.equity.iloc[-1] - 10000 * s.iloc[-1] / s.iloc[1]) < 1e-6
    f = series(np.linspace(1.32, 1.20, 30))                          # short GBP/USD while GBP falls (no cap trims)
    rs = run_balance(f, zero(), zero(), decide(d0=-1.0), 0.0, 0.0, 10000)
    assert abs(rs.equity.iloc[-1] - (20000 - 10000 * f.iloc[-1] / f.iloc[1])) < 1e-6 and len(rs.trades) == 1


def test_no_ratchet_resizes_to_target_at_decisions():
    """D1: v1 never grows a position back after a loss trim; v2 is at the target after every decision."""
    s = series(np.r_[np.full(10, 100.0), np.full(10, 80.0), np.full(10, 120.0)])
    t = series(np.nan); t.iloc[::5] = 1.0                            # weekly decisions, always long
    r = run_balance(s, series(0.03), zero(), t, 0.0001, 0.0, 10000, invert=True)
    exec_days = IDX[1::5]
    assert np.allclose(r.exposure_x.loc[exec_days], 1.0, atol=1e-12)
    v1 = run_fx(s, series(0.03), zero(), t.ffill(), 0.0001, 0.0, 10000)
    assert abs(v1.notional.iloc[-1] / v1.equity.iloc[-1] - 1) > 0.02


def test_cap_enforced_at_every_close_and_trims_are_labelled():
    s = series(np.linspace(100, 70, 30))         # yen strengthens: a long USD/JPY (short JPY) position's yen debt grows
    r = run_balance(s, zero(), zero(), decide(d0=1.0), 0.001, 0.0, 10000, invert=True)
    assert (r.exposure_x.abs() <= 1 + 1e-12).all()
    c = trade_counts(r)
    assert c["open"] == 1 and c["cap_trim"] > 5 and position_changes(r) == 1
    s2 = series(np.linspace(100, 130, 30))       # short USD/JPY = long JPY with a zero USD balance: stays exactly 1x
    r2 = run_balance(s2, zero(), zero(), decide(d0=-1.0), 0.001, 0.0, 10000, invert=True)
    assert np.allclose(r2.exposure_x.iloc[1:], -1.0, atol=1e-12) and trade_counts(r2)["cap_trim"] == 0


def test_band_suppresses_small_resizes():
    s = series(np.r_[np.full(10, 100.0), np.full(20, 102.0)])   # long gains: exposure_x falls to ~0.96
    t = series(np.nan); t.iloc[::5] = 1.0
    a = run_balance(s, zero(), zero(), t, 0.0001, 0.0, 10000, invert=True, band=0.0)
    b = run_balance(s, zero(), zero(), t, 0.0001, 0.0, 10000, invert=True, band=0.05)
    assert trade_counts(a)["resize"] >= 1 and trade_counts(b)["resize"] == 0


def test_trade_kinds_and_position_changes():
    t = decide(d0=1.0, d5=1.0, d10=-1.0, d15=0.5, d20=0.0)
    s = series(np.linspace(100, 110, 30))
    r = run_balance(s, zero(), zero(), t, 0.0001, 0.0, 10000, invert=True)
    assert list(r.trades["kind"]) == ["open", "resize", "reverse", "reverse", "close"] or \
        list(r.trades["kind"]) == ["open", "reverse", "reverse", "close"]
    assert position_changes(r) == 4
    hd = holding_days(r)
    assert list(hd) == [10, 5, 5]


def test_costs_are_charged_on_traded_usd_and_exposure_is_exact_after_costs():
    r = run_balance(series(100.0), zero(), zero(), decide(d0=1.0, d10=0.0), 0.001, 0.0, 10000, invert=True)
    o, c = r.trades.iloc[0], r.trades.iloc[1]
    assert abs(o["cost_usd"] - 0.001 * o["usd_traded"]) < 1e-12
    assert abs(r.exposure_x.iloc[1] - 1.0) < 1e-12                    # exactly 1x after paying the entry cost
    assert abs(r.equity.iloc[-1] - (10000 - o["cost_usd"] - c["cost_usd"])) < 1e-9
    assert abs(o["usd_traded"] + o["cost_usd"] - 10000) < 1e-6


def test_carry_markup_and_cash_accrue_over_weekends():
    """Long USD/JPY 1x at a flat price: USD balance 2E earns r_usd act/360, JPY balance -E pays r_jpy act/365."""
    r = run_balance(series(100.0), series(0.05), series(0.01), decide(d0=1.0), 0.0, 0.0075, 10000, invert=True)
    fri, mon = IDX[4], IDX[5]
    assert (mon - fri).days == 3
    usd = r.equity.loc[fri] - r.units.loc[fri] / 100.0
    expo = abs(r.units.loc[fri] / 100.0)
    exp_change = usd * 0.05 * 3 / 360 - expo * 0.01 * 3 / 365 - expo * 0.0075 * 3 / 365
    assert abs((r.equity.loc[mon] - r.equity.loc[fri]) - exp_change) < 1e-9
    ov = r.overlay.loc[mon]
    assert abs(ov - (exp_change - r.equity.loc[fri] * 0.05 * 3 / 360) / r.equity.loc[fri]) < 1e-12


def test_flat_account_earns_cash_rate_only():
    r = run_balance(series(100.0), series(0.036), series(0.0), series(0.0), 0.0, 0.0, 10000)
    dd = np.diff(IDX).astype("timedelta64[D]").astype(int)
    assert abs(r.equity.iloc[-1] - 10000 * np.prod(1 + 0.036 * dd / 360)) < 1e-6
    assert (r.overlay.abs() < 1e-15).all() and len(r.trades) == 0


def test_lag_executes_at_next_price():
    s = series(np.arange(100, 130, dtype=float))
    r = run_balance(s, zero(), zero(), decide(d3=1.0), 0.0, 0.0, 10000, invert=True, lag=2)
    assert r.trades.iloc[0]["date"] == IDX[5] and r.trades.iloc[0]["price"] == s.iloc[5]


def test_no_lookahead():
    s = series(np.linspace(100, 120, 30))
    t = series(np.nan); t.iloc[::5] = 1.0
    a = run_balance(s, series(0.02), series(0.001), t, 0.0001, 0.005, 10000, invert=True)
    s2 = s.copy(); s2.iloc[20:] *= 0.5
    b = run_balance(s2, series(0.02), series(0.001), t, 0.0001, 0.005, 10000, invert=True)
    pd.testing.assert_series_equal(a.equity.iloc[:20], b.equity.iloc[:20])


def test_bad_inputs_rejected():
    with pytest.raises(ValueError):
        run_balance(series(100.0), zero(), zero(), decide(d0=1.5), 0.0, 0.0, 10000)
    s = series(100.0); s.iloc[3] = np.nan
    with pytest.raises(ValueError):
        run_balance(s, zero(), zero(), decide(d0=1.0), 0.0, 0.0, 10000)
    with pytest.raises(ValueError):
        run_balance(series(0.0), zero(), zero(), decide(d0=1.0), 0.0, 0.0, 10000)


def test_single_day_matches_v1():
    """Over one day after entry, v1 and v2 agree (D3 only matters over multi-day holds). The JPY rate is 0 here:
    v2 accrues JPY interest in yen and values it at the new rate, v1 at the entry rate (a ~0.002 USD difference)."""
    s = series(100.0); s.iloc[2:] = 104.0
    t = decide(d0=1.0)
    a = run_fx(s, series(0.04), series(0.0), t, 0.0, 0.0075, 10000)      # costs 0: v1 charges the entry cost on the
    b = run_balance(s, series(0.04), series(0.0), t, 0.0, 0.0075, 10000, invert=True)   # pre-cost equity (0.02% more)
    assert abs(a.equity.iloc[2] - b.equity.iloc[2]) < 1e-6


def test_cap_tolerance_reduces_trims_and_bounds_exposure():
    s = series(np.linspace(100, 70, 30))
    strict = run_balance(s, zero(), zero(), decide(d0=1.0), 0.001, 0.0, 10000, invert=True)
    loose = run_balance(s, zero(), zero(), decide(d0=1.0), 0.001, 0.0, 10000, invert=True, cap_tolerance=0.05)
    assert trade_counts(loose)["cap_trim"] < trade_counts(strict)["cap_trim"]
    assert (loose.exposure_x.abs() <= 1.05 + 1e-12).all() and loose.exposure_x.abs().max() > 1.0
