"""Phase 3 engine tests. Required by the plan:
no lookahead; costs applied correctly; adjusted prices used consistently; cash interest
applied correctly; buy-and-hold matches the instrument's raw return within rounding;
the mode switch triggers exactly once at $1,000. (The synthetic formula's hand
calculation is in test_data.py.)
"""
import copy

import numpy as np
import pandas as pd
import pytest

from src import load_config
from src import data as D
from src import metrics as M
from src import strategies as S
from src.engine import run_backtest

CFG = load_config()
IDX = pd.bdate_range("2021-01-04", periods=12)


def cfg_with(**costs):
    c = copy.deepcopy(CFG)
    c["costs"].update(costs)
    return c


def zero_cost_cfg():
    return cfg_with(half_spread={"unleveraged": 0.0, "leveraged": 0.0}, slippage=0.0)


def px(opens, closes, idx=IDX):
    o = pd.Series(opens, index=idx[:len(opens)], dtype=float)
    c = pd.Series(closes, index=idx[:len(closes)], dtype=float)
    return pd.DataFrame({"Open": o, "High": np.maximum(o, c), "Low": np.minimum(o, c), "Close": c})


def zero_rate(idx=IDX):
    return pd.Series(0.0, index=idx)


# ---------------------------------------------------------------- costs, by hand

def test_buy_cost_hand_calculation():
    prices = {"SPY": px([100] * 3 + [110] * 9, [100, 105] + [110] * 10)}
    tg = pd.DataFrame({"SPY": 1.0}, index=IDX)
    r = run_backtest(prices, tg, zero_rate(), CFG, risk_layer=False)
    t = r.trades.iloc[0]
    # decided at close of day 0, executed at open of day 1 = 100
    assert t["date"] == IDX[1] and t["side"] == "buy" and t["ref_open"] == 100
    hs, sl = 0.0002, 0.0005
    exec_px = 100 * (1 + hs + sl)                       # 100.07
    shares = 100.0 / exec_px                             # all $100 spent, fractional
    assert t["exec_price"] == pytest.approx(exec_px)
    assert t["shares"] == pytest.approx(shares)
    assert t["half_spread_cost"] == pytest.approx(shares * 100 * hs)
    assert t["slippage_cost"] == pytest.approx(shares * 100 * sl)
    assert t["half_spread_cost"] + t["slippage_cost"] + t["notional_at_open"] == pytest.approx(100.0)
    assert r.cash.iloc[1] == pytest.approx(0.0, abs=1e-9)
    assert r.equity.iloc[1] == pytest.approx(shares * 105)


def test_sell_cost_and_leveraged_spread():
    prices = {"UPRO": px([50] * 12, [50] * 12)}
    tg = pd.DataFrame({"UPRO": [1.0, 1.0, 0.0] + [0.0] * 9}, index=IDX)
    r = run_backtest(prices, tg, zero_rate(), CFG, risk_layer=False)
    buy, sell = r.trades.iloc[0], r.trades.iloc[1]
    c = 0.0005 + 0.0005                                  # leveraged half-spread + slippage
    assert buy["exec_price"] == pytest.approx(50 * (1 + c))
    assert sell["date"] == IDX[3] and sell["exec_price"] == pytest.approx(50 * (1 - c))
    assert r.equity.iloc[-1] == pytest.approx(100 * (1 - c) / (1 + c))   # round trip at a flat price


def test_cost_multiplier_scales_costs():
    prices = {"SPY": px([100] * 12, [100] * 12)}
    tg = pd.DataFrame({"SPY": 1.0}, index=IDX)
    t3 = run_backtest(prices, tg, zero_rate(), CFG, cost_mult=3, risk_layer=False).trades.iloc[0]
    assert t3["exec_price"] == pytest.approx(100 * (1 + 3 * 0.0007))


def test_min_order_skips_small_buys_but_allows_full_exit():
    prices = {"SPY": px([100] * 12, [100] * 12), "QQQ": px([100] * 12, [100] * 12)}
    tg = pd.DataFrame({"SPY": [0.995] * 12, "QQQ": [0.005] * 12}, index=IDX)   # QQQ slice = $0.50
    r = run_backtest(prices, tg, zero_rate(), zero_cost_cfg(), risk_layer=False)
    assert list(r.trades["ticker"]) == ["SPY"]


