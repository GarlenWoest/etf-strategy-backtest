"""Commodity study (Phase 9+): clean data, FRED release lags, signals and the frozen trial list V093-V118.

Universe (user decision 2026-10-22): gold GLD, silver SLV, oil USO; 2x versions UGL, AGQ, UCO.
Copper dropped. Benchmarks (not trials): buy-and-hold of each, SPY, equal weight GLD/SLV/USO
monthly, and 70/30 SPY/GLD monthly.

Conventions are the ETF study's (src/strategies.py): signals from the unleveraged ETF's adjusted
close; row t uses data known at the close of t; the engine fills at the open of t+1; before a
lookback is filled the target is 0 (cash).

FRED release lags (conservative, documented in config.yaml commodity_study.fred):
  DFII10 (H.15, posted 4:15 pm ET each business day with the prior business day's rates): a value
    dated d is first used on the 2nd trading day after d.
  DTWEXBGS (H.10, posted weekly on Monday for the week ending the prior Friday): a value dated d is
    first used on the first trading day on or after (Friday of d's week) + 5 calendar days (Wednesday),
    which also covers a Monday-holiday release on Tuesday.
FRED values are the current vintage; revisions are not modelled (no free vintage access without a key).
"""
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src import PROJECT_ROOT, load_config
from src import data as D
from src.strategies import TRADING_DAYS_PER_MONTH, Variant, month_end_flags

OHLC = D.OHLC
UNLEV = ["GLD", "SLV", "USO"]
LEV = {"GLD": "UGL", "SLV": "AGQ", "USO": "UCO"}
OIL = {"USO", "UCO"}
USO_FLAG = "USO structure change Apr-2020 (front-month -> multi-month futures; 1:8 reverse split 2020-04-29)"
RAW = PROJECT_ROOT / "data" / "raw" / "commodities"
CLEAN = PROJECT_ROOT / "data" / "clean" / "commodities"


def study_cfg(cfg=None):
    """Config for the commodity study: the main config with AGQ/UCO added to the leveraged set
    (so they pay the leveraged half-spread) and the study's own evaluation start."""
    import copy
    cfg = copy.deepcopy(cfg or load_config())
    cs = cfg["commodity_study"]
    for t, spec in cs["leveraged"].items():
        cfg["instruments"]["leveraged"][t] = spec
    cfg["dates"]["evaluation_start"] = cs["evaluation_start"]
    return cfg


# ---------------------------------------------------------------- clean data

def _raw(t, kind="yahoo_adj"):
    return pd.read_csv(RAW / kind / ("%s.csv" % t.replace("^", "").replace("=", "_")), index_col="Date",
                       parse_dates=["Date"]).sort_index()


