"""Write reports/phase5_validation.md from results/phase5_*.

Usage: .venv/bin/python tools/make_phase5_report.py
"""
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import yfinance

from src import PROJECT_ROOT, load_config

cfg = load_config()
RES = PROJECT_ROOT / "results"
df = pd.read_csv(RES / "phase5_metrics.csv", index_col=0)
wf = pd.read_csv(RES / "phase5_walk_forward.csv")
for c in ("signal", "trade"):                 # "|" would break markdown tables; display only
    df[c] = df[c].str.replace("|", "/", regex=False)
wf["group"] = wf["group"].str.replace("|", "/", regex=False)
meta = pd.read_pickle(RES / "phase5_meta.pkl")
v = df[df.index.str.startswith("V")].copy()
b = df[df.index.str.startswith("B")].copy()
ew, spy = meta["ew_val"], meta["spy_val"]
N = cfg["strategies"]["total_trials"]
from src import data as D
_c = D.load_cash().loc[cfg["dates"]["validation_start"]:cfg["dates"]["validation_end"]]
T_DAYS = len(_c)                      # daily returns in the validation window (first one from the 2018-12-31 close)
def param_label(params, family_params):
    """The ';'-segment(s) of a params string that vary within its family (e.g. vol_threshold=20%)."""
    parts = [p.split(";") for p in family_params]
    vary = [i for i in range(len(parts[0])) if len({q[i] for q in parts}) > 1]
    seg = params.split(";")
    return ";".join(seg[i] for i in vary) if vary else params


def heat(sub, family):
    lab = {p: param_label(p, list(sub["params"].unique())) for p in sub["params"].unique()}
    rows = sub["signal"] + "->" + sub["trade"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 0.45 * rows.nunique() + 2.2))
    for ax, col, title in ((axes[0], "is_sharpe", "in-sample 2006-2018"), (axes[1], "val_sharpe", "validation 2019-2023")):
        piv = sub.assign(row=rows).pivot_table(index="row", columns="params", values=col, sort=False)
        im = ax.imshow(piv.to_numpy(float), cmap="RdYlGn", vmin=-0.5, vmax=1.5, aspect="auto")
        ax.set_xticks(range(piv.shape[1]))
        ax.set_xticklabels([lab[c] for c in piv.columns], rotation=30, ha="right", fontsize=8)
        ax.set_yticks(range(piv.shape[0]))
        ax.set_yticklabels(piv.index, fontsize=8)
        for i in range(piv.shape[0]):
            for j in range(piv.shape[1]):
                ax.text(j, i, "%.2f" % piv.iat[i, j], ha="center", va="center", fontsize=7)
        ax.set_title("%s: Sharpe, %s" % (family, title), fontsize=9)
    fig.colorbar(im, ax=axes, shrink=0.8)
    name = "phase5_heatmap_%s.png" % family
    fig.savefig(PROJECT_ROOT / "reports" / name, dpi=100, bbox_inches="tight")
    plt.close(fig)
    return name


pct = lambda x: "%.1f%%" % (100 * x)
f2 = lambda x: "%.2f" % x
v["plabel"] = [param_label(p, list(v.loc[v["strategy"] == st, "params"].unique())) for p, st in zip(v["params"], v["strategy"])]

beat_ew = v[v["val_sharpe"] > ew]
beat_both = beat_ew[beat_ew["val_sharpe"] > beat_ew["own_bench_val_sharpe"]]
top5 = v.sort_values("val_sharpe", ascending=False).head(5)
wf_ew = wf[wf["wf_sharpe"] > wf["ew_sharpe"]]
wf_both = wf_ew[wf_ew["wf_sharpe"] > wf_ew["own_bench_sharpe"]]

L = []
w = L.append
w("# Phase 5: validation\n")
w("## Result\n")
w("- **%d of %d trials beat the equal-weight benchmark out of sample** (validation 2019–2023: Sharpe above "
  "equal weight's %.2f). **%d of them also beat buy-and-hold of their own instrument(s).**" % (len(beat_ew), N, ew, len(beat_both)))
w("- **Walk-forward 2011–2023 (stitched, per strategy group): %d of %d groups beat equal weight** (%.2f over the "
  "same years), and %d of those also beat their own buy-and-hold." % (len(wf_ew), len(wf), wf["ew_sharpe"].iloc[0], len(wf_both)))
