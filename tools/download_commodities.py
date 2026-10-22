"""Phase 9c: download and validate daily data for the commodity universe (holdout stays locked).

Writes, without touching the Phase 2 ETF data:
  data/raw/commodities/yahoo_adj/<T>.csv     auto_adjust=True OHLC (Yahoo Finance via yfinance)
  data/raw/commodities/yahoo_unadj/<T>.csv   raw OHLC + actions (cross-check only)
  data/raw/commodities/fred/<ID>.csv         FRED macro series (fredgraph CSV endpoint)
  data/raw/commodities/download_meta.json    rows, first/last date, sha256 per file
  results/commodities_validation.json        every validation issue (read by the report)

Holdout rule: every request ends before dates.holdout_start (exclusive). Any row on or after
that date that a source still returns is dropped before the file is written, without being
read, and the count is recorded. Nothing is filled or interpolated.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src import PROJECT_ROOT, load_config
from src import data as D

cfg = load_config()
assert cfg["dates"]["holdout_locked"], "holdout must stay locked"
END = D.download_end(cfg)                      # "2024-01-01", exclusive
CUT = pd.Timestamp(END)
START = "2000-01-01"

TRADABLE = {          # ticker: description (see research/IDEA_POOL_COMMODITIES.md, feasibility table)
    "GLD": "SPDR Gold Shares (gold, grantor trust)",
    "IAU": "iShares Gold Trust (gold, grantor trust)",
    "GLDM": "SPDR Gold MiniShares (gold, grantor trust)",
    "SLV": "iShares Silver Trust (silver, grantor trust)",
    "USO": "United States Oil Fund (WTI futures pool, K-1)",
    "CPER": "United States Copper Index Fund (copper futures pool, K-1)",
    "UGL": "ProShares Ultra Gold (2x gold, K-1)",
    "AGQ": "ProShares Ultra Silver (2x silver, K-1)",
    "UCO": "ProShares Ultra Bloomberg Crude Oil (2x crude, K-1)",
    "DGP": "DB Gold Double Long ETN (2x gold, ETN)",
    "SPY": "SPDR S&P 500 ETF (benchmark)",
}
SIGNAL = {            # used only as signal inputs, never traded in a $100 account
    "GC=F": "COMEX gold front-month continuous (Yahoo)",
    "SI=F": "COMEX silver front-month continuous (Yahoo)",
    "CL=F": "NYMEX WTI front-month continuous (Yahoo)",
    "HG=F": "COMEX copper front-month continuous (Yahoo)",
    "^GVZ": "Cboe gold ETF volatility index",
    "^OVX": "Cboe crude oil ETF volatility index",
    "^IRX": "13-week T-bill yield (cash rate)",
}
FRED = {
    "DFII10": "10-year TIPS real yield (daily)",
    "T10YIE": "10-year breakeven inflation (daily)",
    "DTWEXBGS": "Nominal broad US dollar index (daily, from 2006)",
    "DTWEXM": "Major-currency US dollar index (daily, discontinued 2019-12-31)",
    "CPIAUCSL": "CPI all items, SA (monthly; released ~2 weeks after month end)",
}

out = PROJECT_ROOT / "data" / "raw" / "commodities"
for sub in ("yahoo_adj", "yahoo_unadj", "fred"):
    (out / sub).mkdir(parents=True, exist_ok=True)


def guard(df, name, meta):
    n = int((df.index >= CUT).sum())
    if n:
        df = df[df.index < CUT]
    meta["holdout_rows_dropped"][name] = n
    return df


def main():
    import yfinance as yf

    meta = {"downloaded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "yahoo": "Yahoo Finance via yfinance %s" % yf.__version__, "fred": "fred.stlouisfed.org fredgraph.csv",
            "start": START, "end_exclusive": END, "files": {}, "holdout_rows_dropped": {}}
    for t in list(TRADABLE) + list(SIGNAL):
        for kind, adj in (("yahoo_adj", True), ("yahoo_unadj", False)):
            if t.startswith("^") and kind == "yahoo_unadj":
                continue
            df = yf.download(t, start=START, end=END, auto_adjust=adj, actions=not adj, progress=False, threads=False)
            if df is None or df.empty:
                raise RuntimeError("download failed or empty: %s (%s)" % (t, kind))
            df = guard(D._flatten(df, t), "%s/%s" % (kind, t), meta)
            path = out / kind / ("%s.csv" % t.replace("^", "").replace("=", "_"))
            df.to_csv(path)
            meta["files"]["%s/%s" % (kind, path.name)] = {"ticker": t, "rows": len(df),
                                                         "first": str(df.index[0].date()),
                                                         "last": str(df.index[-1].date()), "sha256": D.sha256(path)}
    last = (CUT - pd.Timedelta(days=1)).date()
    for sid in FRED:
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s&cosd=%s&coed=%s" % (sid, START, last)
        df = pd.read_csv(url)
        if df.shape[1] != 2:
            raise RuntimeError("FRED format changed for %s: columns %s" % (sid, list(df.columns)))
        df.columns = ["Date", sid]
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
        df[sid] = pd.to_numeric(df[sid], errors="coerce")     # FRED marks missing days with "."
        if df[sid].notna().sum() == 0:
            raise RuntimeError("FRED download empty: %s" % sid)
        df = guard(df, "fred/%s" % sid, meta)
        path = out / "fred" / ("%s.csv" % sid)
        df.to_csv(path)
        v = df[sid].dropna()
        meta["files"]["fred/%s" % path.name] = {"ticker": sid, "rows": len(df), "non_missing": len(v),
                                                "first": str(v.index[0].date()), "last": str(v.index[-1].date()),
                                                "sha256": D.sha256(path)}
    meta["descriptions"] = {**TRADABLE, **SIGNAL, **FRED}
    with open(out / "download_meta.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    return meta


def validate(meta):
    spy = pd.read_csv(out / "yahoo_adj" / "SPY.csv", index_col="Date", parse_dates=["Date"]).sort_index()
    cal = spy.index
    gap = float(cfg["data"]["gap_flag"])
    res = {}
    for t in list(TRADABLE) + list(SIGNAL):
        df = pd.read_csv(out / "yahoo_adj" / ("%s.csv" % t.replace("^", "").replace("=", "_")),
                         index_col="Date", parse_dates=["Date"]).sort_index()
        assert df.index.max() < CUT
        # index levels have no meaningful OHLC structure on Yahoo; validate closes the same way
        res[t] = D.validate_prices(df, t, calendar=cal, gap_flag=gap, stale_days=3)
    for sid in FRED:
        df = pd.read_csv(out / "fred" / ("%s.csv" % sid), index_col="Date", parse_dates=["Date"])
        assert df.index.max() < CUT
        res[sid] = [{"ticker": sid, "check": "missing_values", "count": int(df[sid].isna().sum()),
                     "dates": [str(d.date()) for d in df.index[df[sid].isna()]], "detail": "FRED '.' entries"}]
    rdir = PROJECT_ROOT / "results"
    rdir.mkdir(exist_ok=True)
    with open(rdir / "commodities_validation.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    return res


if __name__ == "__main__":
    m = main() if "--validate-only" not in sys.argv else json.load(open(out / "download_meta.json"))
    r = validate(m)
    for k, v in m["files"].items():
        print("%-28s %6d rows  %s .. %s" % (k, v["rows"], v["first"], v["last"]))
    print("holdout rows dropped:", {k: n for k, n in m["holdout_rows_dropped"].items() if n})
    for t, iss in r.items():
        print(t, {i["check"]: i["count"] for i in iss if i["count"]})
