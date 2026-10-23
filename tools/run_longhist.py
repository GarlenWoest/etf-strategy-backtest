"""Study 3: run the 16 pre-registered long-history trials (V119-V134, commit 79d90a4) and write the report.

Primary run: 1x historical costs (config study3_longhist.costs_one_way), no extra lag. Robustness (not trials): costs x2
and x3, and signals lagged one extra month. Era pass rule and DSR exactly as pre-registered in config.yaml.
Outputs: reports/study3_longhist.md, results/study3_metrics.csv, rows in research_log.csv.
Usage: .venv/bin/python -I tools/run_longhist.py
"""
import csv
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src import PROJECT_ROOT, load_config
from src import longhist as LH
from src import validate as V

cfg = load_config()
assert cfg["dates"]["holdout_locked"]
C3 = cfg["study3_longhist"]
N = int(C3["cumulative_trials_for_dsr"])
ERAS = {k: tuple(v) for k, v in C3["eras"].items()}
E0, E1 = C3["evaluation"]["first_return"], C3["evaluation"]["last_return"]
GOLD_SPAN = "1972-11-30"            # first return after gold's first 12-month lookback on floating prices
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
LOG = PROJECT_ROOT / "research_log.csv"

r, rf = LH.load_returns()
assert r.index.max() <= pd.Timestamp("2018-12-31")

trials, bench = [], []
for i, m in enumerate((6, 8, 10, 12)):
    trials.append(("V%03d" % (119 + i), "P2_multi_asset_trend_longhist", "all", "sma_months=%d" % m, LH.p2_weights(r, m)))
k = 123
for m in (3, 6, 12):
    for a in ("stocks", "bonds", "gold", "commodities"):
        trials.append(("V%03d" % k, "S3_tsmom_monthly_longhist", a, "lookback_months=%d" % m, LH.s3_weights(r, a, m)))
        k += 1
with open(LOG, newline="") as fh:
    reg = [x for x in csv.DictReader(fh) if x["phase"] == "study3-freeze" and x["result"] == "PRE-REGISTERED"]
assert [(t[0], t[1], t[3]) for t in trials] == [(x["test_id"], x["strategy"], x["params"].split(";")[0]) for x in reg]
bench = [("L01", "B&H stocks", "stocks", LH.buy_and_hold(r, "stocks")), ("L02", "B&H bonds", "bonds", LH.buy_and_hold(r, "bonds")),
         ("L03", "B&H commodities", "commodities", LH.buy_and_hold(r, "commodities")), ("L04", "B&H gold", "gold", LH.buy_and_hold(r, "gold")),
         ("L05", "Equal weight (available assets)", "all", LH.equal_weight(r)), ("L06", "60/40 stocks/bonds", "stocks|bonds", LH.sixty_forty(r))]
OWN = {"stocks": "L01", "bonds": "L02", "commodities": "L03", "gold": "L04", "all": "L05"}


def span(asset):
    return GOLD_SPAN if asset == "gold" else E0


runs = {}
for tid, *_, w in [(t[0], t[4]) for t in trials] + [(b[0], b[3]) for b in bench]:
    for tag, kw in (("x1", {}), ("x2", {"cost_mult": 2.0}), ("x3", {"cost_mult": 3.0}), ("lag1", {"lag": 1})):
        runs[(tid, tag)] = LH.simulate(r, rf, w, **kw)[0]

asset_of = {t[0]: t[2] for t in trials}
asset_of.update({b[0]: b[2] for b in bench})


def era_stats(tid, tag, a, b):
    x = runs[(tid, tag)].loc[a:b].dropna()
    asset = asset_of[tid]
    first = r[asset].first_valid_index() if asset in r.columns else r.index[0]
    if asset == "gold":
        first = pd.Timestamp(GOLD_SPAN)
    years = len(x.loc[max(pd.Timestamp(a), first):]) / 12
    if years < 10:
        return np.nan, np.nan, years
    x = x.loc[max(pd.Timestamp(a), first):]
    return LH.sharpe(x, rf), LH.cagr(x), years


rows = {}
for tid in [t[0] for t in trials] + [b[0] for b in bench]:
    d = {}
    for tag in ("x1", "x2", "x3", "lag1"):
        for e, (a, b) in ERAS.items():
            sh, cg, yrs = era_stats(tid, tag, a, b)
            d["%s_%s_sharpe" % (e, tag)], d["%s_%s_cagr" % (e, tag)] = sh, cg
            d["%s_years" % e] = yrs
    full = runs[(tid, "x1")].loc[span(asset_of[tid]):E1].dropna()
    d.update({"full_start": str(full.index[0].date()), "full_sharpe": LH.sharpe(full, rf), "full_cagr": LH.cagr(full),
              "full_max_dd": LH.max_dd(full)})
    wr, wend = LH.worst_rolling(full, 120)
    d.update({"worst10y_ann": wr, "worst10y_end": str(wend.date())})
    rows[tid] = d
