"""Phase 4 strategy tests: rules by hand, no lookahead, registry matches the frozen list."""
import csv

import numpy as np
import pandas as pd
import pytest

from src import PROJECT_ROOT, load_config
from src import strategies as S

CFG = load_config()


def rand_closes(n=700, seed=None, tickers=S.UNLEV):
    rng = np.random.default_rng(CFG["project"]["random_seed"] if seed is None else seed)
    idx = pd.bdate_range("2010-01-04", periods=n)
    data = {t: 100 * np.cumprod(1 + rng.normal(0.0003, 0.012, n)) for t in tickers}
    return pd.DataFrame(data, index=idx)


# ---------------------------------------------------------------- rules by hand

def test_rsi_series_equals_reused_wilder_rsi():
    c = rand_closes(120)["SPY"]
    r = S.rsi_series(c, 2)
    for i in (5, 30, 77, 119):
        assert r.iloc[i] == pytest.approx(S.wilder_rsi(list(c.iloc[:i + 1]), 2))
    assert r.iloc[:2].isna().all()


def test_trend_and_tsmom_signals_by_hand():
    c = pd.Series([1, 2, 3, 2, 1, 2, 4], index=pd.bdate_range("2021-01-04", periods=7), dtype=float)
    assert S.trend_signal(c, 3).tolist() == [0, 0, 1, 0, 0, 1, 1]      # SMA3: -,-,2,2.33,2,1.67,2.33
    k = S.TRADING_DAYS_PER_MONTH
    c2 = pd.Series(np.r_[np.full(k, 10.0), 11.0, 9.0], index=pd.bdate_range("2021-01-04", periods=k + 2))
    assert S.tsmom_signal(c2, 1).tolist()[-2:] == [1.0, 0.0]
    assert S.tsmom_signal(c2, 1).iloc[:k].sum() == 0                     # warm-up is cash


def test_rsi2_state_machine():
    idx = pd.bdate_range("2021-01-04", periods=12)
    c = pd.Series([10, 10.5, 11, 11.5, 12, 11, 10, 9.5, 9.6, 9.7, 12, 12.1], index=idx)
    sig = S.rsi2_signal(c, 15)
    r = S.rsi_series(c, 2)
    first = int(np.argmax((r < 15).to_numpy()))
    assert sig.iloc[first] == 1 and sig.iloc[:first].sum() == 0          # enters on the first RSI<15 close
    exit_i = next(i for i in range(first + 1, 12) if c.iloc[i] > c.rolling(5).mean().iloc[i])
    assert sig.iloc[first:exit_i].eq(1).all() and sig.iloc[exit_i] == 0  # exits on first close above SMA5


def test_rsi2_trend_filter_blocks_entries_below_sma200():
    c = pd.Series(np.linspace(200, 100, 260), index=pd.bdate_range("2020-01-01", periods=260))
    assert S.rsi2_signal(c, 15).sum() > 0                    # falling series: plain RSI(2) buys
    assert S.rsi2_signal(c, 15, trend_filter_days=200).sum() == 0


def test_rotation_picks_best_and_goes_to_cash_when_all_negative():
    idx = pd.bdate_range("2021-01-01", "2021-05-31")
    me = S.month_end_flags(idx)
    c = pd.DataFrame(100.0, index=idx, columns=S.UNLEV)
    c.loc["2021-02-01":, "QQQ"] = 110.0                       # QQQ best over Jan-end -> Feb-end
    c.loc["2021-04-01":, :] = 50.0                            # everything down by April-end
    pick = S.rotation_choice(c, 1)
    feb_end = idx[me.values][1]
    apr_end = idx[me.values][3]
    assert pick.loc[:idx[me.values][0]].isna().all()          # no lookback yet: cash
    assert pick.loc[feb_end] == "QQQ"
    assert pick.loc[apr_end] is None


def test_vol_gated_states():
    idx = pd.bdate_range("2019-01-01", periods=260)
    calm = pd.Series(100 * np.cumprod(np.r_[1.0, np.full(259, 1.001)]), index=idx)
    wl, w1 = S.vol_gated_weights(calm, 0.15)
    assert wl.iloc[-1] == 1 and w1.iloc[-1] == 0              # uptrend, ~0 vol -> leveraged
    wl, w1 = S.vol_gated_weights(calm, 0.0)
    assert wl.iloc[-1] == 0 and w1.iloc[-1] == 1              # vol >= threshold -> 1x
    assert (wl.iloc[:199] == 0).all() and (w1.iloc[:199] == 0).all()   # warm-up cash


def test_multi_trend_weights_quarter_slices():
    c = rand_closes(400)
    w, me = S.multi_trend_weights(c, 6)
    assert set(np.unique(w.to_numpy())) <= {0.0, 0.25}
    assert (w.sum(axis=1) <= 1.0).all()
    changes = w.diff().abs().sum(axis=1) > 0
    assert set(w.index[changes]) <= set(w.index[me.values])   # weights only change at month-ends


# ---------------------------------------------------------------- no lookahead, every variant

def test_no_variant_uses_future_data():
    c1 = rand_closes(700)
    cut = c1.index[450]
    c2 = c1.copy()
    c2.loc[c2.index > cut] *= np.linspace(0.3, 3.0, (c2.index > cut).sum())[:, None]
    v1, v2 = S.build_variants(c1), S.build_variants(c2)
    for a, b in zip(v1, v2):
        pd.testing.assert_frame_equal(a.targets.loc[:cut], b.targets.loc[:cut], obj=a.test_id)
        if a.rebalance is not None:
            pd.testing.assert_series_equal(a.rebalance.loc[:cut], b.rebalance.loc[:cut])


def test_targets_are_long_only_and_at_most_fully_invested():
    for v in S.build_variants(rand_closes(700)):
        t = v.targets.to_numpy()
        assert (t >= 0).all() and (t.sum(axis=1) <= 1 + 1e-12).all(), v.test_id


def test_signals_come_from_unleveraged_closes_only():
    # leveraged prices are not even an input: build_variants receives only GLD/SPY/QQQ/TLT closes
    c = rand_closes(300)
    for v in S.build_variants(c):
        held = [col for col in v.targets.columns if v.targets[col].abs().sum() > 0]
        assert set(held) <= set(S.UNLEV) | set(S.LEV.values()), v.test_id


# ---------------------------------------------------------------- registry == frozen list

def test_registry_matches_preregistered_research_log():
    with open(PROJECT_ROOT / "research_log.csv", newline="") as fh:
        reg = [r for r in csv.DictReader(fh) if r["result"] == "PRE-REGISTERED" and r["phase"] == "0.5-freeze"]
    vs = S.build_variants(rand_closes(300))
    assert len(vs) == len(reg) == CFG["strategies"]["total_trials"] == 92
    for v, r in zip(vs, reg):
        assert (v.test_id, v.strategy, v.signal_instrument, v.trade_instrument, v.params) == \
            (r["test_id"], r["strategy"], r["signal_instrument"], r["trade_instrument"], r["params"])
