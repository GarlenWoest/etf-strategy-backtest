"""USD/JPY data validation (Phase 2 analogue) -> reports/specialists/usdjpy/data_quality.md. Never modifies data.

Checks each daily series: duplicates, gaps vs the US business-day calendar, NaN share, non-positive values (FX), large
daily moves (flagged, kept), stale runs. Cross-checks: FRED DEXJPUS vs Yahoo JPY=X close (independent vendor, to
2023-12-29 only); MoF JGB 10Y vs FRED IRLTLT01JPM156N (OECD monthly Japan long-term rate). Describes the MoF
intervention record (counts by year and direction only). No strategy statistic of any kind is computed here.
Usage: .venv/bin/python tools/validate_usdjpy.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src import PROJECT_ROOT, load_config

cfg = load_config()
CUT = cfg["specialists"]["usdjpy"]["periods"]["holdout_start"]
RAW = PROJECT_ROOT / "data" / "raw" / "usdjpy"
OUT = PROJECT_ROOT / "reports" / "specialists" / "usdjpy"
OUT.mkdir(parents=True, exist_ok=True)
meta = json.load(open(RAW / "download_meta.json"))


def load(name):
    return pd.read_csv(RAW / ("%s.csv" % name), index_col=0, parse_dates=True)


def check(s, name, kind, flag):
    s = s.loc["1990-01-01":]                        # the study period starts 1990
    v = s.dropna()
    bd = pd.bdate_range(v.index.min(), v.index.max())
    miss = bd.difference(s.index)
    nan_days = s.index[s.isna()]
    mv = v.pct_change() if kind == "fx" else v.diff()
    big = mv[mv.abs() > flag]
    same = v.diff().eq(0)
    run = same.groupby((~same).cumsum()).cumsum()
    return {"series": name, "first (1990+)": str(v.index.min().date()), "last": str(v.index.max().date()), "values": len(v),
            "duplicate dates": int(s.index.duplicated().sum()), "weekdays absent from file": len(miss),
            "blank values (holidays)": len(nan_days), "non-positive": int((v <= 0).sum()) if kind == "fx" else "n/a",
            "large moves": "%d (> %s)%s" % (len(big), ("%.0f%%" % (100 * flag)) if kind == "fx" else "%.2f pp" % flag,
                                             ": " + ", ".join("%s %+.3g" % (d.date(), x if kind != "fx" else 100 * x)
                                                              for d, x in big.abs().sort_values(ascending=False).head(4).items()) if len(big) else ""),
            "values inside 5+ day unchanged runs": int((run >= 4).sum())}


rows = []
fx = load("fred_DEXJPUS")["DEXJPUS"]
rows.append(check(fx, "DEXJPUS (yen per USD)", "fx", 0.03))
for sid in ("DGS1", "DGS2", "DGS10", "DTB3"):
    rows.append(check(load("fred_" + sid)[sid], sid, "rate", 0.30))
rows.append(check(load("fred_VIXCLS")["VIXCLS"], "VIXCLS", "rate", 15.0))
jgb = load("mof_jgb_yields")
for m in ("1Y", "2Y", "10Y"):
    rows.append(check(jgb[m], "JGB " + m, "rate", 0.30))

# ---- cross-checks
cc = []
try:
    import yfinance as yf
    y = yf.download("JPY=X", start="2003-01-01", end=CUT, auto_adjust=False, progress=False, threads=False)
    y.index = pd.to_datetime(y.index).tz_localize(None)
    yc = (y["Close"]["JPY=X"] if isinstance(y.columns, pd.MultiIndex) else y["Close"]).loc[:"2023-12-29"]
    j = pd.concat([fx, yc], axis=1, keys=["fred", "yahoo"]).dropna()
    j = j[j.index < CUT]
    rel = (j["yahoo"] / j["fred"] - 1)
    r = j.pct_change()
    lag = {k: pd.concat([r["fred"], r["yahoo"].shift(k)], axis=1).corr().iloc[0, 1] for k in (-1, 0, 1)}
    late = r.loc["2011":].corr().iloc[0, 1]
    cc.append(("DEXJPUS (noon NY) vs Yahoo JPY=X close, %s..%s" % (j.index.min().date(), j.index.max().date()),
               "levels agree (median diff %.2f%%, 99th pct |diff| %.2f%%), but daily-return correlation is only %.2f "
               "(Yahoo shifted -1/0/+1 day: %.2f / %.2f / %.2f; 2011-2023 alone: %.2f). Yahoo FX daily bars are not on a "
               "consistent timestamp and are not used; DEXJPUS is the single price source (%d days)" % (
                   100 * rel.median(), 100 * rel.abs().quantile(0.99), lag[0], lag[-1], lag[0], lag[1], late, len(j))))
except Exception as e:                              # report, never fill
    cc.append(("DEXJPUS vs Yahoo JPY=X", "unavailable: %s" % e))
try:
    o = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=IRLTLT01JPM156N&coed=2023-12-31")
    o = pd.Series(pd.to_numeric(o.iloc[:, 1], errors="coerce").to_numpy(), index=pd.to_datetime(o.iloc[:, 0]))
    jm = jgb["10Y"].dropna().resample("MS").mean()
    k = pd.concat([jm, o], axis=1, keys=["mof", "oecd"]).dropna().loc["1990":"2023"]
    cc.append(("MoF JGB 10Y monthly mean vs FRED IRLTLT01JPM156N (OECD), %s..%s" % (k.index.min().date(), k.index.max().date()),
               "corr %.4f; mean abs diff %.3f pp; max abs diff %.3f pp; %d months" % (
                   k.corr().iloc[0, 1], (k["mof"] - k["oecd"]).abs().mean(), (k["mof"] - k["oecd"]).abs().max(), len(k))))
except Exception as e:
    cc.append(("JGB 10Y vs OECD", "unavailable: %s" % e))

iv = load("mof_intervention")
ivu = iv[iv["usdjpy"]]
by = ivu.groupby([ivu.index.year, "direction"]).size().unstack(fill_value=0)

L = ["# USD/JPY specialist: data quality\n",
     "_Produced by `tools/validate_usdjpy.py`. Downloaded %s. All files truncated before %s right after parsing; originals "
     "deleted; rows dropped unread: %s. Nothing filled or edited. No strategy statistic is computed here._\n" % (
         meta["downloaded_at_utc"], CUT, ", ".join("%s %d" % (k, v) for k, v in meta["holdout_rows_dropped"].items() if v)),
     "## Series (from 1990, the study start)\n",
     "| " + " | ".join(rows[0].keys()) + " |", "|" + "---|" * len(rows[0])]
for r in rows:
    L.append("| " + " | ".join(str(v) for v in r.values()) + " |")
L += ["\n\"Weekdays absent\" are mostly US holidays (FRED omits or blanks them). The JGB file follows Tokyo business days, "
      "so its absent weekdays include Japanese holidays.\n", "## Cross-checks\n", "| Check | Result |", "|---|---|"]
L += ["| %s | %s |" % c for c in cc]
L += ["\n## MoF intervention record (USD/JPY operations only; counts of operation days)\n",
      "| Year | " + " | ".join(by.columns) + " |", "|---|" + "---|" * len(by.columns)]
L += ["| %d | %s |" % (yr, " | ".join(str(int(x)) for x in r)) for yr, r in by.iterrows()]
oth = iv[~iv["usdjpy"]]
olist = oth.assign(y=oth.index.year, p=oth["pair_text"].str.replace("\u3000", " ").str.split().str.join(" ")).groupby("p")["y"].agg(["min", "max", "size"])
L += ["\nOther-currency operations in the file, excluded from USD/JPY (%d days): %s." % (len(oth), "; ".join(
          "%s %s (%d)" % (p, ("%d" % r["min"]) if r["min"] == r["max"] else "%d–%d" % (r["min"], r["max"]), r["size"]) for p, r in olist.iterrows())),
      "\n## Point-in-time caveats\n",
      "- **H.10 noon rate:** a market price observable at noon NY on its date; the Fed publishes H.10 weekly, so the "
      "official series lags but the price itself was observable.",
      "- **H.15 yields (DGS*):** usable from the 2nd trading day after their date (rule used in Study 2).",
      "- **JGB yields:** MoF posts them after the Tokyo close; usable from the next US trading day.",
      "- **Intervention:** the 1991-04 to 2001-03 daily record was disclosed only in July 2001 (Ito 2003); today MoF "
      "publishes monthly totals about 2 days after each monthly period and daily detail about 5 weeks after each "
      "quarter (MoF pages, 2026). When monthly totals were first published is UNVERIFIED. Any signal must use "
      "publication dates, never intervention dates.",
      "- **VIX:** an end-of-day index; usable the next trading day."]
(OUT / "data_quality.md").write_text("\n".join(L) + "\n")
print("\n".join(L))
