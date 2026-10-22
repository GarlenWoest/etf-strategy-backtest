"""Phase 5 tool tests: trade episodes, walk-forward, bootstrap, DSR, effective trials."""
import math

import numpy as np
import pandas as pd
import pytest

from src import load_config
from src import validate as V
from src.engine import run_backtest

CFG = load_config()


def zero_cost():
    import copy
    c = copy.deepcopy(CFG)
    c["costs"]["half_spread"] = {"unleveraged": 0.0, "leveraged": 0.0}
    c["costs"]["slippage"] = 0.0
    return c


def test_trade_episodes_round_trips_by_hand():
    idx = pd.bdate_range("2021-01-04", periods=10)
    o = pd.Series([100, 100, 110, 120, 120, 90, 90, 100, 100, 100], index=idx, dtype=float)
    p = {"SPY": pd.DataFrame({"Open": o, "High": o, "Low": o, "Close": o})}
    tg = pd.DataFrame({"SPY": [1, 1, 1, 0, 1, 1, 0, 1, 1, 1]}, index=idx, dtype=float)
    r = run_backtest(p, tg, pd.Series(0.0, index=idx), zero_cost(), risk_layer=False)
    eps = V.trade_episodes(r, p)
    assert len(eps) == 3
    # buy 100 @ day1 open, sell @ day4 open 120: +20%
    assert eps[0]["ret"] == pytest.approx(0.20) and not eps[0]["open"]
    # target back to 1 at the day-4 close: buy @ day5 open 90, sell @ day7 open 100: +11.1%
    assert eps[1]["ret"] == pytest.approx(100 / 90 - 1)
    # buy @ day8 open 100, still open at the end, marked at close 100
    assert eps[2]["open"] and eps[2]["ret"] == pytest.approx(0.0)
    s = V.trade_stats(eps, idx[0], idx[-1])
    assert s["n_round_trips"] == 3 and s["n_completed"] == 2
    assert s["win_rate"] == pytest.approx(2 / 3)            # the flat open trade counts as a non-win
    assert s["profit_factor"] == float("inf")               # no losing trade


def test_walk_forward_picks_best_past_sharpe_and_never_peeks():
    idx = pd.bdate_range("2010-01-01", "2016-12-31")
    rng = np.random.default_rng(1)
    a = pd.Series(rng.normal(0.001, 0.01, len(idx)), index=idx)      # good in training years
    b = pd.Series(rng.normal(-0.001, 0.01, len(idx)), index=idx)
    b.loc["2015"] = 0.02                                               # b is great only in the test year
    stitched, chosen = V.walk_forward(pd.DataFrame({"a": a, "b": b}), pd.Series(0.0, index=idx), 2015, 2016)
    assert chosen == {2015: "a", 2016: "b"}       # 2016 may use 2015 (now in its training window)
    assert stitched.index.min() == pd.Timestamp("2015-01-01") and stitched.index.max().year == 2016
    pd.testing.assert_series_equal(stitched.loc["2015"], a.loc["2015"], check_names=False)


def test_bootstrap_is_seeded_and_brackets_the_estimate():
    rng = np.random.default_rng(0)
    x = rng.normal(0.0005, 0.01, 2000)
    lo1, hi1 = V.bootstrap_sharpe_ci(x, 2000, seed=7)
    lo2, hi2 = V.bootstrap_sharpe_ci(x, 2000, seed=7)
    assert (lo1, hi1) == (lo2, hi2)
    est = x.mean() / x.std(ddof=1) * math.sqrt(252)
    assert lo1 < est < hi1


def test_psr_and_dsr_properties():
    assert V.probabilistic_sharpe(0.05, 0.05, 1000, 0.0, 3.0) == pytest.approx(0.5)
    # normal returns: PSR = Phi((sr - sr0) * sqrt(T-1) / sqrt(1 + sr^2/2))
    sr, sr0, t = 0.06, 0.0, 1260
    want = V.stats.norm.cdf(sr * math.sqrt(t - 1) / math.sqrt(1 + sr ** 2 / 2))
    assert V.probabilistic_sharpe(sr, sr0, t, 0.0, 3.0) == pytest.approx(want)
    # the deflation hurdle grows with the number of trials
    assert V.expected_max_sharpe(0.001, 100) > V.expected_max_sharpe(0.001, 10) > 0
    x = np.random.default_rng(3).normal(0.001, 0.01, 1260)
    d1, h1 = V.deflated_sharpe(x, [0.0, 0.02, 0.04, 0.06], 2)
    d2, h2 = V.deflated_sharpe(x, [0.0, 0.02, 0.04, 0.06], 92)
    assert h2 > h1 and d2 < d1


def test_effective_trials():
    rng = np.random.default_rng(5)
    base = rng.normal(size=(500, 1))
    same = np.hstack([base] * 5)
    assert V.effective_trials(same) == pytest.approx(1.0)
    indep = rng.normal(size=(5000, 6))
    assert V.effective_trials(indep) == pytest.approx(6.0, rel=0.05)


def test_monte_carlo_constant_returns_by_hand():
    # +1% a day, zero cash rate: $100 reaches $1,000 on the first day with 100 * 1.01^d >= 1000
    d = int(np.ceil(np.log(10) / np.log(1.01)))
    out = V.monte_carlo(np.full(50, 0.01), np.zeros(50), 1.0, 0, 1.0, CFG, 200, 20, 2, seed=1)
    assert out["p_reach_before_ruin"] == 1.0
    assert out["time_to_target_years"][50] == pytest.approx(d / 252)


def test_monte_carlo_ruin_and_sizing():
    # -2% a day all-in: reaches $20 first; at 20% size the account loses only 0.4% a day
    out = V.monte_carlo(np.full(50, -0.02), np.zeros(50), 1.0, 0, 1.0, CFG, 100, 20, 1, seed=1)
    assert out["p_ruin_first"] == 1.0 and out["p_reach_before_ruin"] == 0.0
    out = V.monte_carlo(np.full(50, -0.02), np.full(50, 0.0), 0.2, 0, 1.0, CFG, 100, 20, 1, seed=1)
    assert out["values"][1][50] == pytest.approx(100 * (1 - 0.004) ** 252)


def test_monte_carlo_contributions_count_toward_target():
    # flat returns, $100 a month: $1,000 after 9 contributions = 189 trading days
    out = V.monte_carlo(np.zeros(30), np.zeros(30), 1.0, 100, 1.0, CFG, 50, 20, 2, seed=2)
    assert out["time_to_target_years"][50] == pytest.approx(189 / 252)
    assert out["values"][1][50] == pytest.approx(100 + 100 * (252 // 21))


def test_monte_carlo_switch_caps_exposure_and_kill_switch():
    # +10% a day until the switch, then the cap 0.3 applies: growth slows to +3% a day
    out = V.monte_carlo(np.full(40, 0.10), np.zeros(40), 1.0, 0, 0.3, CFG, 10, 20, 1, seed=3)
    d = int(np.ceil(np.log(10) / np.log(1.1)))
    assert out["time_to_target_years"][50] == pytest.approx(d / 252)
    after = 100 * 1.1 ** d * 1.03 ** (252 - d)
    assert out["values"][1][50] == pytest.approx(after, rel=1e-9)
    # a crash after the switch triggers the kill switch: account then stays in cash
    r = np.r_[np.full(30, 0.10), np.full(10, -0.5)]
    out = V.monte_carlo(r, np.zeros(40), 1.0, 0, 1.0, CFG, 20, 40, 1, seed=4)
    assert out["p_killed"] > 0