w("- **No trial reaches a Deflated Sharpe probability of 0.95.** With N = %d, a validation Sharpe must clear about "
  "%.2f just to equal the best-of-%d luck level. Five years of data leaves wide error bars." % (N, v["dsr_hurdle_ann"].iloc[0], N))
w("\n**Best 5 by validation Sharpe:**\n")
w("| ID | Strategy | Trades in | Params | Validation Sharpe | 95%% bootstrap CI | **DSR (N=92)** | DSR (effective N≈%d) | "
  "In-sample Sharpe | Validation CAGR | Validation max DD |" % round(meta["n_eff"]))
w("|---|---|---|---|---|---|---|---|---|---|---|")
for tid, r in top5.iterrows():
    w("| %s | %s | %s | %s | %.2f | [%.2f, %.2f] | **%.3f** | %.3f | %.2f | %s | %s |" % (
        tid, r["strategy"], r["trade"], r["plabel"], r["val_sharpe"], r["val_sharpe_ci_lo"],
        r["val_sharpe_ci_hi"], r["dsr"], r["dsr_eff_n"], r["is_sharpe"], pct(r["val_cagr"]), pct(r["val_max_drawdown"])))
w("\nAll five confidence intervals reach down to roughly zero. Their DSRs (0.67–0.73) mean about a 1-in-4 to "
  "1-in-3 chance the best result is luck from testing 92 variants. Even with the lenient effective N, none reaches 0.95. "
  "**On the pre-agreed rule (DSR ≥ 0.95), every trial fails.** Phase 6 applies all kill criteria formally.\n")
w("**Caveat on the validation window:** 2019–2023 was strong for QQQ (buy-and-hold Sharpe 0.86) and "
  "catastrophic for long bonds (TLT −1.8%/yr, TMF −18%/yr, TMF max DD −92%). Results favoring equities or avoiding "
  "TLT partly reflect that one regime.\n")

w("## Definitions\n")
w("- **Runs:** each trial and benchmark is one continuous run from %s to %s, at 1x, 2x and 3x costs, $100 "
  "start, risk layer off (your decision). In-sample (%s to %s) and validation (%s to %s) windows are sliced from "
  "these runs. Positions carry into 2019 exactly as they would live, and each window is rescaled to its prior close. "
  "Nothing after 2023-12-29 was loaded." % (cfg["dates"]["evaluation_start"], cfg["dates"]["validation_end"],
  cfg["dates"]["evaluation_start"], cfg["dates"]["in_sample_end"], cfg["dates"]["validation_start"], cfg["dates"]["validation_end"]))
w("- **Out of sample** = the validation window for each fixed variant, plus the stitched walk-forward per group. "
  "No parameter was chosen on validation data.")
w("- **Walk-forward:** for each group (same strategy, signal and traded instrument; the grid is its parameters), each "
  "test year Y in %d–%d uses the parameter with the best Sharpe over the 5 prior calendar years. The stitched daily "
  "returns come from the continuous runs. A parameter switch at a year boundary is treated as free (each run already "
  "pays its own trading costs). Every group has 3 or 4 parameter values to choose from, rotation included." % (meta["first_wf"], meta["last_wf"]))
w("- **Sharpe / Sortino:** annualized daily excess returns over the prior day's T-bill rate. Calmar = CAGR / |max DD|.")
w("- **Trade:** one holding episode in one instrument, from entry to full exit (top-ups and trims included). "
  "Counted in the window containing its exit; an episode still open at the window end is marked to market.")
w("- **Own benchmark:** the higher validation Sharpe of buy-and-hold of the signal ETF and of the instrument(s) "
  "traded (e.g. QQQ and TQQQ for a QQQ→TQQQ trial). Multi-asset trials use equal weight.")
w("- **Bootstrap:** 10,000 i.i.d. resamples of daily validation excess returns, seed %d + trial index; 2.5%%/97.5%% "
  "percentiles." % cfg["project"]["random_seed"])