def test_targets_must_be_long_only_and_unlevered():
    prices = {"SPY": px([100] * 12, [100] * 12)}
    with pytest.raises(ValueError):
        run_backtest(prices, pd.DataFrame({"SPY": 1.5}, index=IDX), zero_rate(), CFG)
    with pytest.raises(ValueError):
        run_backtest(prices, pd.DataFrame({"SPY": -0.5}, index=IDX), zero_rate(), CFG)


# ---------------------------------------------------------------- no lookahead

def sma_signal(close, n=3):
    """A test strategy that uses only past closes: long when close > n-day SMA."""
    return (close > close.rolling(n).mean()).astype(float).to_frame("SPY")


def test_no_lookahead_future_changes_do_not_change_the_past():
    idx = pd.bdate_range("2021-01-04", periods=60)
    rng = np.random.default_rng(CFG["project"]["random_seed"])
    close = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, 60)), index=idx)
    open_ = close.shift(1).fillna(100) * (1 + rng.normal(0, 0.002, 60))
    p1 = {"SPY": px(open_.values, close.values, idx)}
    cut = idx[40]
    close2 = close.copy()
    close2[close2.index > cut] *= 1.5                    # change the future only
    open2 = open_.copy()
    open2[open2.index > cut] *= 0.5
    p2 = {"SPY": px(open2.values, close2.values, idx)}
    s1, s2 = sma_signal(p1["SPY"]["Close"]), sma_signal(p2["SPY"]["Close"])
    pd.testing.assert_frame_equal(s1.loc[:cut], s2.loc[:cut])
    r1 = run_backtest(p1, s1, zero_rate(idx), CFG, risk_layer=False)
    r2 = run_backtest(p2, s2, zero_rate(idx), CFG, risk_layer=False)
    pd.testing.assert_series_equal(r1.equity.loc[:cut], r2.equity.loc[:cut])
    t1 = r1.trades[r1.trades["date"] <= cut].reset_index(drop=True)
    t2 = r2.trades[r2.trades["date"] <= cut].reset_index(drop=True)
    pd.testing.assert_frame_equal(t1, t2)


def test_signal_at_close_fills_at_next_open_never_same_day():
    idx = pd.bdate_range("2021-01-04", periods=10)
    tg = pd.DataFrame({"SPY": [0, 0, 0, 1, 1, 1, 0, 0, 0, 0]}, index=idx, dtype=float)
    prices = {"SPY": px(np.arange(10) + 100.0, np.arange(10) + 100.5, idx)}
    r = run_backtest(prices, tg, zero_rate(idx), CFG, risk_layer=False)
    assert list(r.trades["date"]) == [idx[4], idx[7]]
    assert list(r.trades["ref_open"]) == [104.0, 107.0]


# ---------------------------------------------------------------- cash interest

def test_cash_interest_compounds_prior_day_rate():
    rate = pd.Series(np.linspace(0.0001, 0.0003, 12), index=IDX)
    prices = {"SPY": px([100] * 12, [100] * 12)}
    r = run_backtest(prices, pd.DataFrame({"SPY": 0.0}, index=IDX), rate, CFG, risk_layer=False)
    expected = 100 * np.cumprod(np.r_[1.0, 1 + rate.values[:-1]])
    np.testing.assert_allclose(r.equity.values, expected, rtol=1e-12)
    assert r.trades.empty


def test_uninvested_remainder_earns_interest():
    rate = pd.Series(0.0002, index=IDX)
    prices = {"SPY": px([100] * 12, [100] * 12)}
    r = run_backtest(prices, pd.DataFrame({"SPY": 0.5}, index=IDX), rate, zero_cost_cfg(), risk_layer=False)
    # $100 x (1.0002) at the day-1 open, half invested; the cash half compounds afterwards
    half = 100 * 1.0002 / 2
    assert r.equity.iloc[-1] == pytest.approx(half + half * 1.0002 ** 10)


# ---------------------------------------------------------------- buy and hold vs raw

def test_buy_and_hold_matches_raw_return_synthetic():
    prices = {"QQQ": px([100, 101, 99, 103, 104, 98, 97, 105, 106, 104, 108, 110],
                        [100, 100, 102, 104, 101, 99, 103, 106, 103, 107, 109, 111])}
    r = run_backtest(prices, S.buy_and_hold(IDX, "QQQ"), zero_rate(), zero_cost_cfg(), risk_layer=False)
    raw = 100 * prices["QQQ"]["Close"].iloc[-1] / prices["QQQ"]["Open"].iloc[1]
    assert r.equity.iloc[-1] == pytest.approx(raw, rel=1e-12)


