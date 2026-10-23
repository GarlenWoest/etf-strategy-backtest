"""USD/JPY specialist data (daily only, free official sources; user decisions 2026-10-23).

Sources:
  FRED (fredgraph.csv, no key needed): DEXJPUS (H.10 noon NY buying rate, yen per USD, 1971+), DGS1, DGS2, DGS10
    (H.15 Treasury constant maturity), DTB3 (3-month T-bill), VIXCLS (Cboe VIX, 1990+)
  Japan MoF: JGB constant-maturity yields 1Y-40Y (jgbcme_all.csv, 1974+)
  Japan MoF: Foreign Exchange Intervention Operations (daily records since April 1991), parsed to one row per
    operation; only USD/JPY operations are flagged as such; nothing is inferred from prices
Downloads land in data/raw/usdjpy/_orig/<source>/ (curl, done separately), are parsed here, truncated to dates before
dates.holdout_start immediately, written as clean CSVs to data/raw/usdjpy/, and the originals are deleted (they
contain 2024+ rows). SHA-256, sizes and download times are kept in data/raw/usdjpy/download_meta.json.
Nothing is filled or estimated. If a source fails or changes format, the script stops.

Usage: .venv/bin/python tools/download_usdjpy.py
"""
import csv
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src import PROJECT_ROOT, load_config
from src import data as D

cfg = load_config()
assert cfg["dates"]["holdout_locked"] and cfg["specialists"]["usdjpy"]["periods"]["holdout_locked"]
CUT = pd.Timestamp(cfg["specialists"]["usdjpy"]["periods"]["holdout_start"])
RAW = PROJECT_ROOT / "data" / "raw" / "usdjpy"
ORIG = RAW / "_orig"
FRED = {"DEXJPUS": "Yen per USD, H.10 noon NY buying rate (FRB), daily",
        "DGS1": "US 1-year Treasury constant maturity (H.15), daily",
        "DGS2": "US 2-year Treasury constant maturity (H.15), daily",
        "DGS10": "US 10-year Treasury constant maturity (H.15), daily",
        "DTB3": "US 3-month T-bill secondary market (H.15), daily",
        "VIXCLS": "Cboe VIX close, daily"}
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def fred(sid):
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s&coed=%s" % (sid, (CUT - pd.Timedelta(days=1)).date())
    df = pd.read_csv(url)
    if df.shape[1] != 2:
        raise RuntimeError("FRED format changed for %s: %s" % (sid, list(df.columns)))
    s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").to_numpy(), index=pd.to_datetime(df.iloc[:, 0]))
    if s.notna().sum() == 0:
        raise RuntimeError("FRED download empty: %s" % sid)
    return s


def parse_jgb(path):
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    i = next(k for k, l in enumerate(lines) if l.startswith("Date,1Y"))
    df = pd.read_csv(io.StringIO("\n".join(lines[i:])), na_values=["-", ""])
    df["Date"] = pd.to_datetime(df["Date"], format="%Y/%m/%d")
    return df.set_index("Date").apply(pd.to_numeric, errors="coerce")


def parse_intervention(path):
    """One row per operation: date, amount (100 million yen), currency-pair text, usdjpy flag, direction.
    Year and month are carried forward from the rows above, as in the MoF layout; quarter subtotal rows are skipped."""
    text = path.read_bytes().decode("shift_jis", errors="replace")
    rows, year, month = [], None, None
    for r in csv.reader(io.StringIO(text)):
        if len(r) < 9:
            continue
        y, m, d, amt, pair = r[3].strip(), r[4].strip(), r[5].strip(), r[6].strip(), r[8].strip()
        if y.isdigit():
            year = int(y)
        if m in MONTHS:
            month = MONTHS[m]
        if not d.isdigit() or not amt.replace(",", "").isdigit() or not pair:
            continue                                    # headers, blank lines, quarter subtotals
        if year is None or month is None:
            raise RuntimeError("intervention row without year/month: %s" % r)
        p = pair.lower()
        usdjpy = "us dollar" in p and "yen" in p
        if usdjpy and "dollar (sold)" in p and "yen (bought)" in p:
            direction = "yen_buying"                    # sells USD: pushes USD/JPY down
        elif usdjpy and "dollar (bought)" in p and "yen (sold)" in p:
            direction = "yen_selling"                   # buys USD: pushes USD/JPY up
        else:
            direction = "other"
        rows.append({"date": pd.Timestamp(year, month, int(d)), "amount_100m_yen": int(amt.replace(",", "")),
                     "pair_text": pair, "usdjpy": usdjpy, "direction": direction})
    if not rows:
        raise RuntimeError("intervention file parsed to zero rows: format changed?")
    return pd.DataFrame(rows).set_index("date").sort_index()


def main():
    meta = {"parsed_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "downloaded_at_utc": (ORIG / "downloaded_at.txt").read_text().strip() if (ORIG / "downloaded_at.txt").exists() else None,
            "sources": {"fred": "fredgraph.csv", "mof_jgb": "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv",
                        "mof_intervention": "https://www.mof.go.jp/english/policy/international_policy/reference/feio/foreign_exchange_intervention_operations.csv"},
            "descriptions": FRED, "originals": {}, "holdout_rows_dropped": {}, "series": {}}
    for p in sorted(ORIG.rglob("*.csv")):
        meta["originals"][str(p.relative_to(ORIG))] = {"bytes": p.stat().st_size, "sha256": D.sha256(p)}
    out = {}
    for sid in FRED:
        out["fred_" + sid] = fred(sid).rename(sid).to_frame()
    out["mof_jgb_yields"] = parse_jgb(ORIG / "mof_jgb" / "jgbcme_all.csv")
    out["mof_intervention"] = parse_intervention(ORIG / "mof_intervention" / "feio.csv")
    for name, df in out.items():
        n = int((df.index >= CUT).sum())
        meta["holdout_rows_dropped"][name] = n
        df = df[df.index < CUT]
        df.to_csv(RAW / ("%s.csv" % name), index_label="date")
        meta["series"][name] = {"first": str(df.index.min().date()), "last": str(df.index.max().date()), "rows": int(len(df)),
                                "sha256": D.sha256(RAW / ("%s.csv" % name))}
    for p in sorted(ORIG.rglob("*"), reverse=True):  # originals contain 2024+ rows
        p.unlink() if p.is_file() else p.rmdir()
    ORIG.rmdir()
    (RAW / "download_meta.json").write_text(json.dumps(meta, indent=2))
    return meta


if __name__ == "__main__":
    m = main()
    for k, v in m["series"].items():
        print("%-22s %s .. %s %6d rows" % (k, v["first"], v["last"], v["rows"]))
    print("holdout rows dropped:", m["holdout_rows_dropped"])