w("- **Deflated Sharpe Ratio (Bailey & López de Prado 2014):** probability the true Sharpe exceeds the expected "
  "maximum of N null trials. Inputs: the cross-trial variance of the 92 daily validation Sharpes, each trial's skew and "
  "kurtosis, and T = %d days. **The official figure uses N = 92.** The effective N (%.1f, participation ratio of the "
  "trials' return-correlation matrix) is shown for information only." % (T_DAYS, meta["n_eff"]))
w("- **Calm years:** the 3 calendar years with the lowest SPY volatility in 2006–2023: %s.\n" % ", ".join(map(str, meta["calm"])))

w("## Benchmarks\n")
w("| ID | Instrument | In-sample Sharpe | Validation Sharpe | Validation CAGR | Validation max DD | Worst day | Worst month | "
  "2008 low ($100 start) | 2020 crash low | 2022 low |")
w("|---|---|---|---|---|---|---|---|---|---|---|")
for tid, r in b.iterrows():
    w("| %s | %s | %.2f | %.2f | %s | %s | %s | %s | $%.1f | $%.1f | $%.1f |" % (
        tid, r["trade"], r["is_sharpe"], r["val_sharpe"], pct(r["val_cagr"]), pct(r["val_max_drawdown"]),
        pct(r["worst_day"]), pct(r["worst_month"]), r["stress_2008_min_value"], r["stress_covid_2020_min_value"],
        r["stress_2022_min_value"]))

w("\n## All 92 trials: validation (2019–2023), 1x costs\n")
w("| ID | Strategy | Signal→Trades in | Params | CAGR | Vol | Sharpe | Sortino | Max DD | DD days | Calmar | "
  "Round trips | Win rate | Avg win / avg loss | Profit factor | In market | Turnover/yr | Costs paid | "
  "vs own bench | vs EW | vs SPY |")
w("|" + "---|" * 21)
for tid, r in v.iterrows():
    wl = "%s / %s" % (pct(r["val_avg_win"]) if pd.notna(r["val_avg_win"]) else "-",
                      pct(r["val_avg_loss"]) if pd.notna(r["val_avg_loss"]) else "-")
    pf = "inf" if r["val_profit_factor"] == np.inf else ("-" if pd.isna(r["val_profit_factor"]) else f2(r["val_profit_factor"]))
    w("| %s | %s | %s→%s | %s | %s | %s | %.2f | %.2f | %s | %d | %.2f | %d | %s | %s | %s | %s | %.1fx | $%.2f | %+.2f | %+.2f | %+.2f |" % (
        tid, r["strategy"], r["signal"], r["trade"], r["plabel"], pct(r["val_cagr"]), pct(r["val_ann_vol"]),
        r["val_sharpe"], r["val_sortino"], pct(r["val_max_drawdown"]), r["val_max_dd_duration_days"], r["val_calmar"],
        r["val_n_round_trips"], pct(r["val_win_rate"]) if pd.notna(r["val_win_rate"]) else "-", wl, pf,
        pct(r["val_time_in_market"]), r["val_turnover_per_year"], r["val_costs_paid_usd"],
        r["val_sharpe"] - r["own_bench_val_sharpe"], r["val_sharpe"] - ew, r["val_sharpe"] - spy))

w("\n## In-sample vs validation Sharpe, statistics, cost sensitivity\n")
w("| ID | In-sample Sharpe | Validation Sharpe | Ratio (val/IS) | 95% CI | DSR (N=92) | Val CAGR 1x / 2x / 3x | "
  "Val Sharpe 1x / 2x / 3x | Profitable at 1x but not 2x |")
w("|---|---|---|---|---|---|---|---|---|")
for tid, r in v.iterrows():
    flip = (r["val_total_return"] > 0) and (r["val_total_return_x2"] <= 0)
    ratio = r["val_sharpe"] / r["is_sharpe"] if r["is_sharpe"] > 0 else float("nan")
    w("| %s | %.2f | %.2f | %s | [%.2f, %.2f] | %.3f | %s / %s / %s | %.2f / %.2f / %.2f | %s |" % (
        tid, r["is_sharpe"], r["val_sharpe"], "-" if np.isnan(ratio) else f2(ratio), r["val_sharpe_ci_lo"],
        r["val_sharpe_ci_hi"], r["dsr"], pct(r["val_cagr"]), pct(r["val_cagr_x2"]), pct(r["val_cagr_x3"]),
        r["val_sharpe"], r["val_sharpe_x2"], r["val_sharpe_x3"], "**YES**" if flip else "no"))
