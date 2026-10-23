"""Commodity study: release lags, no lookahead, registry."""
import numpy as np
import pandas as pd

from src import commodities as CM

CAL = pd.bdate_range("2020-01-01", "2020-03-31")


def test_h15_value_usable_on_second_trading_day_after():
    d = pd.DatetimeIndex(["2020-01-06"])                       # Monday
    assert CM.available_on(d, CAL, "h15_daily").iloc[0] == pd.Timestamp("2020-01-08")


def test_h10_week_usable_from_following_wednesday():
    d = pd.DatetimeIndex(["2020-01-06", "2020-01-10"])         # Monday and Friday of the same week
    a = CM.available_on(d, CAL, "h10_weekly")
    assert list(a) == [pd.Timestamp("2020-01-15")] * 2


def test_as_of_never_uses_unreleased_values():
    obs = pd.Series(np.arange(len(CAL), dtype=float), index=CAL)
    m = CM.as_of(obs, CAL, "h15_daily")
    assert np.isnan(m.iloc[0]) and np.isnan(m.iloc[1])
    assert (m.iloc[2:].to_numpy() == obs.iloc[:-2].to_numpy()).all()   # value at t is the obs of t-2


def _closes(n=600, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2010-01-01", periods=n)
    return pd.DataFrame({t: 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))) for t in CM.UNLEV}, index=idx)


def test_signals_have_no_lookahead():
    c = _closes()
    cash = pd.Series(0.0001, index=c.index)
    cut = c.index[450]
    c2 = c.copy()
    c2.loc[c2.index > cut] *= 1.5                                # change only the future
    for f in (lambda x: CM.i01_tsmom_basket(x, cash, 6)[0], lambda x: CM.i04_dual_momentum(x, cash, 3),
              lambda x: CM.i03_vol_scaled(x, 0.2)):
        a, b = f(c).loc[:cut], f(c2).loc[:cut]
        pd.testing.assert_frame_equal(a, b)


def test_tsmom_beats_tbill_rule():
    idx = pd.bdate_range("2010-01-01", periods=200)
    up = pd.DataFrame({t: np.linspace(100, 101, 200) for t in CM.UNLEV}, index=idx)   # +1% over the period
    w0, _ = CM.i01_tsmom_basket(up, pd.Series(0.0, index=idx), 3)
    w1, _ = CM.i01_tsmom_basket(up, pd.Series(0.001, index=idx), 3)                   # T-bills beat +1% / 63 days
    assert w0.iloc[-1].sum() > 0.99 and w1.iloc[-1].sum() == 0.0
