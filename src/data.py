"""Data: download, cache, validate, synthetic leveraged series, T-bill cash rate.

Raw downloads are written once to data/raw and never edited. Everything derived
goes to data/clean. Nothing here fills missing prices with guesses: gaps are
reported, and the only forward fill is the T-bill rate across days when the
ETF market traded but the T-bill series did not (bond-market holidays).

The holdout period (config dates.holdout_start onward) is never downloaded
while dates.holdout_locked is true.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src import PROJECT_ROOT, load_config

OHLC = ["Open", "High", "Low", "Close"]


# ---------------------------------------------------------------- paths

def raw_dir(cfg=None):
    cfg = cfg or load_config()
    return PROJECT_ROOT / cfg["data"]["raw_dir"]


def clean_dir(cfg=None):
    cfg = cfg or load_config()
    return PROJECT_ROOT / cfg["data"]["clean_dir"]


def download_end(cfg):
    """Exclusive end date for downloads. The holdout stays unseen while locked."""
    if cfg["dates"]["holdout_locked"]:
        return cfg["dates"]["holdout_start"]
    return None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- download (network)

def _flatten(df, ticker):
    if isinstance(df.columns, pd.MultiIndex):
        df = df.xs(ticker, axis=1, level=1)
    df = df.copy()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df.index.name = "Date"
    return df


def download_all(cfg=None, start="2004-01-01"):
    """Download adjusted and unadjusted daily OHLC for every instrument plus ^IRX.

    Writes data/raw/yahoo_adj/<T>.csv (auto_adjust=True: open, high, low, close all
    adjusted for splits and dividends), data/raw/yahoo_unadj/<T>.csv (raw prices,
    Adj Close, Dividends, Stock Splits; kept for cross-checks only) and
    data/raw/download_meta.json. Raises on any empty download instead of continuing.
    """
    import yfinance as yf

    cfg = cfg or load_config()
    end = download_end(cfg)
    tickers = cfg["instruments"]["unleveraged"] + list(cfg["instruments"]["leveraged"])
    cash = cfg["instruments"]["cash_rate"]["ticker"]
    out = raw_dir(cfg)
    (out / "yahoo_adj").mkdir(parents=True, exist_ok=True)
    (out / "yahoo_unadj").mkdir(parents=True, exist_ok=True)
    meta = {"downloaded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "Yahoo Finance via yfinance", "yfinance_version": yf.__version__,
            "start": start, "end_exclusive": end, "files": {}}
    for t in tickers + [cash]:
        for kind, adj in (("yahoo_adj", True), ("yahoo_unadj", False)):
            if t == cash and kind == "yahoo_unadj":
                continue
            df = yf.download(t, start=start, end=end, auto_adjust=adj, actions=not adj,
                             progress=False, threads=False)
            if df is None or df.empty:
                raise RuntimeError("download failed or empty: %s (%s)" % (t, kind))
            df = _flatten(df, t)
            path = out / kind / ("%s.csv" % t.replace("^", ""))
            df.to_csv(path)
            meta["files"]["%s/%s" % (kind, path.name)] = {
                "ticker": t, "rows": len(df), "first": str(df.index[0].date()),
                "last": str(df.index[-1].date()), "sha256": sha256(path)}
    with open(out / "download_meta.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    return meta


# ---------------------------------------------------------------- loading

def load_raw(ticker, kind="yahoo_adj", cfg=None):
    path = raw_dir(cfg) / kind / ("%s.csv" % ticker.replace("^", ""))
    df = pd.read_csv(path, index_col="Date", parse_dates=["Date"])
    return df.sort_index()


# ---------------------------------------------------------------- validation

def validate_prices(df, ticker, calendar=None, gap_flag=0.10, stale_days=3):
    """Return a list of issue dicts. Never modifies the data.

    Checks: duplicate dates, NaN prices, zero or negative prices, OHLC
    inconsistency (low above open/close or high below them), missing trading
    days versus `calendar`, single-day moves larger than gap_flag (close-to-close
    and prior close to open), and runs of identical closes of `stale_days` or more.
    """
    issues = []

    def add(kind, dates, detail=""):
        dates = [str(pd.Timestamp(d).date()) for d in dates]
        if dates:
            issues.append({"ticker": ticker, "check": kind, "count": len(dates),
                           "dates": dates, "detail": detail})

    add("duplicate_date", df.index[df.index.duplicated()])
    d = df[~df.index.duplicated()]
    add("nan_price", d.index[d[OHLC].isna().any(axis=1)])
    add("non_positive_price", d.index[(d[OHLC] <= 0).any(axis=1)])
    tol = 1e-6
    bad = (d["Low"] > d[["Open", "Close"]].min(axis=1) * (1 + tol)) | \
          (d["High"] < d[["Open", "Close"]].max(axis=1) * (1 - tol)) | (d["Low"] > d["High"])
    add("ohlc_inconsistent", d.index[bad])
    if calendar is not None:
        cal = calendar[calendar >= d.index[0]]      # a fund may start late, but must not end early
        add("missing_trading_day", cal.difference(d.index))
        add("extra_day_not_in_calendar", d.index.difference(calendar))
    cc = d["Close"].pct_change()
    add("gap_close_to_close", d.index[cc.abs() > gap_flag], "flag only, kept (>%.0f%%)" % (gap_flag * 100))
    oc = d["Open"] / d["Close"].shift(1) - 1
    add("gap_prev_close_to_open", d.index[oc.abs() > gap_flag], "flag only, kept (>%.0f%%)" % (gap_flag * 100))
    same = d["Close"].diff().eq(0)
    run = same.groupby((~same).cumsum()).cumsum()
    add("stale_close_run", d.index[run >= stale_days - 1], "close unchanged for %d+ days" % stale_days)
    return issues


# ---------------------------------------------------------------- cash rate

def daily_cash_rate(irx, calendar):
    """Daily T-bill rate aligned to `calendar` (the ETF trading days).

    rate = (IRX / 100) / 252. IRX values on days the ETF market was closed are
    dropped. On ETF trading days with no IRX print (bond-market holidays such as
    Columbus Day and Veterans Day) the previous value is carried forward; the
    returned dict reports every forward-filled date so it can be audited.
    """
    s = irx["Close"].reindex(calendar)
    filled = s.index[s.isna()]
    first_valid = s.first_valid_index()
    s = s.ffill()
    rate = (s / 100.0) / 252.0
    return rate, {"forward_filled_dates": [str(x.date()) for x in filled if x > first_valid],
                  "leading_missing": [str(x.date()) for x in filled if x < first_valid]}


# ---------------------------------------------------------------- synthetic leveraged series

def synthetic_returns(under_close, cash_daily, leverage, expense_ratio, extra_drag=0.0):
    """Daily close-to-close return of a daily-reset leveraged fund.

    r = L * r_underlying - expense_ratio / 252 - (L - 1) * daily_cash_rate - extra_drag / 252
    The cash rate is the prior-day T-bill rate (financing is set at the close
    when the fund resets), so no future information is used. extra_drag is the
    per-fund annual shortfall of the real fund versus the formula, calibrated on
    in-sample overlap only (calibrate_extra_drag).
    """
    r_u = under_close.pct_change()
    fin = cash_daily.shift(1).reindex(r_u.index)
    return leverage * r_u - expense_ratio / 252.0 - (leverage - 1) * fin - extra_drag / 252.0


def synthetic_ohlc(under, cash_daily, leverage, expense_ratio, anchor_close=1.0, extra_drag=0.0):
    """Synthetic OHLC for a leveraged fund built from the underlying's adjusted OHLC.

    Close: chained synthetic close-to-close returns (synthetic_returns).
    Open/High/Low: the fund holds L x exposure from the prior close, so an
    intraday price P_und maps to C_prev * (1 + L * (P_und / C_und_prev - 1)).
    Financing and fees accrue at the close only. Levels start at anchor_close.
    """
    r = synthetic_returns(under["Close"], cash_daily, leverage, expense_ratio, extra_drag)
    close = anchor_close * (1 + r.fillna(0)).cumprod()
    prev_c = close.shift(1)
    prev_u = under["Close"].shift(1)
    out = pd.DataFrame(index=under.index)
    for col in ("Open", "High", "Low"):
        out[col] = prev_c * (1 + leverage * (under[col] / prev_u - 1))
    out["Close"] = close
    out.iloc[0, out.columns.get_loc("Open")] = close.iloc[0]
    out.iloc[0, out.columns.get_loc("High")] = close.iloc[0]
    out.iloc[0, out.columns.get_loc("Low")] = close.iloc[0]
    hi = out[["Open", "High", "Low", "Close"]].max(axis=1)
    lo = out[["Open", "High", "Low", "Close"]].min(axis=1)
    out["High"], out["Low"] = hi, lo
    return out[OHLC]


def calibrate_extra_drag(real_close, synthetic_close, end):
    """Annual extra cost = mean daily (synthetic - real) return x 252, on dates up to `end`.

    Only the overlap through `end` (the in-sample end) is used, so validation and
    holdout data never influence the synthetic history.
    """
    a = real_close.loc[:end].pct_change()
    b = synthetic_close.reindex(real_close.index).loc[:end].pct_change()
    j = pd.concat([a, b], axis=1, keys=["real", "syn"]).dropna()
    return float((j["syn"] - j["real"]).mean() * 252), int(len(j))


def splice(real, synthetic):
    """Synthetic history before the real fund's first date, real data from then on.

    Synthetic levels are rescaled so the synthetic close on the real first date
    equals the real close: the joined series has no jump at the seam. Returns the
    joined frame and a 'source' column ('synthetic' or 'real').
    """
    d0 = real.index[0]
    syn = synthetic.loc[:d0, OHLC]
    scale = real.loc[d0, "Close"] / syn.loc[d0, "Close"]
    syn = syn.iloc[:-1] * scale
    syn = syn.assign(source="synthetic")
    rl = real[OHLC].assign(source="real")
    return pd.concat([syn, rl])


def tracking_stats(real_close, synthetic_close):
    """Overlap statistics of daily close-to-close returns (real vs synthetic)."""
    a = real_close.pct_change()
    b = synthetic_close.reindex(real_close.index).pct_change()
    j = pd.concat([a, b], axis=1, keys=["real", "syn"]).dropna()
    diff = j["real"] - j["syn"]
    years = len(j) / 252.0
    cum_real = float((1 + j["real"]).prod() - 1)
    cum_syn = float((1 + j["syn"]).prod() - 1)
    return {"days": int(len(j)), "start": str(j.index[0].date()), "end": str(j.index[-1].date()),
            "correlation": float(j["real"].corr(j["syn"])),
            "tracking_error_ann": float(diff.std() * np.sqrt(252)),
            "mean_diff_ann": float(diff.mean() * 252),
            "cagr_real": float((1 + cum_real) ** (1 / years) - 1),
            "cagr_syn": float((1 + cum_syn) ** (1 / years) - 1),
            "max_abs_daily_diff": float(diff.abs().max()),
            "max_abs_daily_diff_date": str(diff.abs().idxmax().date())}


# ---------------------------------------------------------------- build clean data

def build_clean(cfg=None):
    """Validate raw data and write data/clean. Returns a report dict.

    data/clean/prices/<T>.csv  adjusted OHLC from dates.common_start (leveraged
                               funds: synthetic before inception, real after;
                               'source' column says which)
    data/clean/cash_rate.csv   daily T-bill rate on ETF trading days
    data/clean/build_meta.json validation issues, tracking stats, file hashes
    """
    cfg = cfg or load_config()
    start = pd.Timestamp(cfg["dates"]["common_start"])
    out = clean_dir(cfg)
    (out / "prices").mkdir(parents=True, exist_ok=True)
    spy = load_raw("SPY", cfg=cfg)
    cal = spy.index[spy.index >= start]
    gap = cfg["data"]["gap_flag"]
    report = {"built_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "calendar": {"source": "SPY trading days", "first": str(cal[0].date()),
                           "last": str(cal[-1].date()), "days": int(len(cal))},
              "issues": [], "tracking": {}, "leveraged_real_start": {}, "files": {}}

    irx = load_raw("^IRX", cfg=cfg)
    cash, info = daily_cash_rate(irx, cal)
    if info["leading_missing"]:
        raise RuntimeError("T-bill series starts after the calendar: %s" % info["leading_missing"][:3])
    report["cash_rate"] = {"forward_filled_dates": info["forward_filled_dates"],
                           "negative_rate_dates": [str(d.date()) for d in irx.index[irx["Close"] < 0]]}
    cash.rename("daily_rate").to_frame().to_csv(out / "cash_rate.csv", index_label="Date")

    for t in cfg["instruments"]["unleveraged"]:
        df = load_raw(t, cfg=cfg)
        df = df[df.index >= start]
        report["issues"] += validate_prices(df, t, cal, gap)
        df = df.reindex(cal)
        if df[OHLC].isna().any().any():
            raise RuntimeError("%s has missing days after validation; refusing to fill" % t)
        df[OHLC].assign(source="real").to_csv(out / "prices" / ("%s.csv" % t))

    for t, spec in cfg["instruments"]["leveraged"].items():
        if spec["expense_ratio"] is None:
            raise RuntimeError("no confirmed expense ratio for %s" % t)
        under = pd.read_csv(out / "prices" / ("%s.csv" % spec["underlying"]), index_col="Date",
                            parse_dates=["Date"])
        real = load_raw(t, cfg=cfg)
        report["issues"] += validate_prices(real, t, cal, gap)
        raw_syn = synthetic_ohlc(under, cash, spec["leverage"], spec["expense_ratio"])
        drag, n_days = calibrate_extra_drag(real["Close"], raw_syn["Close"], cfg["dates"]["in_sample_end"])
        syn = synthetic_ohlc(under, cash, spec["leverage"], spec["expense_ratio"], extra_drag=drag)
        report["leveraged_real_start"][t] = str(real.index[0].date())
        report.setdefault("extra_drag", {})[t] = {"annual": drag, "calibration_days": n_days,
                                                  "calibration_end": cfg["dates"]["in_sample_end"]}
        report.setdefault("tracking_uncalibrated", {})[t] = tracking_stats(real["Close"], raw_syn["Close"])
        report["tracking"][t] = tracking_stats(real["Close"], syn["Close"])
        oos = real.loc[cfg["dates"]["validation_start"]:]
        report.setdefault("tracking_2019_2023", {})[t] = tracking_stats(oos["Close"], syn["Close"])
        ov_real = (real["Open"] / real["Close"].shift(1) - 1)
        ov_syn = (syn["Open"] / syn["Close"].shift(1) - 1).reindex(real.index)
        j = pd.concat([ov_real, ov_syn], axis=1).dropna()
        report["tracking"][t]["overnight_corr"] = float(j.iloc[:, 0].corr(j.iloc[:, 1]))
        report["tracking"][t]["overnight_te_ann"] = float((j.iloc[:, 0] - j.iloc[:, 1]).std() * np.sqrt(252))
        joined = splice(real.reindex(cal[cal >= real.index[0]]), syn)
        if joined[OHLC].isna().any().any():
            raise RuntimeError("%s has missing days after splice; refusing to fill" % t)
        joined.to_csv(out / "prices" / ("%s.csv" % t))

    for p in sorted(out.rglob("*.csv")):
        report["files"][str(p.relative_to(PROJECT_ROOT))] = sha256(p)
    with open(out / "build_meta.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    return report


def load_clean(ticker, cfg=None):
    path = clean_dir(cfg) / "prices" / ("%s.csv" % ticker)
    return pd.read_csv(path, index_col="Date", parse_dates=["Date"])


def load_cash(cfg=None):
    return pd.read_csv(clean_dir(cfg) / "cash_rate.csv", index_col="Date", parse_dates=["Date"])["daily_rate"]


# ---------------------------------------------------------------- second-source cross-check

def load_stooq(folder, cfg=None):
    """{TICKER: DataFrame} from truncated Stooq daily CSVs (folder/pre2024/*.csv).

    Refuses any file holding a date on or after the holdout start.
    """
    cfg = cfg or load_config()
    cutoff = pd.Timestamp(cfg["dates"]["holdout_start"])
    wanted = cfg["instruments"]["unleveraged"] + list(cfg["instruments"]["leveraged"])
    out = {}
    for p in sorted(Path(folder, "pre2024").glob("*.csv")):
        stem = p.stem.lower().replace(".", "_")
        t = next((w for w in wanted if stem == w.lower() or stem.startswith(w.lower() + "_")), None)
        if t is None:
            continue
        df = pd.read_csv(p)
        col = next(c for c in df.columns if c.strip().lower() in ("date", "data"))
        df.index = pd.to_datetime(df.pop(col).astype(str))
        df.index.name = "Date"
        df.columns = [c.strip().capitalize() for c in df.columns]
        if df.index.max() >= cutoff:
            raise RuntimeError("%s contains holdout dates; run tools/truncate_holdout.py" % p.name)
        out[t] = df.sort_index()
    return out


def crosscheck(stooq, cfg=None, tol=None):
    """Compare Stooq closes with Yahoo closes (adjusted and unadjusted) on common dates.

    Returns per ticker: overlap, median level ratio vs each Yahoo series, the basis
    that matches (smaller median absolute deviation from 1), and every date where
    the matching closes differ by more than tol (default config 0.5%).
    """
    cfg = cfg or load_config()
    tol = cfg["data"]["crosscheck_mismatch_flag"] if tol is None else tol
    res = {}
    for t, s in stooq.items():
        y = {"adjusted": load_raw(t, cfg=cfg)["Close"], "unadjusted": load_raw(t, "yahoo_unadj", cfg=cfg)["Close"]}
        r = {}
        for basis, yc in y.items():
            j = pd.concat([s["Close"], yc], axis=1, keys=["stooq", "yahoo"]).dropna()
            dev = j["stooq"] / j["yahoo"] - 1
            r[basis] = {"days": int(len(j)), "median_abs_dev": float(dev.abs().median()),
                        "mismatch_dates": [str(d.date()) for d in dev.index[dev.abs() > tol]],
                        "max_abs_dev": float(dev.abs().max()),
                        "max_abs_dev_date": str(dev.abs().idxmax().date())}
        best = min(r, key=lambda b: r[b]["median_abs_dev"])
        only_y = y["adjusted"].index.difference(s.index)
        only_s = s.index.difference(y["adjusted"].index)
        res[t] = {"basis": best, "compare": r, "stooq_first": str(s.index[0].date()),
                  "stooq_last": str(s.index[-1].date()),
                  "dates_only_in_yahoo": len(only_y[only_y >= s.index[0]]),
                  "dates_only_in_stooq": len(only_s[only_s >= y["adjusted"].index[0]])}
    return res


# ---------------------------------------------------------------- suspect-price sensitivity (Phase 5)

def interpolate_suspects(df, start, end):
    """Copy of df with closes in [start, end] replaced by linear interpolation in time
    between the last close before start and the first close after end.

    Only Close is replaced; High/Low are widened if needed so each bar stays consistent.
    Used only for the Phase 5 sensitivity run; the clean data itself is never changed.
    """
    out = df.copy()
    window = (out.index >= pd.Timestamp(start)) & (out.index <= pd.Timestamp(end))
    if not window.any():
        raise ValueError("no rows in %s..%s" % (start, end))
    before = out.index[out.index < pd.Timestamp(start)][-1]
    after = out.index[out.index > pd.Timestamp(end)][0]
    c0, c1 = out.at[before, "Close"], out.at[after, "Close"]
    span = (after - before).days
    for d in out.index[window]:
        out.at[d, "Close"] = c0 + (c1 - c0) * (d - before).days / span
    out.loc[window, "High"] = out.loc[window, ["High", "Close"]].max(axis=1)
    out.loc[window, "Low"] = out.loc[window, ["Low", "Close"]].min(axis=1)
    return out
