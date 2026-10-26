"""FX engine: spot P&L for a USD account, carry and markup with calendar-day accrual, costs, 1x cap, no lookahead."""
import numpy as np
import pandas as pd
import pytest

from src.fx_engine import run_fx, round_trips

IDX = pd.bdate_range("2010-01-04", periods=30)


def series(v):
    return pd.Series(v, index=IDX, dtype=float)


def test_flat_account_earns_cash_rate_only():
    r = run_fx(series(100.0), series(0.036), series(0.0), series(0), 0.0, 0.0, 10000)
    d = (IDX[-1] - IDX[0]).days
    assert abs(r.equity.iloc[-1] - 10000 * np.prod([1 + 0.036 * dd / 360 for dd in np.diff(IDX).astype("timedelta64[D]").astype(int)])) < 1e-6
    assert (r.overlay == 0).all() and d > 0


def test_long_spot_pnl_exact_and_costs():
    s = series(100.0)
    s.iloc[5:] = 110.0                                     # USD/JPY rises 10% on day 5
    t = series(np.nan); t.iloc[0] = 1                      # decide long on day 0 -> executed at day 1 price (100)
    r = run_fx(s, series(0.0), series(0.0), t, 0.0001, 0.0, 10000)
    N = 10000 * (1 - 0.0001)                               # notional after paying the entry cost
    assert abs(r.equity.iloc[-1] - (N + N * (1 - 100 / 110))) < 1e-6
    assert r.trades.iloc[0]["date"] == IDX[1] and abs(r.trades.iloc[0]["cost_usd"] - 1.0) < 1e-9


def test_carry_and_markup_accrue_over_weekends():
    t = series(np.nan); t.iloc[0] = 1
    r = run_fx(series(100.0), series(0.05), series(0.01), t, 0.0, 0.0075, 10000, start=None)
    fri, mon = IDX[4], IDX[5]                              # Fri 2010-01-08 -> Mon 2010-01-11 (3 calendar days)
    assert (mon - fri).days == 3
    e_f, e_m = r.equity.loc[fri], r.equity.loc[mon]
    N = r.notional.loc[fri]
    expected = e_f * 0.05 * 3 / 360 + N * (0.05 * 3 / 360 - 0.01 * 3 / 365) - N * 0.0075 * 3 / 365
    assert abs((e_m - e_f) - expected) < 1e-9


def test_short_and_switch_pays_double_notional():
    t = series(np.nan); t.iloc[0] = 1; t.iloc[10] = -1
    r = run_fx(series(100.0), series(0.0), series(0.0), t, 0.001, 0.0, 10000)
    sw = r.trades.iloc[1]
    assert sw["from"] == 1 and sw["to"] == -1
    assert abs(sw["usd_traded"] - (r.notional.iloc[10] * 1 + r.equity.iloc[11] + sw["cost_usd"])) < 5     # ~2N traded
    assert round_trips(r) == 2


def test_notional_never_exceeds_cap():
    s = series(np.linspace(100, 70, 30))                   # USD/JPY falls: a short position gains, equity rises
    t = series(np.nan); t.iloc[0] = -1
    r = run_fx(s, series(0.0), series(0.0), t, 0.0, 0.0, 10000, max_x=1.0)
    assert (r.notional.abs() <= r.equity * (1 + 1e-9)).all()


def test_no_lookahead():
    s = series(np.linspace(100, 120, 30))
    t = series(np.nan); t.iloc[0] = 1
    a = run_fx(s, series(0.02), series(0.0), t, 0.0001, 0.005, 10000)
    s2 = s.copy(); s2.iloc[20:] *= 0.5
    b = run_fx(s2, series(0.02), series(0.0), t, 0.0001, 0.005, 10000)
    pd.testing.assert_series_equal(a.equity.iloc[:20], b.equity.iloc[:20])


def test_bad_targets_and_missing_data_rejected():
    with pytest.raises(ValueError):
        run_fx(series(100.0), series(0.0), series(0.0), series(2), 0.0, 0.0, 10000)
    s = series(100.0); s.iloc[3] = np.nan
    with pytest.raises(ValueError):
        run_fx(s, series(0.0), series(0.0), series(0), 0.0, 0.0, 10000)


def test_resize_default_unchanged_and_diagnostic_resets_to_1x():
    s = series(np.r_[np.full(10, 100.0), np.full(10, 80.0), np.full(10, 120.0)])   # loss shrinks notional, then recovery
    t = series(np.nan); t.iloc[0] = 1
    a = run_fx(s, series(0.03), series(0.0), t, 0.0001, 0.0, 10000)
    b = run_fx(s, series(0.03), series(0.0), t, 0.0001, 0.0, 10000, resize=None)
    pd.testing.assert_series_equal(a.equity, b.equity)                  # default = frozen behaviour
    weekly = pd.Series(False, index=IDX); weekly.iloc[::5] = True
    c = run_fx(s, series(0.03), series(0.0), t, 0.0001, 0.0, 10000, resize=weekly)
    assert abs(a.notional.iloc[-1] / a.equity.iloc[-1] - 1.0) > 0.02     # frozen rule: drifted away from 1x
    assert abs(c.notional.iloc[-1] / c.equity.iloc[-1] - 1.0) < 0.02     # diagnostic: back near 1x after a re-size
    assert len(c.trades) > len(a.trades)                                # re-sizes are trades and pay costs