df = pd.DataFrame(rows).T

# ---- era pass rule
for t in trials:
    tid, own = t[0], OWN[t[2]]
    for tag in ("x1", "x2", "x3", "lag1"):
        n_pass = 0
        for e in ERAS:
            s_t, s_o, s_6 = (df.at[x, "%s_%s_sharpe" % (e, tag)] for x in (tid, own, "L06"))
            ok = bool(np.isfinite(s_t) and np.isfinite(s_o) and s_t > s_o and s_t > s_6)
            df.at[tid, "%s_%s_pass" % (e, tag)] = ok
            n_pass += ok
        df.at[tid, "eras_passed_%s" % tag] = n_pass

# ---- DSR at cumulative N (monthly excess returns, own span; variance over the 16 Study 3 trials)
ex = {t[0]: (runs[(t[0], "x1")] - rf).loc[span(t[2]):E1].dropna() for t in trials}
msr = np.array([x.mean() / x.std(ddof=1) for x in ex.values()])
for tid, x in ex.items():
    dsr, sr0 = V.deflated_sharpe(x.to_numpy(), msr, N)
    df.at[tid, "dsr"], df.at[tid, "dsr_hurdle_ann"] = dsr, sr0 * np.sqrt(12)
for t in trials:
    df.at[t[0], "passes_era_rule"] = df.at[t[0], "eras_passed_x1"] >= 3
    df.at[t[0], "passes_dsr"] = df.at[t[0], "dsr"] >= cfg["validation"]["kill_criteria"]["min_deflated_sharpe_probability"]

# ---- AQR reference (long/short, vol-scaled, 58 markets; context only)
aqr = LH._s("aqr_tsmom_factor_reference")
aqr_rows = {name: LH.sharpe((aqr + rf.reindex(aqr.index)).loc[a:b].dropna(), rf) for name, (a, b) in
            (("1985-1999", ("1985-01-31", "1999-12-31")), ("2000-2018", ("2000-01-31", "2018-12-31")))}
(PROJECT_ROOT / "results").mkdir(exist_ok=True)
df.to_csv(PROJECT_ROOT / "results" / "study3_metrics.csv")

REPORT_ONLY = "--report-only" in sys.argv          # recompute (deterministic) and rewrite the report; log nothing
with open(LOG if not REPORT_ONLY else "/dev/null", "a", newline="") as fh:
    w = csv.writer(fh)
    for t in trials:
        x = df.loc[t[0]]
        w.writerow([t[0], NOW, "study3-run", t[1], t[2], t[2], t[3], "%s..%s monthly" % (x["full_start"], E1), 1,
                    "%.6f" % x["full_cagr"], "", "%.4f" % x["full_sharpe"], "%.6f" % x["full_max_dd"], "",
                    "PASS" if (x["passes_era_rule"] and x["passes_dsr"]) else "KILLED",
                    "eras passed %d/4 (x1); DSR(N=134)=%.3f" % (x["eras_passed_x1"], x["dsr"]),
                    "eras passed x2=%d x3=%d lag1=%d; worst 10y %.1f%%/yr to %s" % (
                        x["eras_passed_x2"], x["eras_passed_x3"], x["eras_passed_lag1"], 100 * x["worst10y_ann"], x["worst10y_end"])])
    for b in bench:
        x = df.loc[b[0]]
        w.writerow([b[0], NOW, "study3-run", b[1], b[2], b[2], "", "%s..%s monthly" % (x["full_start"], E1), 1,
                    "%.6f" % x["full_cagr"], "", "%.4f" % x["full_sharpe"], "%.6f" % x["full_max_dd"], "", "BENCHMARK-RUN", "", ""])

