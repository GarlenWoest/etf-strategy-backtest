"""Study 3 data validation (Phase 2 analogue for monthly long-history series) -> reports/data_quality_longhist.md.

Checks every stored series (duplicates, missing months, NaN, non-positive levels, big moves, stale runs) and
cross-checks each traded series against an independent source where one exists. Never modifies data.
Usage: .venv/bin/python -I tools/validate_longhist.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src import PROJECT_ROOT
from src import longhist as LH

RAW = LH.RAW
meta = json.load(open(RAW / "download_meta.json"))
s = {n: LH._s(n) for n in meta["series"]}
KIND = {"stocks_kf_total_return": ("return", 0.25), "tbill_kf_rf": ("level", 2.0),
        "commodities_aqr_excess_return": ("return", 0.25), "aqr_tsmom_factor_reference": ("return", 0.25),
        "aqr_tsmom_cm_factor_reference": ("return", 0.25), "gold_worldbank_usd_oz_monthly_avg": ("level", 0.25),
        "shiller_bond_gross_return": ("level", 0.25), "shiller_cpi": ("level", 0.10), "shiller_sp_price": ("level", 0.25),
        "shiller_sp_dividend": ("level", 0.25), "fred_LTGOVTBD": ("level", 0.25), "fred_GS10": ("level", 0.25),
        "fred_TB3MS": ("level", 2.0), "fred_CPIAUCNS": ("level", 0.10)}


def validate(x, name, kind, flag):
    out = {}
    full = pd.date_range(x.index.min(), x.index.max(), freq="ME")
    out["duplicate months"] = int(x.index.duplicated().sum())
    out["missing months"] = len(full.difference(x.index))
    out["NaN"] = int(x.isna().sum())
    if kind == "level":
        out["non-positive"] = int((x <= 0).sum())
        mv = x.pct_change()
    else:
        out["returns <= -100%"] = int((x <= -1).sum())
        mv = x
    big = mv[mv.abs() > flag]
    out["big moves (>%.0f%%/month)" % (100 * flag)] = "%d%s" % (len(big), (": " + ", ".join(
        "%s %+.0f%%" % (d.strftime("%Y-%m"), 100 * v) for d, v in big.head(6).items())) if len(big) else "")
    same = x.diff().eq(0)
    run = same.groupby((~same).cumsum()).cumsum()
    out["months inside 3+ month unchanged runs"] = int((run >= 2).sum())
    return out


rows = {n: validate(x, n, *KIND[n]) for n, x in s.items()}

# ---------------------------------------------------------------- cross-checks (to 2018, the study's last month)
cc = []
E = "2018-12-31"
lt = LH.bond_returns(s["fred_LTGOVTBD"], 20.0)
g10 = LH.bond_returns(s["fred_GS10"], 10.0)
shb = (s["shiller_bond_gross_return"] - 1).shift(1)   # Shiller dates the return of month m->m+1 at m; ours at m+1 (corr 0.31 unshifted, 1.00 shifted)


def corr(a, b, a0, a1):
    j = pd.concat([a, b], axis=1).sort_index().loc[a0:a1].dropna()
    return float(j.iloc[:, 0].corr(j.iloc[:, 1])), float((j.iloc[:, 0] - j.iloc[:, 1]).mean() * 12), len(j)


c, d, n = corr(g10, shb, "1953-05-31", E)
cc.append(("Bonds 1953-05..2018: my GS10 total return vs Shiller monthly bond return (Shiller shifted 1 month: he dates a return by its start month)", c, d, n))
c, d, n = corr(lt, shb, "1926-07-31", "1953-04-30")
cc.append(("Bonds 1926-07..1953-04: my LTGOVTBD total return vs Shiller (interpolated yields; expect lower)", c, d, n))
c, d, n = corr(lt, g10, "1953-05-31", "2000-06-30")
cc.append(("Bonds 1953-05..2000-06: LTGOVTBD (20y) vs GS10 (10y) construction, overlap", c, d, n))
c, d, n = corr(s["tbill_kf_rf"], s["fred_TB3MS"] / 1200, "1934-01-31", E)
cc.append(("T-bill: Ken French 1-month RF vs FRED TB3MS/12", c, d, n))
sh_tr = (s["shiller_sp_price"] + s["shiller_sp_dividend"] / 12) / s["shiller_sp_price"].shift(1) - 1
c, d, n = corr(s["stocks_kf_total_return"], sh_tr, "1926-08-31", E)
cc.append(("Stocks: Ken French market vs Shiller S&P (monthly-average prices)", c, d, n))
c, d, n = corr(s["fred_CPIAUCNS"].pct_change(), s["shiller_cpi"].pct_change(), "1913-02-28", E)
cc.append(("CPI: FRED CPIAUCNS vs Shiller CPI, monthly change", c, d, n))
gld = pd.read_csv(PROJECT_ROOT / "data/clean/prices/GLD.csv", index_col=0, parse_dates=True)["Close"]
gld_avg = gld.resample("ME").mean().pct_change()
gld_end = gld.resample("ME").last().pct_change()
wb = s["gold_worldbank_usd_oz_monthly_avg"].pct_change()
c, d, n = corr(wb, gld_avg, "2005-01-31", E)
cc.append(("Gold: World Bank monthly average vs GLD monthly average of closes", c, d, n))
c, d, n = corr(wb, gld_end, "2005-01-31", E)
cc.append(("Gold: World Bank monthly average vs GLD month-end (shows averaging smoothing)", c, d, n))
ac = {k: float(v.loc[a0:E].autocorr()) for k, v, a0 in (("gold WB avg", wb, "1971-10-31"), ("GLD month-end", gld_end, "2005-01-31"),
                                                        ("GLD monthly avg", gld_avg, "2005-01-31"),
                                                        ("stocks KF", s["stocks_kf_total_return"], "1926-07-31"),
                                                        ("bonds (built)", pd.concat([lt.loc[:"1953-04-30"], g10.loc["1953-05-31":]]), "1926-08-31"),
                                                        ("commodities AQR", s["commodities_aqr_excess_return"], "1926-07-31"))}

L = ["# Study 3: long-history data quality\n",
     "_Produced by `tools/validate_longhist.py`. Downloaded %s (FRED %s). Every file was truncated before 2024-01-01 "
     "right after parsing and the originals deleted; rows dropped unread: %s. Nothing was filled or edited._\n" % (
         meta["downloaded_at_utc"], meta["fred_downloaded_at_utc"],
         ", ".join("%s %d" % (k, v) for k, v in meta["holdout_rows_dropped"].items() if v)),
     "## Sources and spans\n", "| Series | Source | First | Last | Rows |", "|---|---|---|---|---|"]
src = {"stocks_kf": "Ken French data library", "tbill_kf": "Ken French data library", "commodities_aqr": "AQR datasets",
       "aqr_tsmom": "AQR datasets (reference only)", "gold_worldbank": "World Bank Pink Sheet", "shiller": "Shiller (Yale), cross-check only",
       "fred": "FRED"}
for n, m in meta["series"].items():
    sname = next(v for k, v in src.items() if n.startswith(k))
    L.append("| %s | %s | %s | %s | %d |" % (n, sname, m["first"], m["last"], m["rows"]))
L += ["\n## Checks\n", "| Series | " + " | ".join(next(iter(rows.values())).keys()) + " |",
      "|---|" + "---|" * len(next(iter(rows.values())))]
for n, r in rows.items():
    keys = list(next(iter(rows.values())).keys())
    L.append("| %s | %s |" % (n, " | ".join(str(r.get(k, r.get("non-positive", r.get("returns <= -100%", "")))) for k in keys)))
L += ["\n(The 4th column is non-positive levels for level series and returns ≤ −100% for return series.)\n",
      "## Cross-checks against a second source (through 2018)\n",
      "| Check | Correlation | Mean difference (per year) | Months |", "|---|---|---|---|"]
for name, c, d, n in cc:
    L.append("| %s | %.3f | %+.2f pp | %d |" % (name, c, 100 * d, n))
L += ["\n## Lag-1 autocorrelation of monthly returns (smoothing check)\n", "| Series | Autocorrelation |", "|---|---|"]
L += ["| %s | %.2f |" % (k, v) for k, v in ac.items()]
L += ["\n## Problems and decisions\n",
      "1. **Gold is a monthly average** (World Bank). Averaging smooths returns and adds positive autocorrelation, which "
      "flatters trend rules. Pre-registered robustness check: every trial is also run with signals lagged one extra month.",
      "2. **Bond yields are monthly averages** (FRED LTGOVTBD, GS10), so the built bond returns are slightly smoothed too. "
      "LTGOVTBD (average maturity above 10 years, modelled as 20) is used until 1953-04, GS10 (10 years) after.",
      "3. **Shiller's long rate before 1953 is linearly interpolated between annual values** (it uses next year's yield), "
      "so it is used only as a cross-check, never as a signal or return.",
      "4. **Gold before 1971 was pegged** ($35/oz); gold enters the universe from 1971-10. US residents could not legally "
      "hold gold bullion from 1933 to 1974.",
      "5. **Indexes are not what an investor could buy** for most of the sample: no index funds before 1976, no futures "
      "on bonds before 1977 or stocks before 1982. Returns are index-level; costs (below) are the only friction.",
      "6. **Ken French market** is CRSP value-weighted, month-end, with dividends: the cleanest series here. Shiller's S&P "
      "uses monthly-average prices, hence the imperfect correlation in the cross-check.",
      "7. **Commodities:** AQR's equal-weight futures index (excess return over T-bills; T-bill added back). No second free source exists; not cross-checked.",
      "8. **The study stops at 2018-12-31.** Rows from 2019–2023 exist on disk but are not used; 2024+ rows were never kept."]
(PROJECT_ROOT / "reports" / "data_quality_longhist.md").write_text("\n".join(L) + "\n")
print("\n".join(L[-40:]))
