"""Daily market data for the older monitoring workflows (paper books, watchlist), replacing Yahoo/yfinance
(Phase G, 2026-10-31; owner-approved migration 2026-10-29; Yahoo's terms prohibit automated collection).

Source check (tools/migration_check.py, criteria fixed before running): Alpaca's IEX feed FAILED (single-exchange
first/last trades differ from the official open/close by up to 0.42% on thin leveraged ETFs); Alpaca's consolidated
SIP feed PASSED (closes identical to the prices the books used, opens within 0.075%, watchlist targets identical).

  prices     Alpaca market data, SIP feed, daily bars; quoted (raw) or split/dividend-adjusted. The free plan serves
             SIP only for data at least 15 minutes old, so requests end 20 minutes before now (completed daily bars).
  dividends  Alpaca corporate-actions cash dividends (amount per share on the ex-date)
  T-bill     FRED DTB3 (3-month T-bill, percent), in place of Yahoo's ^IRX (13-week T-bill index, percent)
All requests are read-only GETs through src/live_usdjpy/sources.py (allow-listed hosts and paths). The returned frame
has the shape yfinance gave (columns field x ticker: Open, Close, Dividends), so the paper and watchlist rules are
untouched: only the price source changes.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SOURCE_LABEL = "Alpaca market data, consolidated SIP feed (quoted Open/Close; corporate-actions cash dividends); FRED DTB3 T-bill"


def fred_dtb3(start):
    """DTB3 in percent, validated by the same fetcher as the forward ledger (HTTP status, header, finite, plausible
    range, no future dates). Raises on failure: the paper update then reports an error; it never books 0%."""
    from src.live_usdjpy import financing as FIN
    obs, err = FIN.fetch("DTB3", datetime.now(timezone.utc), lookback_days=(datetime.now(timezone.utc).date()
                                                                            - pd.Timestamp(start).date()).days + 30)
    if err:
        raise RuntimeError("FRED DTB3: %s" % err)
    s = pd.Series({pd.Timestamp(d): v * 100.0 for d, v, _ in obs}).sort_index()
    return s[s.index >= pd.Timestamp(start) - pd.Timedelta(days=15)]


def frame(tickers, start, adjusted=False, dividends=True, now=None, alpaca=None):
    """yfinance-shaped daily frame. '^IRX' among tickers -> FRED DTB3 in its Close column."""
    from src.live_usdjpy import sources as SR
    now = now or datetime.now(timezone.utc)
    end = (now - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    al = alpaca or SR.Alpaca()
    eq = sorted(t for t in set(tickers) if not t.startswith("^"))
    bars = SR.daily_ohlc(al, eq, start, end, adjustment="all" if adjusted else "raw", feed="sip")
    missing = [t for t in eq if bars.get(t) is None or bars[t].empty]
    if missing:
        raise RuntimeError("no Alpaca SIP bars for %s" % ", ".join(missing))
    cols = {}
    for t in eq:
        cols[("Open", t)] = bars[t]["open"]
        cols[("Close", t)] = bars[t]["close"]
    df = pd.DataFrame(cols).sort_index()
    if dividends:
        dv = SR.cash_dividends(al, eq, start, now.date())
        for t in eq:
            df[("Dividends", t)] = pd.Series(dv.get(t, {}), dtype=float).reindex(df.index).fillna(0.0)
    if "^IRX" in tickers:
        df[("Close", "^IRX")] = fred_dtb3(start).reindex(df.index)   # raw: NaN on days without an observation, so the
                                                                     # observation date and age stay visible (2026-11-02)
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    df.index = pd.to_datetime(df.index).normalize()
    return df