# ---------------------------------------------------------------- report
EN = list(ERAS)
ELAB = {"E1_pre1950": "1927–1949", "E2_1950_1979": "1950–1979", "E3_1980_1999": "1980–1999", "E4_2000_2018": "2000–2018"}
label = {t[0]: "%s %s %s" % ("P2 trend" if t[1].startswith("P2") else "S3 TSMOM", t[2] if t[2] != "all" else "4-asset", t[3]) for t in trials}
label.update({b[0]: b[1] for b in bench})
tv = df.loc[[t[0] for t in trials]]
surv = [t for t in tv.index if tv.at[t, "passes_era_rule"] and tv.at[t, "passes_dsr"]]
era_ok = [t for t in tv.index if tv.at[t, "passes_era_rule"]]
best = tv["dsr"].astype(float).idxmax()
edge_lines = []
for t in era_ok:
    sp = span(asset_of[t])
    for bm in ("L05", "L06"):
        dlt = (runs[(t, "x1")] - runs[(bm, "x1")]).loc[sp:E1].dropna()
        edge_lines.append("%s minus %s: %+.1f pp a year, t-stat %.1f" % (
            t, bm, 100 * 12 * dlt.mean(), dlt.mean() / dlt.std(ddof=1) * np.sqrt(len(dlt))))
f = lambda x: "—" if not np.isfinite(float(x)) else "%.2f" % float(x)
L = ["# Study 3: long-history validation of the near-miss families (1927–2018)\n",
     "_Run %s. Pre-registered in commit 79d90a4 (V119–V134). Monthly data, 1x historical costs. Python %s, pandas %s, numpy %s._\n"
     % (NOW, platform.python_version(), pd.__version__, np.__version__),
     "## Result first\n",
     "- **Survivors under the primary pre-registered settings (1x costs): %s.** %s %d of 16 trials pass the era rule (beat own buy-and-hold and 60/40 on Sharpe in at least 3 of 4 "
     "eras)%s; %d of 16 have a Deflated Sharpe ≥ 0.95 at cumulative N = %d." % (
         "YES (" + ", ".join(surv) + ")" if surv else "NO",
         ("**But neither holds up:** both fall to 2 of 4 eras or fewer at 2x costs, at 3x costs and with signals lagged one "
          "extra month; their grid neighbours (8 and 10 months) pass only 2 eras; and their full-span edge over equal weight is "
          "about zero (and negative versus 60/40). I would not treat them as validated." if surv else ""), len(era_ok), (": " + ", ".join(era_ok)) if era_ok else "",
         int(sum(bool(x) for x in tv["passes_dsr"])), N),
     "- **Best Deflated Sharpe at N = %d: %.3f** (%s, %s), hurdle Sharpe %.2f a year over %s–2018." % (
         N, float(tv.at[best, "dsr"]), best, label[best], float(tv.at[best, "dsr_hurdle_ann"]), tv.at[best, "full_start"][:4]),
     "- **Robustness (pre-registered, not trials):** %s" % "; ".join(
         "%s passes %d of 4 eras at 2x costs, %d at 3x costs, %d with signals lagged one extra month" % (
             t, tv.at[t, "eras_passed_x2"], tv.at[t, "eras_passed_x3"], tv.at[t, "eras_passed_lag1"]) for t in era_ok) + ".",
     "- **How much better than the benchmarks (information only, full span, 1x costs):** " + "; ".join(edge_lines) + ".",
     "- **What the Deflated Sharpe does and doesn't say here:** it tests whether a Sharpe ratio above zero could be luck "
     "from %d trials. Over 90 years almost any diversified rule clears that bar (equal weight alone has a full-span "
     "Sharpe of %.2f). It does not test whether the rule beats the benchmarks; the era rule does." % (N, float(df.at["L05", "full_sharpe"])),
     "- Cumulative trials across the three studies: 92 + 26 + 16 = %d. The holdout stays locked.\n" % N,
     "## Results by era (Sharpe ratio, excess over T-bills, 1x costs)\n",
     "✓ = beats both its own buy-and-hold and 60/40 in that era; — = under 10 years of data in the era (counts as not passed).\n",
     "| ID | Rule | " + " | ".join(ELAB[e] for e in EN) + " | Eras passed (1x / 2x / 3x costs / lag 1) | Full-span Sharpe | DSR (N=134) |",
     "|---|---|" + "---|" * len(EN) + "---|---|---|"]
for t in trials:
    x = df.loc[t[0]]
    cells = []
    for e in EN:
        s = x["%s_x1_sharpe" % e]
        cells.append(f(s) + (" ✓" if x["%s_x1_pass" % e] else ""))
    L.append("| %s | %s | %s | %d / %d / %d / %d | %.2f | %.3f |" % (
        t[0], label[t[0]], " | ".join(cells), x["eras_passed_x1"], x["eras_passed_x2"], x["eras_passed_x3"],
        x["eras_passed_lag1"], x["full_sharpe"], x["dsr"]))