# ---------------------------------------------------------------- adjusted prices

def _have_clean():
    return (D.clean_dir(CFG) / "prices" / "SPY.csv").exists()


@pytest.mark.skipif(not _have_clean(), reason="run build_clean() first")
def test_adjusted_prices_give_total_return_consistently():
    """Engine buy-and-hold on adjusted SPY (2010-2014) equals total return rebuilt from
    unadjusted closes with dividends reinvested at the ex-date close, within 0.1%."""
    spy = D.load_clean("SPY").loc["2010-01-04":"2014-12-31"]
    cash = pd.Series(0.0, index=spy.index)
    r = run_backtest({"SPY": spy}, S.buy_and_hold(spy.index, "SPY"), cash, zero_cost_cfg(), risk_layer=False)
    eng = r.equity.iloc[-1] / r.equity.iloc[0]
    u = D.load_raw("SPY", "yahoo_unadj").loc[spy.index]
    start_open_adj = spy["Open"].iloc[1]
    start_open_unadj = start_open_adj * u["Close"].iloc[1] / spy["Close"].iloc[1]   # same-day adjustment factor
    shares = 1.0 / start_open_unadj
    for d in u.index[2:]:
        if u.at[d, "Dividends"] > 0:
            shares += shares * u.at[d, "Dividends"] / u.at[d, "Close"]
    tr = shares * u["Close"].iloc[-1]
    assert eng == pytest.approx(tr, rel=1e-3)
    price_only = u["Close"].iloc[-1] / start_open_unadj
    assert eng > price_only * 1.05                      # dividends are really in the adjusted series


# ---------------------------------------------------------------- risk mode switch

def test_mode_switch_triggers_exactly_once_at_1000():
    idx = pd.bdate_range("2021-01-04", periods=10)
    #                         buy  x5    x10.5  below   back above   higher
    closes = [100, 100, 500, 1050, 900, 1100, 1200, 1100, 1000, 1000]
    prices = {"SPY": px([100, 100, 500, 1050, 900, 1100, 1200, 1100, 1000, 1000], closes, idx)}
    r = run_backtest(prices, S.buy_and_hold(idx, "SPY"), zero_rate(idx), zero_cost_cfg(), risk_layer=True)
    assert r.switch_count == 1
    assert r.switch_date == idx[3]                       # first close >= $1,000
    assert (r.mode.loc[:idx[2]] == "aggressive").all()
    assert r.mode.loc[idx[3]:].str.startswith("phase_7b").all()   # stays on after equity drops below 1,000
    # Phase 7B cap: 100% target cut to the 50% single-instrument cap at the next open
    cut = r.trades[r.trades["date"] == idx[4]]
    assert list(cut["side"]) == ["sell"]
    assert r.weights.loc[idx[4], "SPY"] == pytest.approx(0.5)


def test_switch_never_happens_below_1000_and_can_be_disabled():
    idx = pd.bdate_range("2021-01-04", periods=6)
    prices = {"SPY": px([100] * 6, [100, 100, 500, 999.99, 999, 998], idx)}
    r = run_backtest(prices, S.buy_and_hold(idx, "SPY"), zero_rate(idx), zero_cost_cfg(), risk_layer=True)
    assert r.switch_count == 0 and (r.mode == "aggressive").all()
    prices = {"SPY": px([100] * 6, [100, 100, 5000, 6000, 7000, 8000], idx)}
    r = run_backtest(prices, S.buy_and_hold(idx, "SPY"), zero_rate(idx), zero_cost_cfg(), risk_layer=False)
    assert r.switch_count == 0


def test_phase7b_leveraged_cap_and_kill_switch():
    idx = pd.bdate_range("2021-01-04", periods=12)
    closes = [100, 100, 1200, 1200, 1200, 1200, 900, 900, 900, 2000, 2000, 2000]
    prices = {"UPRO": px([100, 100] + closes[1:-1], closes, idx)}
    r = run_backtest(prices, S.buy_and_hold(idx, "UPRO"), zero_rate(idx), zero_cost_cfg(), risk_layer=True)
    assert r.switch_date == idx[2]
    assert r.weights.loc[idx[3], "UPRO"] == pytest.approx(0.3)   # single leveraged ETF cap 30%
    # peak after switch: equity on idx[3..5]; drop on idx[6] exceeds 20% only if equity falls enough
    peak = r.equity.loc[idx[2]:idx[5]].max()
    killed = r.equity.loc[idx[6]] <= 0.8 * peak
    assert (r.kill_date is not None) == bool(killed)


