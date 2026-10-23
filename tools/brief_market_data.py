"""Weekly market brief helper: prints last week's market numbers as Markdown. Informational only.

User decision 2026-10-23: the weekly brief is exempt from hard rule 2 (holdout) for briefs/ ONLY. This script therefore
reads current market data, but it writes NOTHING to disk (stdout only), imports nothing from src/, and its output may
never enter data/, research_log.csv or any study.

Prints:
  - weekly and year-to-date total returns (adjusted closes) for SPY, QQQ, GLD, SLV, USO, TLT, measured from the last
    close of the prior week / prior year to the last close of the most recent completed trading week;
  - gold (COMEX front month GC=F and GLD), the ICE US dollar index (DX-Y.NYB), and the 10-year real yield (FRED DFII10).
If a source fails, the affected line says so; nothing is estimated or filled.

Usage: .venv/bin/python -I tools/brief_market_data.py
"""
import warnings
from datetime import date, timedelta

warnings.filterwarnings("ignore")      # library deprecation noise only; data problems are still printed below

import pandas as pd

TICKERS = ["SPY", "QQQ", "GLD", "SLV", "USO", "TLT"]


def week_bounds(today):
    """Last completed Mon-Fri week relative to `today` (a Sunday run covers the week just ended)."""
    last_fri = today - timedelta(days=(today.weekday() - 4) % 7 or (7 if today.weekday() == 4 else 0))
    return last_fri - timedelta(days=4), last_fri


def closes(tickers, start):
    import yfinance as yf
    df = yf.download(tickers, start=start, auto_adjust=True, progress=False, threads=False)
    if df is None or df.empty:
        raise RuntimeError("empty download")
    c = df["Close"] if isinstance(df.columns, pd.MultiIndex) else df[["Close"]].rename(columns={"Close": tickers[0]})
    c.index = pd.to_datetime(c.index).tz_localize(None).normalize()
    return c


def main():
    today = date.today()
    mon, fri = week_bounds(today)
    print("_Week %s to %s (data pulled %s)._\n" % (mon.isoformat(), fri.isoformat(), today.isoformat()))
    try:
        c = closes(TICKERS, date(fri.year - 1, 12, 15).isoformat()).loc[:pd.Timestamp(fri)]
        end = c.index[-1]
        prev_wk = c.loc[:pd.Timestamp(mon) - pd.Timedelta(days=1)].iloc[-1]
        prev_yr = c.loc[:pd.Timestamp(date(fri.year - 1, 12, 31))].iloc[-1]
        print("| ETF | Last close (%s) | Week | Year to date |\n|---|---|---|---|" % end.date())
        for t in TICKERS:
            last = c[t].dropna().iloc[-1]
            print("| %s | %.2f | %+.2f%% | %+.2f%% |" % (t, last, 100 * (last / prev_wk[t] - 1), 100 * (last / prev_yr[t] - 1)))
        print("\nReturns use dividend-adjusted closes (Yahoo Finance via yfinance).")
    except Exception as e:                                  # report, never fill
        print("ETF returns unavailable: %s" % e)
    print("\n**Gold and macro**\n")
    try:
        g = closes(["GC=F", "GLD", "DX-Y.NYB"], (fri - timedelta(days=21)).isoformat()).loc[:pd.Timestamp(fri)]
        for t, name in (("GC=F", "Gold, COMEX front month ($/oz)"), ("GLD", "GLD"), ("DX-Y.NYB", "US dollar index (ICE DXY)")):
            s = g[t].dropna()
            wk = s.loc[:pd.Timestamp(mon) - pd.Timedelta(days=1)].iloc[-1]
            print("- %s: %.2f on %s (week %+.2f%%)" % (name, s.iloc[-1], s.index[-1].date(), 100 * (s.iloc[-1] / wk - 1)))
    except Exception as e:
        print("- Gold / dollar unavailable: %s" % e)
    try:
        y = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10&cosd=%s" % (fri - timedelta(days=30)).isoformat())
        y.columns = ["date", "v"]
        y["v"] = pd.to_numeric(y["v"], errors="coerce")
        y = y.dropna()
        y = y[pd.to_datetime(y["date"]) <= pd.Timestamp(fri)]
        prev = y[pd.to_datetime(y["date"]) < pd.Timestamp(mon)]
        print("- 10-year real yield (FRED DFII10): %.2f%% on %s (week %+.2f pp)" % (
            y["v"].iloc[-1], y["date"].iloc[-1], y["v"].iloc[-1] - prev["v"].iloc[-1]))
    except Exception as e:
        print("- 10-year real yield unavailable: %s" % e)


if __name__ == "__main__":
    main()