L += ["\n**Benchmarks (same costs on rebalancing):**\n",
      "| ID | Benchmark | " + " | ".join(ELAB[e] for e in EN) + " | Full-span Sharpe | CAGR |", "|---|---|" + "---|" * len(EN) + "---|---|"]
for b in bench:
    x = df.loc[b[0]]
    L.append("| %s | %s | %s | %.2f | %.1f%% |" % (b[0], b[1], " | ".join(f(x["%s_x1_sharpe" % e]) for e in EN),
                                                  x["full_sharpe"], 100 * x["full_cagr"]))
L += ["\n## Worst 10-year stretch (annualized total return over the worst 120 months, full span)\n",
      "| ID | Series | Worst 10 years (per year) | Ending | Full-span CAGR | Max drawdown |", "|---|---|---|---|---|---|"]
for tid in [t[0] for t in trials] + [b[0] for b in bench]:
    x = df.loc[tid]
    L.append("| %s | %s | %+.1f%% | %s | %.1f%% | %.0f%% |" % (tid, label[tid], 100 * x["worst10y_ann"], x["worst10y_end"][:7],
                                                           100 * x["full_cagr"], 100 * x["full_max_dd"]))
L += ["\n## Context: AQR's diversified trend factor\n",
      "AQR's TSMOM factor (long/short, volatility-scaled, about 58 futures markets; reference only, not a trial): Sharpe %.2f "
      "in 1985–1999 and %.2f in 2000–2018. The rules tested here are long-only, unscaled and use 3–4 markets, as in Study 1.\n"
      % (aqr_rows["1985-1999"], aqr_rows["2000-2018"]),
      "## Method and assumptions\n",
      "- **Data:** stocks = Ken French US market total return; bonds = total return built from FRED long-term Treasury "
      "yields (LTGOVTBD to 1953-04, GS10 after; matches Shiller's bond returns at correlation 1.000 after 1953); "
      "commodities = AQR equal-weight futures index plus T-bills; gold = World Bank monthly average from 1971-10; cash = "
      "Ken French T-bill. Details: [`data_quality_longhist.md`](data_quality_longhist.md).",
      "- **Rules:** P2 = 1/k in each available asset above its N-month average of month-end total-return values "
      "(N = 6/8/10/12); S3 = 100% in the asset when its trailing 3/6/12-month total return is positive. Monthly decisions "
      "(Study 1's S3 was checked daily; only monthly data exist here). No leverage.",
      "- **Execution:** weights set at a month-end close earn the next month; rebalanced every month-end; costs on turnover.",
      "- **Costs (one-way):** Hurst, Ooi & Pedersen (2017, Appendix B; AQR 2012 estimates scaled ×6 before 1993 and ×2 for "
      "1993–2002, following Jones 2002): stocks 0.34% / 0.11% / 0.07%, bonds 0.06% / 0.02% / 0.07%, commodities and gold "
      "0.58% / 0.19% / 0.10% (to 1992 / 1993–2002 / 2003+; 2003+ floored at this project's ETF cost). Jones (2002) puts "
      "one-way stock costs near 1% in the 1960s–70s for actual share trading, so the ×3 column is the realistic case for a "
      "pre-1975 stock investor.",
      "- **Pass rule (pre-registered):** an era passes if the trial's Sharpe beats its own buy-and-hold (S3: the asset; P2: "
      "equal weight of available assets) and 60/40; at least 3 of 4 eras needed; eras with under 10 years of the asset's "
      "data count as not passed, so S3 on gold (from 1971-10) cannot pass. DSR uses N = 134 and the cross-trial variance of "
      "the 16 Study 3 Sharpe ratios.",
      "- **Robustness (not trials):** 2x and 3x costs, and signals lagged one extra month, because gold and bond data are "
      "monthly averages (smoothed; lag-1 autocorrelation 0.27 and 0.31).",
      "\n## Limitations\n",
      "- Index-level returns: no index funds before 1976, no bond futures before 1977, no stock-index futures before 1982.",
      "- Gold and bond yields are monthly averages; gold was pegged before 1971 and illegal for US residents to hold 1933–1974.",
      "- The 2000–2018 era overlaps Study 1's in-sample period (2006–2018), where the near-misses were first seen.",
      "- One data vendor per asset (no free second source for commodities)."]
(PROJECT_ROOT / "reports" / "study3_longhist.md").write_text("\n".join(L) + "\n")
print("\n".join(L[3:8]))
print(df.loc[[t[0] for t in trials], ["eras_passed_x1", "eras_passed_lag1", "dsr", "full_sharpe"]].to_string())