def test_kill_switch_moves_everything_to_cash_for_good():
    idx = pd.bdate_range("2021-01-04", periods=10)
    closes = [100, 100, 1100, 1100, 300, 300, 300, 3000, 3000, 3000]
    prices = {"SPY": px([100, 100] + closes[1:-1], closes, idx)}
    r = run_backtest(prices, S.buy_and_hold(idx, "SPY"), zero_rate(idx), zero_cost_cfg(), risk_layer=True)
    assert r.kill_date == idx[4]
    assert r.weights.loc[idx[5]:, "SPY"].abs().max() == pytest.approx(0.0)
    assert r.equity.iloc[-1] == pytest.approx(r.equity.loc[idx[5]])


# ---------------------------------------------------------------- equal weight and RSI helper

def test_equal_weight_rebalances_monthly():
    idx = pd.bdate_range("2021-01-25", "2021-03-10")
    p = {t: px([100.0] * len(idx), [100.0] * len(idx), idx) for t in ("GLD", "QQQ", "TLT")}
    spy = np.linspace(100, 160, len(idx))                # SPY drifts up, so rebalances are needed
    p["SPY"] = px(spy, spy, idx)
    w, flag = S.equal_weight(idx, ["GLD", "SPY", "QQQ", "TLT"])
    assert list(idx[flag.values]) == [pd.Timestamp("2021-01-29"), pd.Timestamp("2021-02-26")]
    r = run_backtest(p, w, zero_rate(idx), CFG, rebalance=flag, risk_layer=False)
    assert sorted(r.trades["date"].unique()) == [idx[1], pd.Timestamp("2021-02-01"), pd.Timestamp("2021-03-01")]
    for d in (pd.Timestamp("2021-02-01"), pd.Timestamp("2021-03-01")):
        t = r.trades[r.trades["date"] == d]
        assert set(t[t["side"] == "sell"]["ticker"]) == {"SPY"}   # trim the winner, top up the rest


def test_wilder_rsi_textbook_and_flat():
    closes = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61,
              46.28, 46.28]
    assert S.wilder_rsi(closes) == pytest.approx(70.46, abs=0.05)
    assert S.wilder_rsi([1.0] * 20) == 50.0
    assert S.wilder_rsi([float(x) for x in range(1, 40)]) == 100.0
    assert S.wilder_rsi([1.0] * 5) is None


# ---------------------------------------------------------------- metrics

def test_metrics_by_hand():
    idx = pd.date_range("2020-01-01", "2022-01-01", freq="D")
    e = pd.Series(np.linspace(100, 121, len(idx)), index=idx)
    yrs = (idx[-1] - idx[0]).days / 365.25
    assert M.cagr(e) == pytest.approx(1.21 ** (1 / yrs) - 1)
    e2 = pd.Series([100, 120, 90, 110, 130, 65], index=pd.bdate_range("2021-01-04", periods=6), dtype=float)
    assert M.max_drawdown(e2) == pytest.approx(65 / 130 - 1)
    assert M.max_drawdown_duration(e2) == 2


@pytest.mark.skipif(not _have_clean(), reason="run build_clean() first")
def test_equal_weight_engine_matches_independent_direct_calculation():
    """Zero costs, no minimum order, zero cash rate: engine == hand-rolled monthly rebalance."""
    c = zero_cost_cfg()
    c["capital"]["min_order_usd"] = 0.0
    eq4 = CFG["instruments"]["unleveraged"]
    raw = {t: D.load_clean(t).loc["2005-01-01":"2007-12-31"] for t in eq4}
    idx = raw["SPY"].index
    w, flag = S.equal_weight(idx, eq4)
    r = run_backtest(raw, w, pd.Series(0.0, index=idx), c, rebalance=flag, risk_layer=False)
    month = idx.to_period("M")
    reb = set(idx[1:][month[1:] != month[:-1]]) | {idx[1]}
    val, shares = [100.0], None
    for d in idx[1:]:
        if d in reb:
            v = 100.0 if shares is None else sum(shares[t] * raw[t].at[d, "Open"] for t in eq4)
            shares = {t: v / 4 / raw[t].at[d, "Open"] for t in eq4}
        val.append(sum(shares[t] * raw[t].at[d, "Close"] for t in eq4))
    np.testing.assert_allclose(r.equity.values, val, rtol=1e-10)
