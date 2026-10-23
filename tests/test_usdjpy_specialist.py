"""USD/JPY specialist: point-in-time lags, weekly decision days, signal signs (synthetic data only)."""
import numpy as np
import pandas as pd
import pytest

from src.specialists import usdjpy as U
from src.specialists import status, require_active

CAL = pd.bdate_range("2012-01-02", periods=400)


def frame(**kw):
    base = dict(spot=100.0, us1=0.03, us2=0.03, us10=0.04, tbill=0.02, jp1=0.001, jp2=0.001, jp10=0.01, vix=15.0)
    base.update(kw)
    return pd.DataFrame({k: (v if isinstance(v, pd.Series) else pd.Series(float(v), index=CAL)) for k, v in base.items()})


def test_lag_to_uses_only_past_observations():
    obs = pd.Series(np.arange(len(CAL), dtype=float), index=CAL)
    l2 = U.lag_to(obs, CAL, 2)
    assert np.isnan(l2.iloc[0]) and np.isnan(l2.iloc[1]) and l2.iloc[2] == 0 and l2.iloc[10] == 8


def test_weekly_flags_last_trading_day_of_week():
    f = U.weekly_flags(CAL)
    assert all(d.weekday() == 4 for d in CAL[f.to_numpy()][:-1])          # Fridays in a holiday-free calendar


def test_carry_level_thresholds():
    d = frame(us2=pd.Series(np.r_[np.full(200, 0.02), np.full(200, 0.005)], index=CAL), jp2=0.001)
    s = U.carry_level(d, 2).dropna()
    assert s.iloc[0] == 1 and s.iloc[-1] == 0                               # 1.9 pp -> long, 0.4 pp -> flat
    d2 = frame(us2=0.001, jp2=0.03)
    assert (U.carry_level(d2, 2).dropna() == -1).all()                      # Japan higher by 2.9 pp -> short


def test_diff_momentum_and_relative_slope_signs():
    rising = pd.Series(np.linspace(0.01, 0.04, len(CAL)), index=CAL)
    s = U.diff_momentum(frame(us2=rising), 63).dropna()
    assert s.iloc[-1] == 1                                                   # widening differential -> long
    steep = pd.Series(np.linspace(0.03, 0.06, len(CAL)), index=CAL)        # US 10y rising, US curve steepening
    r = U.relative_slope_change(frame(us10=steep), 63).dropna()
    assert r.iloc[-1] == -1                                                  # relative US steepening -> short (Chen & Tsang)


def test_riskoff_filter_flattens_carry():
    vix = pd.Series(15.0, index=CAL); vix.iloc[-20:] = 60.0
    s = U.carry_riskoff(frame(vix=vix, us2=0.03), "vix").dropna()
    assert s.iloc[-1] == 0 and s.iloc[-30] == 1


def test_signals_no_lookahead():
    d = frame(us2=pd.Series(np.linspace(0.01, 0.04, len(CAL)), index=CAL))
    d2 = d.copy(); d2.iloc[300:, :] = d2.iloc[300:, :] * 3
    for f in (lambda x: U.diff_momentum(x, 63), lambda x: U.carry_riskoff(x, "vol"), lambda x: U.relative_slope_change(x, 126)):
        pd.testing.assert_series_equal(f(d).iloc[:300], f(d2).iloc[:300])


def test_only_active_specialists_may_research():
    assert status("usdjpy") == "active" and status("gold") == "monitoring"
    with pytest.raises(PermissionError):
        require_active("gbpusd")
