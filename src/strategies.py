"""Strategy definitions for the frozen list (config.yaml strategies).

Every strategy returns target weights: a DataFrame indexed by trading day whose row
for day t uses only data up to the close of t. The engine executes it at open t+1.
Phase 3 provides the benchmarks and the RSI helper; Phase 4 adds the trial strategies.
"""
import numpy as np
import pandas as pd


def buy_and_hold(index, ticker):
    """100% in one ticker from the first close onward (bought at the next open)."""
    return pd.DataFrame({ticker: 1.0}, index=index)


def equal_weight(index, tickers):
    """Equal weight, rebalanced at the open after each month's last trading day.

    Returns (targets, rebalance_flags). The flag is True on the last trading day of
    each month (known at that close, because the next trading day is in a new month).
    """
    w = pd.DataFrame(1.0 / len(tickers), index=index, columns=list(tickers))
    month = index.to_period("M")
    flag = pd.Series(np.r_[month[1:] != month[:-1], False], index=index)
    return w, flag


def wilder_rsi(closes, n=14):
    """Wilder's RSI on a list of closes; returns the RSI at the last close.

    Copied from day-trader-skill (MIT License, Copyright (c) 2026 Jake Schincariol),
    commit 3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd, trader-scanner/scan.py:485-495,
    audited in AUDIT.md. One change: a series with no up and no down moves returns
    50 instead of 100.
    """
    if len(closes) < n + 1:
        return None
    g = [max(0.0, closes[i] - closes[i - 1]) for i in range(1, len(closes))]
    lo = [max(0.0, closes[i - 1] - closes[i]) for i in range(1, len(closes))]
    ag, al = sum(g[:n]) / n, sum(lo[:n]) / n
    for i in range(n, len(g)):
        ag = (ag * (n - 1) + g[i]) / n
        al = (al * (n - 1) + lo[i]) / n
    if al == 0:
        return 50.0 if ag == 0 else 100.0
    return 100 - 100 / (1 + ag / al)


# ================================================================ Phase 4: the frozen trial list
#
# Shared conventions (config.yaml strategies, frozen 2026-10-22):
#  - Signals always come from the UNLEVERAGED ETF's adjusted close. Positions may be held
#    in the leveraged version (LEV map).
#  - Every row t uses data up to and including the close of t only. The engine executes it
#    at the next open.
#  - Before a lookback is filled the target is 0 (cash).
#  - "Month-end" = the last trading day of a calendar month, known at that close because the
#    next trading day falls in a new month (the same rule as equal_weight).

from dataclasses import dataclass

TRADING_DAYS_PER_MONTH = 21
UNLEV = ["GLD", "SPY", "QQQ", "TLT"]
LEV = {"GLD": "UGL", "SPY": "UPRO", "QQQ": "TQQQ", "TLT": "TMF"}


def sma(close, n):
    return close.rolling(n, min_periods=n).mean()


def rsi_series(close, n=2):
    """Vectorized Wilder RSI: same recursion as wilder_rsi (seeded with the simple mean of the
    first n gains/losses, then (prev * (n - 1) + x) / n). Flat stretches give 50."""
    d = close.diff()
    g, lo = d.clip(lower=0), (-d).clip(lower=0)
    gv, lv = g.to_numpy(), lo.to_numpy()
    a_g, a_l = np.full(len(close), np.nan), np.full(len(close), np.nan)
    if len(close) > n:
        a_g[n] = np.nanmean(gv[1:n + 1])
        a_l[n] = np.nanmean(lv[1:n + 1])
        for i in range(n + 1, len(close)):
            a_g[i] = (a_g[i - 1] * (n - 1) + gv[i]) / n
            a_l[i] = (a_l[i - 1] * (n - 1) + lv[i]) / n
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = a_g / a_l
        out = 100 - 100 / (1 + rs)
    out = np.where((a_l == 0) & (a_g == 0), 50.0, np.where(a_l == 0, 100.0, out))
    out[np.isnan(a_g)] = np.nan
    return pd.Series(out, index=close.index)


def month_end_flags(index):
    month = index.to_period("M")
    return pd.Series(np.r_[month[1:] != month[:-1], False], index=index)


def realized_vol(close, n=20):
    return close.pct_change().rolling(n, min_periods=n).std() * np.sqrt(252)


# ---------------------------------------------------------------- signal functions (0/1 or weights)

def trend_signal(close, n):
    """S2: 1 when close > n-day SMA, else 0."""
    return (close > sma(close, n)).astype(float)


def tsmom_signal(close, months):
    """S3: 1 when the trailing return over months x 21 trading days is positive, else 0."""
    k = months * TRADING_DAYS_PER_MONTH
    ret = close / close.shift(k) - 1
    return (ret > 0).astype(float)


def rsi2_signal(close, entry_below, trend_filter_days=None):
    """S4 / P3 state machine at each close:
    flat -> long when RSI(2) < entry_below (and, for P3, close > trend_filter_days SMA);
    long -> flat when close > 5-day SMA. Exit is not checked on the entry close."""
    r = rsi_series(close, 2).to_numpy()
    s5 = sma(close, 5).to_numpy()
    c = close.to_numpy()
    filt = np.ones(len(c), bool)
    if trend_filter_days:
        f = sma(close, trend_filter_days).to_numpy()
        filt = c > f                                   # NaN SMA compares False: no entries during warm-up
    pos = np.zeros(len(c))
    long = False
    for i in range(len(c)):
        if long:
            if c[i] > s5[i]:
                long = False
        elif r[i] < entry_below and filt[i]:
            long = True
        pos[i] = 1.0 if long else 0.0
    return pd.Series(pos, index=close.index)