def build_clean(cfg=None):
    """data/clean/commodities/<T>.csv for SLV, USO (real) and AGQ, UCO (synthetic before launch,
    calibrated on in-sample overlap only, exactly as Phase 2). GLD, UGL, SPY and the cash rate are
    the Phase 2 clean files, reused unchanged."""
    cfg = cfg or load_config()
    cs = cfg["commodity_study"]
    CLEAN.mkdir(parents=True, exist_ok=True)
    cash = D.load_cash(cfg)
    start = pd.Timestamp(cs["calendar_start"])
    cal = cash.index[cash.index >= start]
    rep = {"built_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "calendar": [str(cal[0].date()), str(cal[-1].date()), int(len(cal))], "extra_drag": {}, "tracking": {},
           "tracking_2019_2023": {}, "tracking_uncalibrated": {}, "real_start": {}, "files": {}}
    for t in ("SLV", "USO"):
        df = _raw(t).reindex(cal)
        if df[OHLC].isna().any().any():
            raise RuntimeError("%s has missing days on the study calendar; refusing to fill" % t)
        df[OHLC].assign(source="real").to_csv(CLEAN / ("%s.csv" % t))
    for t, spec in cs["leveraged"].items():
        under = pd.read_csv(CLEAN / ("%s.csv" % spec["underlying"]), index_col="Date", parse_dates=["Date"])
        real = _raw(t)
        real = real[real.index.isin(cal)]
        raw_syn = D.synthetic_ohlc(under, cash, spec["leverage"], spec["expense_ratio"])
        drag, n = D.calibrate_extra_drag(real["Close"], raw_syn["Close"], cfg["dates"]["in_sample_end"])
        syn = D.synthetic_ohlc(under, cash, spec["leverage"], spec["expense_ratio"], extra_drag=drag)
        rep["extra_drag"][t] = {"annual": drag, "calibration_days": n, "calibration_end": cfg["dates"]["in_sample_end"]}
        rep["tracking_uncalibrated"][t] = D.tracking_stats(real["Close"], raw_syn["Close"])
        rep["tracking"][t] = D.tracking_stats(real["Close"], syn["Close"])
        rep["tracking_2019_2023"][t] = D.tracking_stats(real.loc[cfg["dates"]["validation_start"]:, "Close"], syn["Close"])
        rep["real_start"][t] = str(real.index[0].date())
        joined = D.splice(real.reindex(cal[cal >= real.index[0]]), syn)
        if joined[OHLC].isna().any().any():
            raise RuntimeError("%s has missing days after splice; refusing to fill" % t)
        joined.to_csv(CLEAN / ("%s.csv" % t))
    for p in sorted(CLEAN.glob("*.csv")):
        rep["files"][p.name] = D.sha256(p)
    with open(CLEAN / "build_meta.json", "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)
    return rep


def load_prices(cfg=None, end=None):
    """{ticker: OHLC} on the study calendar for every instrument the study can trade, plus SPY."""
    cfg = cfg or load_config()
    end = end or cfg["dates"]["validation_end"]
    start = pd.Timestamp(cfg["commodity_study"]["calendar_start"])
    px = {}
    for t in ("GLD", "UGL", "SPY"):
        px[t] = D.load_clean(t, cfg)
    for t in ("SLV", "USO", "AGQ", "UCO"):
        px[t] = pd.read_csv(CLEAN / ("%s.csv" % t), index_col="Date", parse_dates=["Date"])
    px = {t: p.loc[start:end] for t, p in px.items()}
    assert max(p.index.max() for p in px.values()) < pd.Timestamp(cfg["dates"]["holdout_start"])
    return px


def load_fred(sid):
    df = pd.read_csv(RAW / "fred" / ("%s.csv" % sid), index_col="Date", parse_dates=["Date"])
    return df[sid].dropna()


# ---------------------------------------------------------------- release lags

def available_on(obs_dates, calendar, rule):
    """Trading day on which each observation is first usable (row t of the signal)."""
    cal = pd.DatetimeIndex(calendar)
    if rule == "h15_daily":                     # 2nd trading day after d
        pos = cal.searchsorted(obs_dates, side="right") + 1
    elif rule == "h10_weekly":                  # first trading day >= Friday of d's week + 5 days
        fri = obs_dates + pd.to_timedelta(4 - obs_dates.weekday, unit="D")
        pos = cal.searchsorted(fri + pd.Timedelta(days=5), side="left")
    else:
        raise ValueError(rule)
    out = pd.Series(pd.NaT, index=obs_dates)
    ok = pos < len(cal)
    out[ok] = cal[pos[ok]]
    return out


def as_of(obs_signal, calendar, rule):
    """Map a signal computed on observation dates to the trading calendar using release lags:
    value at day t = latest observation whose release-adjusted date is <= t (NaN before any)."""
    s = obs_signal.dropna()
    avail = available_on(s.index, calendar, rule)
    t = pd.Series(s.to_numpy(), index=avail.to_numpy())
    t = t[~t.index.isna()]
    t = t[~t.index.duplicated(keep="last")]           # several obs released the same day: keep the latest
    return t.reindex(pd.DatetimeIndex(calendar)).ffill()


# ---------------------------------------------------------------- helpers

def tbill_index(cash, index):
    """Growth of $1 in T-bills, engine convention: day i earns the rate of day i-1."""
    r = cash.reindex(index).shift(1).fillna(0.0)
    return (1 + r).cumprod()


def excess_lookback(closes, cash, k):
    """k-trading-day total return minus the T-bill return over the same k days."""
    tb = tbill_index(cash, closes.index)
    ret = closes / closes.shift(k) - 1
    tbr = tb / tb.shift(k) - 1
    return ret.sub(tbr, axis=0)


def week_end_flags(index):
    wk = index.to_period("W-FRI")                      # weeks end on Friday; last trading day of each week
    return pd.Series(np.r_[wk[1:] != wk[:-1], False], index=index)


# ---------------------------------------------------------------- signals (I01, I03, I04, I05, I06)

def i01_tsmom_basket(closes, cash, months):
    """Month-end: 1/3 in each of GLD/SLV/USO whose 21*months-day return beats T-bills; else that third
    in cash. Held to the next month-end; rebalanced to thirds at every month-end."""
    me = month_end_flags(closes.index)
    ex = excess_lookback(closes, cash, months * TRADING_DAYS_PER_MONTH)
    w = (ex > 0).astype(float) / len(closes.columns)
    w.loc[~me.to_numpy()] = np.nan
    w = w.ffill().fillna(0.0)
    return w, me


def i04_dual_momentum(closes, cash, months):
    """Month-end: the one of GLD/SLV/USO with the highest 21*months-day return; held only if that return
    beats T-bills over the same days, else cash. Any missing lookback -> cash."""
    me = month_end_flags(closes.index)
    k = months * TRADING_DAYS_PER_MONTH
    ret = closes / closes.shift(k) - 1
    ex = excess_lookback(closes, cash, k)
    w = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for d in closes.index[me.values]:
        row = ret.loc[d]
        w.loc[d] = 0.0
        if row.isna().any():
            continue
        best = row.idxmax()
        if ex.at[d, best] > 0:
            w.at[d, best] = 1.0
    return w.ffill().fillna(0.0)


EWMAC_SCALAR = 3.75                                    # Carver (Systematic Trading) published forecast scalar for EWMAC(16, 64)


def ewmac_forecast(close):
    """Carver EWMAC(16,64): (EWMA16 - EWMA64) / (close x 64-day std of daily returns), x 3.75 / 10,
    clipped to [-2, 2]. NaN until 64 returns are available."""
    f = close.ewm(span=16, adjust=False).mean() - close.ewm(span=64, adjust=False).mean()
    sd = close.pct_change().rolling(64, min_periods=64).std()
    raw = f / (close * sd)
    return (raw * EWMAC_SCALAR / 10.0).clip(-2, 2)


def i03_vol_scaled(closes, target_vol, band=0.10):
    """Weekly (last trading day of each week): per instrument with budget b = 1/len(closes.columns),
    desired = b * min(1, max(f, 0) / 2 * target_vol / rv60), f = ewmac_forecast, rv60 = 60-day realized
    vol. The held target changes only if |desired - held| >= band * b, or desired is 0 (exit)."""
    b = 1.0 / len(closes.columns)
    wk = week_end_flags(closes.index).to_numpy()
    out = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    for t in closes.columns:
        f = ewmac_forecast(closes[t])
        rv = closes[t].pct_change().rolling(60, min_periods=60).std() * np.sqrt(252)
        desired = (b * np.minimum(1.0, f.clip(lower=0) / 2 * target_vol / rv)).to_numpy()
        held, col = 0.0, np.zeros(len(closes))
        for i in range(len(closes)):
            if wk[i]:
                d = desired[i]
                d = 0.0 if np.isnan(d) else d
                if d == 0.0 or abs(d - held) >= band * b:
                    held = d
            col[i] = held
        out[t] = col
    return out


def i05_real_yield(calendar, slow):
    """1 when the 20-observation mean of DFII10 is below its `slow`-observation mean (real yields
    falling), using only values released by each day (h15 lag); else 0."""
    y = load_fred("DFII10")
    sig = (y.rolling(20, min_periods=20).mean() < y.rolling(slow, min_periods=slow).mean()).astype(float)
    sig[y.rolling(slow, min_periods=slow).mean().isna()] = np.nan
    return as_of(sig, calendar, "h15_daily").fillna(0.0)


def i06_dollar(calendar, n):
    """1 when the broad dollar index (DTWEXBGS) is below its n-observation SMA, using only values
    released by each day (h10 weekly lag); else 0."""
    x = load_fred("DTWEXBGS")
    s = x.rolling(n, min_periods=n).mean()
    sig = (x < s).astype(float)
    sig[s.isna()] = np.nan
    return as_of(sig, calendar, "h10_weekly").fillna(0.0)


# ---------------------------------------------------------------- registry

COLS = UNLEV + [LEV[t] for t in UNLEV] + ["SPY"]


def build_variants(closes, cash):
    """The 26 frozen commodity trials V093-V118 in registry (= grid) order. closes: GLD/SLV/USO."""
    idx = closes.index
    out = []

    def frame(w):
        f = pd.DataFrame(0.0, index=idx, columns=COLS)
        for k, v in w.items():
            f[k] = v
        return f

    def add(strategy, sig, trade, params, w, rebalance=None):
        out.append(Variant("V%03d" % (93 + len(out)), strategy, sig, trade, params, frame(w), rebalance))

    basket = "GLD|SLV|USO"
    for m in (3, 6, 12):
        w, me = i01_tsmom_basket(closes[UNLEV], cash, m)
        add("I01_tsmom_basket", basket, basket, "lookback_months=%d;thirds;monthly;vs_tbill" % m,
            {t: w[t] for t in UNLEV}, me)
        add("I01_tsmom_basket", basket, "UGL|AGQ|UCO", "lookback_months=%d;thirds;monthly;vs_tbill" % m,
            {LEV[t]: w[t] for t in UNLEV}, me)
    for scope in ("gold", "basket"):
        cols = ["GLD"] if scope == "gold" else UNLEV
        for tv in (15, 20, 25):
            w = i03_vol_scaled(closes[cols], tv / 100.0)
            add("I03_vol_scaled_trend", "|".join(cols), "|".join(cols),
                "target_vol=%d%%;ewmac16_64;weekly;band10%%" % tv, {t: w[t] for t in cols})
    for m in (3, 6, 12):
        w = i04_dual_momentum(closes[UNLEV], cash, m)
        add("I04_dual_momentum", basket, "winner_1x", "lookback_months=%d;monthly;vs_tbill" % m,
            {t: w[t] for t in UNLEV})
        add("I04_dual_momentum", basket, "winner_leveraged", "lookback_months=%d;monthly;vs_tbill" % m,
            {LEV[t]: w[t] for t in UNLEV})
    for slow in (120, 250):
        s = i05_real_yield(idx, slow)
        for t in ("GLD", "UGL"):
            add("I05_real_yield", "DFII10", t, "fast=20;slow=%d;h15_lag" % slow, {t: s})
    for n in (100, 200):
        s = i06_dollar(idx, n)
        for t in ("GLD", "UGL"):
            add("I06_dollar_trend", "DTWEXBGS", t, "sma=%d;h10_lag" % n, {t: s})
    # registry order above puts 1x and leveraged of the same lookback next to each other; grid
    # neighbours for K5 are taken within (strategy, signal, trade), so order inside a group = grid order
    return out


def benchmarks(index):
    from src.strategies import buy_and_hold, equal_weight
    bench = []
    for i, t in enumerate(UNLEV + [LEV[t] for t in UNLEV] + ["SPY"]):
        bench.append(Variant("CB%02d" % (i + 1), "buy_and_hold", t, t, "",
                             buy_and_hold(index, t).reindex(columns=COLS, fill_value=0.0)))
    w, flag = equal_weight(index, UNLEV)
    bench.append(Variant("CB08", "equal_weight", "GLD|SLV|USO", "GLD|SLV|USO", "monthly",
                         w.reindex(columns=COLS, fill_value=0.0), flag))
    mix = pd.DataFrame(0.0, index=index, columns=COLS)
    mix["SPY"], mix["GLD"] = 0.7, 0.3
    bench.append(Variant("CB09", "mix_70_30", "SPY|GLD", "SPY|GLD", "70/30;monthly", mix, flag))
    return bench


def uses_oil(v):
    return any(t in v.trade_instrument or t in v.signal_instrument for t in ("USO", "UCO")) or \
        v.trade_instrument.startswith("winner")