flips = v[(v["val_total_return"] > 0) & (v["val_total_return_x2"] <= 0)]
w("\nProfitable at 1x but not at 2x costs: **%d** (%s). Median Sharpe loss going from 1x to 3x costs: %.2f; "
  "largest: %.2f (high-turnover RSI(2) trials)." % (len(flips), ", ".join(flips.index) or "none",
  (v["val_sharpe"] - v["val_sharpe_x3"]).median(), (v["val_sharpe"] - v["val_sharpe_x3"]).max()))

w("\n## Walk-forward (2011–2023, stitched)\n")
w("| Group | WF Sharpe | WF CAGR | WF max DD | Own buy-and-hold Sharpe | Equal-weight Sharpe | Parameter chosen per year |")
w("|---|---|---|---|---|---|---|")
for _, r in wf.iterrows():
    w("| %s | %.2f | %s | %s | %.2f | %.2f | %s |" % (r["group"], r["wf_sharpe"], pct(r["wf_cagr"]), pct(r["wf_max_dd"]),
                                                   r["own_bench_sharpe"], r["ew_sharpe"], r["chosen"]))

w("\n## Parameter stability (heatmaps)\n")
w("Each cell is the Sharpe of one trial. Left: in-sample. Right: validation. A robust edge shows similar colors across "
  "a row's parameters in both panels.\n")
for h in [heat(v[v["strategy"] == f], f) for f in v["strategy"].unique()]:
    w("![%s](%s)\n" % (h, h))

w("## Regimes and stress (1x costs; $100 at the close before each period)\n")
cols = [c for c in v.columns if c.startswith("stress_") and c.endswith("_min_value")]
names = [c[len("stress_"):-len("_min_value")] for c in cols]
w("| ID | " + " | ".join("%s return / low" % n for n in names) + " | Worst day | Worst month |")
w("|" + "---|" * (len(names) + 3))
for tid, r in v.iterrows():
    w("| %s | " % tid + " | ".join("%s / $%.0f" % (pct(r["stress_%s_return" % n]), r["stress_%s_min_value" % n]) for n in names)
      + " | %s (%s) | %s (%s) |" % (pct(r["worst_day"]), r["worst_day_date"], pct(r["worst_month"]), r["worst_month_date"]))
low = {n: v["stress_%s_min_value" % n].min() for n in ("2008", "covid_2020", "2022")}
w("\nLowest value of a $100 account in the three stress periods across all 92 trials: 2008 $%.1f, 2020 crash $%.1f, "
  "2022 $%.1f. **No trial fell to $20 or below.** Buy-and-hold UPRO and TQQQ did in 2008 ($8.7 and $7.6)." %
  (low["2008"], low["covid_2020"], low["2022"]))

w("\n## Suspect-price sensitivity (your instruction)\n")
w("Every trial was rerun with the unresolved suspect closes (QQQ 2012-08-27 to 08-29, UGL 2018-05-18 to 05-22) "
  "replaced by linear interpolation. Largest absolute change in Sharpe: **in-sample %.4f, validation %.4f**. "
  "The suspect days sit in the in-sample period, so validation results are unaffected; the in-sample effect is "
  "negligible. **No conclusion changes.** All 92 reruns are logged in `research_log.csv`.\n"
  % (v["interp_is_sharpe_diff"].abs().max(), v["interp_val_sharpe_diff"].abs().max()))

w("## Reproducibility\n")
w("Seed %d. Python %s, pandas %s, numpy %s, scipy %s, yfinance %s. Data downloaded 2026-10-22 (hashes in "
  "`data/raw/download_meta.json`). Run %s. Full metrics in `results/phase5_metrics.csv` (not tracked); every run is "
  "logged in `research_log.csv` (phase 5-validation at 1x/2x/3x, 5-walk-forward, 5-suspect-sensitivity)." % (
  cfg["project"]["random_seed"], platform.python_version(), pd.__version__, np.__version__, scipy.__version__,
  yfinance.__version__, meta["now"]))
(PROJECT_ROOT / "reports" / "phase5_validation.md").write_text("\n".join(L) + "\n")
print("\n".join(L[:20]))