def rotation_choice(closes, months):
    """S5/S6: at each month-end close, the ticker with the highest trailing `months`-month
    return (month-end to month-end); None (cash) if that return is <= 0 or a lookback is
    missing. Held until the next month-end. Returns a Series of tickers/None."""
    idx = closes.index
    me = month_end_flags(idx)
    me_closes = closes[me.values]
    trail = me_closes / me_closes.shift(months) - 1
    pick = pd.Series([None] * len(idx), index=idx, dtype=object)
    cur = None
    me_dates = set(me_closes.index)
    for d in idx:
        if d in me_dates:
            row = trail.loc[d]
            if row.isna().any():
                cur = None
            else:
                best = row.idxmax()
                cur = best if row[best] > 0 else None
        pick[d] = cur
    return pick


def vol_gated_weights(close, threshold, sma_days=200, vol_days=20):
    """P1: returns (w_lev, w_1x): above SMA and vol < threshold -> leveraged; above SMA and
    vol >= threshold -> 1x; otherwise cash. NaN vol/SMA during warm-up -> cash."""
    s = sma(close, sma_days)
    v = realized_vol(close, vol_days)
    up = (close > s) & s.notna() & v.notna()
    w_lev = (up & (v < threshold)).astype(float)
    w_1x = (up & (v >= threshold)).astype(float)
    return w_lev, w_1x


def multi_trend_weights(closes, months):
    """P2: at each month-end, 0.25 in each asset whose month-end close is above the mean of its
    last `months` month-end closes (including the current one), else 0. Held until the next
    month-end; rebalanced to 25% slices at every month-end."""
    idx = closes.index
    me = month_end_flags(idx)
    mec = closes[me.values]
    above = (mec > mec.rolling(months, min_periods=months).mean()).astype(float) * 0.25
    w = above.reindex(idx).ffill().fillna(0.0)
    return w, me


# ---------------------------------------------------------------- the registry

@dataclass
class Variant:
    test_id: str
    strategy: str
    signal_instrument: str
    trade_instrument: str
    params: str
    targets: pd.DataFrame
    rebalance: object = None


def build_variants(closes):
    """All 92 frozen trials, in the order pre-registered as V001-V092.

    closes: DataFrame of adjusted closes of GLD, SPY, QQQ, TLT on the trading calendar.
    Returns a list of Variant whose targets cover all 8 ETFs (zeros elsewhere).
    """
    idx = closes.index
    cols = UNLEV + [LEV[t] for t in UNLEV]
    out = []

    def frame(**w):
        f = pd.DataFrame(0.0, index=idx, columns=cols)
        for k, v in w.items():
            f[k] = v
        return f

    def add(strategy, sig, trade, params, targets, rebalance=None):
        out.append(Variant("V%03d" % (len(out) + 1), strategy, sig, trade, params, targets, rebalance))

    for n in (50, 100, 200):
        for s in UNLEV:
            sig = trend_signal(closes[s], n)
            for t in (s, LEV[s]):
                add("S2_trend_ma", s, t, "N=%d" % n, frame(**{t: sig}))
    for m in (3, 6, 12):
        for s in UNLEV:
            sig = tsmom_signal(closes[s], m)
            for t in (s, LEV[s]):
                add("S3_tsmom", s, t, "lookback_months=%d" % m, frame(**{t: sig}))
    for x in (5, 10, 15):
        for s in ("SPY", "QQQ"):
            sig = rsi2_signal(closes[s], x)
            for t in (s, LEV[s]):
                add("S4_rsi2", s, t, "entry_rsi<%d;exit_close>sma5" % x, frame(**{t: sig}))
    for lev, name, trade in ((False, "S5_rotation", "winner_1x"), (True, "S6_leveraged_rotation", "winner_leveraged")):
        for m in (3, 6, 12):
            pick = rotation_choice(closes[UNLEV], m)
            f = frame()
            for s in UNLEV:
                f[LEV[s] if lev else s] = (pick == s).astype(float)
            add(name, "GLD|SPY|QQQ|TLT", trade, "lookback_months=%d;monthly;cash_if_all_negative" % m, f)
    for v in (15, 20, 25):
        for s in ("SPY", "QQQ"):
            wl, w1 = vol_gated_weights(closes[s], v / 100.0)
            add("P1_vol_gated_leverage", s, "%s|%s|cash" % (LEV[s], s),
                "sma=200;vol_window=20;vol_threshold=%d%%" % v, frame(**{LEV[s]: wl, s: w1}))
    for m in (6, 8, 10, 12):
        w, me = multi_trend_weights(closes[UNLEV], m)
        add("P2_multi_asset_trend", "GLD|SPY|QQQ|TLT", "GLD|SPY|QQQ|TLT",
            "sma_months=%d;25%%_each;monthly" % m, frame(**{s: w[s] for s in UNLEV}), me)
        add("P2_multi_asset_trend", "GLD|SPY|QQQ|TLT", "UGL|UPRO|TQQQ|TMF",
            "sma_months=%d;25%%_each;monthly" % m, frame(**{LEV[s]: w[s] for s in UNLEV}), me)
    for x in (5, 10, 15):
        for s in ("SPY", "QQQ"):
            sig = rsi2_signal(closes[s], x, trend_filter_days=200)
            for t in (s, LEV[s]):
                add("P3_rsi2_trend_filter", s, t, "entry_rsi<%d;close>sma200;exit_close>sma5" % x, frame(**{t: sig}))
    return out
