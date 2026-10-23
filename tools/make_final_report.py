"""Final report: reports/FINAL_REPORT.md plus two charts.

Reads results/phase5_metrics.csv, results/phase6_kill.csv, results/INFORMATIONAL_phase7a_mc.csv and
re-runs (deterministically) the equity curves of the five near-miss P2 trials, equal weight and SPY.
The holdout stays locked: nothing after the validation end is loaded.

Usage: .venv/bin/python tools/make_final_report.py
"""
import csv
import json
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import PROJECT_ROOT, load_config
from src import data as D
from src import metrics as M
from src import strategies as S
from src.engine import run_backtest

cfg = load_config()
d = cfg["dates"]
assert d["holdout_locked"]
REP, RES = PROJECT_ROOT / "reports", PROJECT_ROOT / "results"
m5 = pd.read_csv(RES / "phase5_metrics.csv", index_col=0)
kill = pd.read_csv(RES / "phase6_kill.csv", index_col=0)
mc = pd.read_csv(RES / "INFORMATIONAL_phase7a_mc.csv")
dl = json.load(open(PROJECT_ROOT / d.get("raw_dir", "data/raw") / "download_meta.json")) \
    if (PROJECT_ROOT / "data/raw/download_meta.json").exists() else {}

# ---------------------------------------------------------------- chart 1: equity curves
ALL = S.UNLEV + [S.LEV[t] for t in S.UNLEV]
prices = {t: D.load_clean(t).loc[:d["validation_end"]] for t in ALL}
cash = D.load_cash().loc[:d["validation_end"]]
closes = pd.DataFrame({t: prices[t]["Close"] for t in S.UNLEV})
vs = {v.test_id: v for v in S.build_variants(closes)}
idx = closes.index
near = [t for t in kill.index if kill.at[t, "reasons"].startswith("K2") and ";" not in kill.at[t, "reasons"]]
w, flag = S.equal_weight(idx, S.UNLEV)
curves = {}
for t in near:
    r = run_backtest(prices, vs[t].targets, cash, cfg, rebalance=vs[t].rebalance, risk_layer=False,
                     start=d["evaluation_start"], end=d["validation_end"])
    lab = "%s P2 %s %s" % (t, vs[t].params.split(";")[0].replace("sma_months=", "") + "-month",
                           "leveraged" if "UGL" in vs[t].trade_instrument else "1x")
    curves[lab] = r.equity
curves["Equal weight (benchmark)"] = run_backtest(prices, w.reindex(columns=ALL, fill_value=0.0), cash, cfg, rebalance=flag,
                                                  risk_layer=False, start=d["evaluation_start"], end=d["validation_end"]).equity
curves["SPY buy-and-hold (benchmark)"] = run_backtest(prices, S.buy_and_hold(idx, "SPY").reindex(columns=ALL, fill_value=0.0),
                                                      cash, cfg, risk_layer=False, start=d["evaluation_start"],
                                                      end=d["validation_end"]).equity
fig, ax = plt.subplots(figsize=(11, 6))
style = {"Equal weight (benchmark)": dict(color="black", lw=2.2), "SPY buy-and-hold (benchmark)": dict(color="gray", lw=2.2, ls="--")}
palette = ["#1f77b4", "#2ca02c", "#9467bd", "#17becf", "#d62728"]
k = 0
for lab, e in curves.items():
    kw = style.get(lab)
    if kw is None:
        kw = dict(color=palette[k % len(palette)], lw=1.2, alpha=0.9)
        k += 1
    ax.plot(e.index, e.values, label="%s ($%.0f)" % (lab, e.iloc[-1]), **kw)
ax.axvspan(pd.Timestamp(d["validation_start"]), e.index[-1], color="#f4d03f", alpha=0.18, label="validation 2019–2023 (out of sample)")
ax.set_yscale("log")
ax.set_ylabel("Account value, $100 start (log scale)")
ax.set_title("Five near-miss trials (failed only the Deflated Sharpe test) vs benchmarks, 2006–2023, 1x costs")
ax.grid(alpha=0.3, which="both")
ax.legend(fontsize=8, loc="upper left")
fig.tight_layout()
fig.savefig(REP / "final_equity_curves.png", dpi=110)
plt.close(fig)

# ---------------------------------------------------------------- chart 2: kill table matrix
crit = ["K1", "K2", "K3", "K4", "K5", "K6", "K7"]
mat = np.array([[1 if any(x.strip().startswith(c) for x in str(kill.at[t, "reasons"]).split(";")) else 0 for c in crit]
                for t in kill.index])
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 9), gridspec_kw={"width_ratios": [1.6, 1]})
ax1.imshow(mat, cmap="Reds", aspect="auto", vmin=0, vmax=1.4)
ax1.set_xticks(range(len(crit)))
ax1.set_xticklabels(crit)
ax1.set_yticks(range(len(kill)))
ax1.set_yticklabels([t + " " + kill.at[t, "strategy"].split("_")[0] for t in kill.index], fontsize=5)
ax1.set_title("Kill criteria failed by each of the 92 trials (red = failed)", fontsize=10)
counts = mat.sum(axis=0)
ax2.barh(crit[::-1], counts[::-1], color="#c0392b")
for i, c in enumerate(counts[::-1]):
    ax2.text(c + 1, i, str(c), va="center", fontsize=9)
ax2.set_xlim(0, 100)
ax2.set_title("Trials failing each criterion (of 92)", fontsize=10)
labels = {"K1": "beats own B&H and EW", "K2": "DSR >= 0.95", "K3": "survives 2x costs", "K4": "enough trades",
          "K5": "neighbors also work", "K6": "OOS >= half of IS", "K7": "no $20 ruin in stress"}
ax2.set_yticks(range(len(crit)))
ax2.set_yticklabels(["%s %s" % (c, labels[c]) for c in crit[::-1]], fontsize=8)
fig.tight_layout()
fig.savefig(REP / "final_kill_matrix.png", dpi=110)
plt.close(fig)

# ---------------------------------------------------------------- numbers
_bm = json.load(open(PROJECT_ROOT / "data/clean/build_meta.json"))
syn_gap = {t: (o["cagr_syn"] - o["cagr_real"]) * 100 for t, o in _bm["tracking_2019_2023"].items()}
v = m5[m5.index.str.startswith("V")]
ew_val = m5.at["B09", "val_sharpe"]
beat_ew = int((v["val_sharpe"] > ew_val).sum())
beat_both = int(((v["val_sharpe"] > ew_val) & (v["val_sharpe"] > v["own_bench_val_sharpe"])).sum())
wf = pd.read_csv(RES / "phase5_walk_forward.csv")
wf_beat = int((wf["wf_sharpe"] > wf["ew_sharpe"]).sum())
crit_counts = dict(zip(crit, counts))
best = v.sort_values("val_sharpe", ascending=False).head(5)
n_runs = sum(1 for _ in open(PROJECT_ROOT / "research_log.csv")) - 1
tests = sum(1 for p in (PROJECT_ROOT / "tests").glob("test_*.py") for line in open(p) if line.startswith("def test_"))


# ---------------------------------------------------------------- Study 2 (commodities) numbers
c5 = pd.read_csv(RES / "commodities_phase5_metrics.csv", index_col=0)
c6 = pd.read_csv(RES / "commodities_phase6_kill.csv", index_col=0)
ceq = pd.read_csv(RES / "commodities_equity_1x.csv", index_col=0, parse_dates=True)
_cbm = json.load(open(PROJECT_ROOT / "data/clean/commodities/build_meta.json"))
cv = c5[c5.index.str.startswith("V")]
c_surv = int((~c6["killed"]).sum())
c_crit = {k: int(c6["reasons"].fillna("").str.contains(k + " ").sum()) for k in crit}
c_best = cv["dsr"].idxmax()
mix = c5.loc["CB09"]
all_val = pd.concat([m5.loc[m5.index.str.startswith("V"), "val_sharpe"], cv["val_sharpe"]])
n_above_mix = int((all_val > mix["val_sharpe"]).sum())
best_any = all_val.idxmax()
yr = lambda t: ceq[t].resample("YE").last().pct_change().loc["2019":"2023"]


def pc(x):
    return "%.0f%%" % (100 * x) if x >= 0.005 or x == 0 else "<1%"


def yrs(x):
    return "%.0f" % x if np.isfinite(x) else "over 30"


L = []
w_ = L.append
w_("# Can a $100 account reach $1,000 with simple ETF or commodity strategies? Two pre-registered backtest studies\n")
w_("_Final report. Data 2004-11-18 to 2023-12-29. The 2024 onward holdout was never opened. Last updated %s._\n" %
   pd.Timestamp.now().strftime("%Y-%m-%d"))
w_("## Headline (both studies)\n")
w_("**0 of %d pre-registered strategies survived** (Study 1: 0 of 92 on ETFs; Study 2: 0 of 26 on commodities; "
   "the Deflated Sharpe test used the cumulative N = %d). Some killed trials and QQQ buy-and-hold had higher 2019–2023 "
   "Sharpe ratios than the 70/30 SPY/GLD mix (%d trials above it; the best, %s, %.2f), but none by enough to rule out "
   "luck. The 70/30 SPY/GLD mix (Sharpe %.2f, worst drop %.0f%%) beat every commodity trial and is a sensible no-skill "
   "baseline.\n" % (92 + len(cv), 92 + len(cv), n_above_mix, best_any, all_val.max(), mix["val_sharpe"],
                     100 * mix["val_max_drawdown"]))
w_("## Study 1 verdict: ETFs\n")
w_("**No.** I tested 92 pre-registered end-of-day strategies on gold, S&P 500, Nasdaq-100 and long Treasury ETFs and "
   "their 2x/3x leveraged versions, with realistic costs. **None survived the pre-agreed validation rules.** "
   "%d of 92 had a better risk-adjusted return than a simple equal-weight portfolio of the four ETFs in the 2019–2023 "
   "out-of-sample period, but the best of them could be explained by luck from testing so many variants. "
   "Its Deflated Sharpe probability was 0.73, against the 0.95 required. The closest call, a monthly multi-asset "
   "trend filter, had a higher Sharpe ratio than the equal-weight portfolio (0.99 vs 0.81) but a lower return (10.3%% "
   "vs 12.1%% a year), with half the drawdown. That difference is not statistically reliable. Leveraged buy-and-hold "
   "raised returns in good years and lost 90%%+ in bad ones (UPRO and TQQQ in 2008, TMF in 2020–2023). For a $100 "
   "account, monthly savings matter far more than strategy choice: $100 a month reaches $1,000 in 9 months. In the "
   "informational simulation, even the best near-miss took a median of about 11 years to get there from $100 alone. **The honest conclusion: "
   "nothing tested here beat a low-cost diversified index portfolio once overfitting was accounted for.**\n" % beat_ew)

w_("## At a glance\n")
w_("| | |\n|---|---|")
w_("| Question | Does any aggressive end-of-day strategy on 4 ETFs (+ leveraged versions) have a durable edge after costs? |")
w_("| Universe | GLD, SPY, QQQ, TLT; UGL (2x), UPRO, TQQQ, TMF (3x) |")
w_("| Data | Daily adjusted OHLC, 2004-11-18 to 2023-12-29 (Yahoo Finance); 3-month T-bill rate for cash |")
w_("| Design | 92 variants frozen before any backtest; in-sample 2006–2018, validation 2019–2023, holdout 2024+ (locked) |")
w_("| Statistics | Walk-forward, bootstrap confidence intervals, Deflated Sharpe Ratio (N = 92), 7 kill criteria |")
w_("| Result | **0 of 92 survive.** 5 near-misses failed only the Deflated Sharpe test |")
w_("| Study 2 | Commodities (GLD, SLV, USO; UGL, AGQ, UCO): **0 of 26 survive**; best DSR %.2f at N = 118 (see Study 2 below) |"
   % cv["dsr"].max())
w_("| Engineering | Python, pandas/numpy/scipy; %d unit tests; every run logged (%d rows in `research_log.csv`) |" % (tests, n_runs))

w_("\n## 1. What was tested\n")
w_("**Instruments.** Four unleveraged ETFs (GLD gold, SPY S&P 500, QQQ Nasdaq-100, TLT 20+ year Treasuries) and their "
   "leveraged counterparts (UGL 2x gold futures, UPRO/TQQQ/TMF 3x). Leveraged funds launched in 2008–2010. Before "
   "that I built synthetic daily series from the underlying ETF, the expense ratio, financing at the T-bill rate, and an "
   "extra cost calibrated on 2009–2018 overlap data.\n")
w_("**Strategies** (8 families, 92 variants; grids of 3–4 values, frozen in advance). Signals always come from the "
   "unleveraged ETF's close; positions can sit in the leveraged version.\n")
w_("| Family | Rule | Variants |\n|---|---|---|")
w_("| S2 Trend | Hold when close > N-day moving average (N = 50/100/200), else cash | 24 |")
w_("| S3 Time-series momentum | Hold when the trailing 3/6/12-month return > 0 | 24 |")
w_("| S4 RSI(2) mean reversion | Buy when RSI(2) < 5/10/15, sell on a close above the 5-day average (SPY/QQQ) | 12 |")
w_("| S5 Rotation | Monthly: hold the single best 3/6/12-month performer, cash if all negative | 3 |")
w_("| S6 Leveraged rotation | Same as S5, held in the leveraged version | 3 |")
w_("| P1 Volatility-gated leverage | Above 200-day average: 3x if 20-day volatility < 15/20/25%, else 1x; below: cash | 6 |")
w_("| P2 Multi-asset trend | Monthly: 25% in each ETF above its 6/8/10/12-month average, rest cash | 8 |")
w_("| P3 RSI(2) with trend filter | S4 plus close > 200-day average | 12 |")
w_("\nP1–P3 came from a literature review of 49 sources (Gayed & Bilello 2016; Avellaneda & Zhang 2010; Faber 2007; "
   "Baltussen et al. 2019). They were approved before any backtest.\n")
w_("**Benchmarks:** buy-and-hold of each of the 8 ETFs, and an equal-weight portfolio of GLD/SPY/QQQ/TLT "
   "rebalanced monthly.\n")

w_("## 2. How it was tested\n")
w_("- **No lookahead:** signals use data up to the close; trades fill at the next day's open. A unit test changes "
   "future prices and confirms that past signals, trades and equity are unchanged.")
w_("- **Costs:** half-spread 0.02% (unleveraged) or 0.05% (leveraged), plus 0.05% slippage, on every fill; $0 "
   "commission; fractional shares; $1 minimum order. Uninvested cash earns the T-bill rate. Every result was rerun "
   "at 2x and 3x costs.")
w_("- **Engine check:** buy-and-hold CAGR and max drawdown from the backtester match a direct pandas calculation to "
   "2 decimals for all 9 benchmarks. A hand-calculated trade matches the engine on every cost line.")
w_("- **Splits:** in-sample 2006–2018 (tuning only), validation 2019–2023 (selection only), holdout 2024+ (never "
   "opened, never downloaded).")
w_("- **Walk-forward:** each year from 2011 to 2023, pick the parameter with the best Sharpe over the prior 5 years "
   "and use it the following year.")
w_("- **Multiple testing:** the Deflated Sharpe Ratio (Bailey & López de Prado 2014) gives the probability that a "
   "strategy's true Sharpe beats the best result expected by chance from 92 trials. Bootstrap 95% confidence "
   "intervals use 10,000 resamples with a fixed seed.")
w_("- **Kill criteria, applied mechanically.** A strategy dies if it fails any one:")
w_("  - K1: it doesn't beat both its own buy-and-hold and equal weight out of sample;")
w_("  - K2: Deflated Sharpe probability below 0.95;")
w_("  - K3: profitable at 1x costs but not at 2x;")
w_("  - K4: fewer than 30 trades (monthly strategies need 5 years of out-of-sample data instead);")
w_("  - K5: a neighboring parameter value fails;")
w_("  - K6: out-of-sample Sharpe below half of in-sample;")
w_("  - K7: $100 falls to $20 in 2008, the 2020 crash or 2022.\n")

w_("## 3. Results\n")
w_("![Equity curves](final_equity_curves.png)\n")
final = {k: float(e.iloc[-1]) for k, e in curves.items()}
ew_end = final["Equal weight (benchmark)"]
one_x = {k: x for k, x in final.items() if k.startswith("V") and "1x" in k}
lev_k = [k for k in final if k.startswith("V") and "leveraged" in k]
w_("**Full period, in dollars:** from $100 in January 2006, the four 1x near-misses ended 2023 with $%.0f–$%.0f, "
   "**less than** buy-and-hold equal weight ($%.0f) or SPY ($%.0f). Their advantage is smoother returns and smaller "
   "drawdowns, not more money. The leveraged version (%s) ended with $%.0f, with a %.0f%% worst drawdown on the way.\n"
   % (min(one_x.values()), max(one_x.values()), ew_end, final["SPY buy-and-hold (benchmark)"], lev_k[0].split(" ")[0],
      final[lev_k[0]], -100 * M.max_drawdown(curves[lev_k[0]])))
w_("**Out of sample (2019–2023):**")
w_("- %d of 92 trials beat equal weight's Sharpe (%.2f); %d also beat buy-and-hold of their own instrument." % (beat_ew, ew_val, beat_both))
w_("- In walk-forward (2011–2023), %d of 30 strategy groups beat equal weight." % wf_beat)
w_("- **No trial reached a Deflated Sharpe probability of 0.95.**\n")
w_("| Best 5 out of sample | Validation Sharpe | 95% CI | Deflated Sharpe (N=92) | Validation CAGR | Max drawdown |")
w_("|---|---|---|---|---|---|")
for t, r in best.iterrows():
    w_("| %s %s %s | %.2f | [%.2f, %.2f] | %.2f | %.1f%% | %.1f%% |" % (t, r["strategy"].split("_")[0], r["params"].split(";")[0],
       r["val_sharpe"], r["val_sharpe_ci_lo"], r["val_sharpe_ci_hi"], r["dsr"], 100 * r["val_cagr"], 100 * r["val_max_drawdown"]))
w_("| Equal weight (benchmark) | %.2f | | | %.1f%% | %.1f%% |" % (ew_val, 100 * m5.at["B09", "val_cagr"], 100 * m5.at["B09", "val_max_drawdown"]))
w_("| SPY (benchmark) | %.2f | | | %.1f%% | %.1f%% |" % (m5.at["B02", "val_sharpe"], 100 * m5.at["B02", "val_cagr"], 100 * m5.at["B02", "val_max_drawdown"]))
w_("\n### Kill table\n")
w_("![Kill matrix](final_kill_matrix.png)\n")
w_("| Criterion | Trials failing |\n|---|---|")
for c in crit:
    w_("| %s %s | %d |" % (c, labels[c], crit_counts[c]))
w_("\nFull per-trial reasons: [`kill_table.md`](kill_table.md).\n")

w_("### Why everything failed\n")
w_("1. **The required edge was too large for the data.** Five years of daily returns give a Sharpe ratio a standard "
   "error of roughly ±0.45. With 92 trials, the best result expected from pure noise is a Sharpe of about %.2f. The "
   "best real result (%.2f) clears that, but not by enough to be 95%% confident." % (v["dsr_hurdle_ann"].iloc[0], best["val_sharpe"].iloc[0]))
w_("2. **Single-ETF timing rules mostly reduce risk; they don't add return.** Trend filters on one ETF usually "
   "lagged buy-and-hold on Sharpe (S2 median in-sample Sharpe 0.26 vs SPY 0.42), consistent with the academic "
   "literature (Zakamulin 2015; Huang et al. 2020).")
w_("3. **Results were fragile.** %d of 92 trials also failed the neighbor test: a nearby parameter value didn't hold "
   "up out of sample. The edge, where it appeared, depended on the exact setting." % crit_counts["K5"])
w_("4. **Costs hurt the active strategies.** The RSI(2) family turns its account over 11–32 times a year; at 3x costs "
   "its Sharpe fell by up to 0.41.")
w_("5. **Diversification was the hidden winner.** The equal-weight portfolio of four uncorrelated-ish assets had a "
   "Sharpe of %.2f, higher than SPY's %.2f, with no rules at all. The near-miss P2 strategies are essentially that "
   "portfolio plus a trend filter." % (ew_val, m5.at["B02", "val_sharpe"]))

w_("\n## 4. Informational Monte Carlo — NOT VALIDATED, FAILED DSR\n")
w_("> Every strategy below was **killed**. This section answers \"what if?\" for illustration only. It replays "
   "2019–2023 daily returns in random 20-day blocks (10,000 paths, 30-year horizon). It assumes the future looks like "
   "a strong stock market. Not a recommendation.\n")
w_("Chance that $100 reaches $1,000 before falling to $20, and median years to $1,000 (no monthly additions):\n")
w_("| Series | 20% invested | 50% invested | 100% invested |\n|---|---|---|---|")
base = mc[mc["monthly"] == 0]
for s in base["series"].unique():
    cells = []
    for size in (0.2, 0.5, 1.0):
        r = base[(base["series"] == s) & (base["size"] == size)].iloc[0]
        cells.append("%s, %s yrs%s" % (pc(r["p_reach_before_20"]), yrs(r["t_reach_p50_years"]),
                                       "; %s hit $20 first" % pc(r["p_20_first"]) if r["p_20_first"] > 0.005 else ""))
    w_("| %s | %s |" % (s.replace("(benchmark)", "(benchmark)"), " | ".join(cells)))
w_("\nWith **$50 or $100 added per month**, every series reaches $1,000 in roughly 0.7–1.4 years, mainly because of "
   "the deposits. Details: [`INFORMATIONAL_phase7a_monte_carlo.md`](INFORMATIONAL_phase7a_monte_carlo.md).\n")

w_("## 5. Limitations\n")
w_("- **Single data source.** All prices come from Yahoo Finance via yfinance (downloaded %s). The planned cross-check "
   "against Stooq was impossible: its download now sits behind a bot-verification page. Two suspected stale-price "
   "stretches (QQQ Aug 27–29 2012; UGL May 18–22 2018) remain unresolved. Rerunning all 92 trials with those days "
   "interpolated changed no conclusion (in-sample Sharpe moved by at most 0.016; validation not at all)."
   % dl.get("downloaded_at_utc", "2026-10-22")[:10])
w_("- **Synthetic leveraged history before 2008–2010.** UGL, UPRO, TQQQ and TMF did not exist in 2004–2008, so "
   "their pre-launch history, including the 2008 crash, is modelled. After calibration the synthetic series track the "
   "real funds closely (correlation 0.996–0.999). In 2019–2023 they still differed by about a point a year: %s. "
   "UGL tracks gold futures, not GLD, adding further tracking error." % "; ".join(
       "%s %s (%+.1f pp/yr)" % (t, "optimistic" if g > 0 else "pessimistic", g) for t, g in syn_gap.items()))
w_("- **Short validation window.** Five years (2019–2023) is too short to separate a modest edge from luck. That is "
   "the main reason the Deflated Sharpe test failed.")
w_("- **2019–2023 regime bias.** The validation period was strong for US large-cap tech (QQQ Sharpe 0.86) and "
   "historically bad for long Treasuries (TMF −18%/year, −92% drawdown). Rules that favored equities and avoided "
   "bonds look better than they likely are in general.")
w_("- **Model simplifications:** today's expense ratios applied to all history; fills at the open with fixed cost "
   "assumptions (no market impact; leveraged ETFs can gap more than 33% in a day); the Monte Carlo's constant "
   "position sizing ignores rebalancing costs. Taxes were not computed, because no strategy survived. If revisited: "
   "short-term gains are taxed as ordinary income (example rates in `config.yaml`: 12% federal + 2.75% Ohio; change "
   "for your situation), and **UGL issues a K-1** (commodity pool; "
   "futures gains roughly 60% long-term / 40% short-term).")
w_("- **The holdout (2024 onward) was deliberately left unopened.** It remains a clean test set for a future, "
   "separately pre-registered study.")

w_("\n## 6. What a future study would need to do differently\n")
w_("1. **Test far fewer ideas, chosen more carefully.** The Deflated Sharpe hurdle grows with the number of trials. A "
   "study of 5–10 variants motivated by economics would need a much smaller edge to pass.")
w_("2. **Use longer out-of-sample evidence.** Use futures or index data back to the 1970s (or earlier) for the "
   "underlying markets, so validation spans several regimes, including inflation-driven bond bear markets.")
w_("3. **Diversify across many markets, not 4 ETFs.** The trend-following evidence that holds up (e.g. Hurst, Ooi & "
   "Pedersen 2017) comes from 50+ futures markets with volatility scaling, not single-asset timing.")
w_("4. **Get a second, independent data source** (e.g. issuer NAV histories or a licensed vendor) and resolve "
   "data anomalies before testing.")
w_("5. **Pre-register the holdout test now:** if a new, independently motivated strategy is defined, run it once on "
   "2024 onward and accept the result.")
w_("6. **Treat contributions as the main lever for small accounts.** At $100, saving rate and diversification "
   "dominate any timing rule tested here.")

w_("\n## Study 2: Commodities\n")
w_("**Question.** After Study 1, does an evidence-backed end-of-day strategy on gold, silver or oil do better? The "
   "research phase graded 153 sources (114 kept; `research/sources_commodities.csv`) into a ranked idea pool "
   "(`research/IDEA_POOL_COMMODITIES.md`). Five ideas were chosen and **26 trials were frozen (V093–V118) before any "
   "backtest**; the Deflated Sharpe test used the **cumulative N = 118** (92 + 26). Same engine, costs, splits "
   "(in-sample %s to 2018, validation 2019–2023, holdout locked) and kill criteria K1–K7, unchanged. Copper was "
   "dropped (CPER unusable before 2017).\n" % cfg["commodity_study"]["evaluation_start"])
w_("| Idea | Rule | Trials |\n|---|---|---|")
w_("| I01 Momentum basket | Month-end: 1/3 each in GLD/SLV/USO whose 3/6/12-month return beats T-bills; 1x or 2x | 6 |")
w_("| I03 Volatility-scaled trend | Carver EWMAC(16,64), sized to 15/20/25% target volatility, weekly; gold only or basket | 6 |")
w_("| I04 Dual momentum | Month-end: hold the best 3/6/12-month performer of GLD/SLV/USO if it beats T-bills; 1x or 2x | 6 |")
w_("| I05 Real-yield filter | Hold GLD/UGL when the 20-day average 10-year TIPS yield is below its 120/250-day average | 4 |")
w_("| I06 Dollar-trend filter | Hold GLD/UGL when the broad dollar index is below its 100/200-day average | 4 |")
w_("\nFRED signals used only values already published on each date (TIPS yield from the 2nd trading day after; dollar "
   "index from the Wednesday after its week). Benchmarks (not trials): buy-and-hold of each fund, SPY, equal weight "
   "GLD/SLV/USO (K1's equal weight) and 70/30 SPY/GLD rebalanced monthly.\n")
w_("### Kill table\n")
w_("**%d of %d survive.** Best Deflated Sharpe at N = 118: **%.3f** (%s, %s), against 0.95 required.\n"
   % (c_surv, len(cv), cv.at[c_best, "dsr"], c_best, cv.at[c_best, "strategy"]))
w_("| Criterion | Trials failing |\n|---|---|")
_cn = {"K1": "does not beat own buy-and-hold and equal weight", "K2": "Deflated Sharpe (N=118) below 0.95",
       "K3": "profitable at 1x, not at 2x costs", "K4": "too few OOS trades / years", "K5": "edge gone one grid step away",
       "K6": "OOS Sharpe below half of in-sample", "K7": "fell to $20 in a stress period"}
for k in crit:
    w_("| %s %s | %d |" % (k, _cn[k], c_crit[k]))
w_("\nFull table: [`commodities_kill_table.md`](commodities_kill_table.md). Validation detail, walk-forward and stress "
   "tests: [`commodities_phase5_validation.md`](commodities_phase5_validation.md).\n")
w_("### Compared with the 70/30 SPY/GLD benchmark (validation 2019–2023)\n")
w_("| Series | Sharpe | CAGR | Max drawdown |\n|---|---|---|---|")
for t, name in ((c_best, "%s %s (best DSR)" % (c_best, cv.at[c_best, "strategy"])), ("V107", "V107 same rule at 1x"),
                ("CB09", "70/30 SPY/GLD"), ("CB07", "SPY"), ("CB01", "GLD buy-and-hold"), ("CB08", "Equal weight GLD/SLV/USO")):
    if t == "V107" and c_best == "V107":
        continue
    r = c5.loc[t]
    w_("| %s | %.2f | %.1f%% | %.1f%% |" % (name, r["val_sharpe"], 100 * r["val_cagr"], 100 * r["val_max_drawdown"]))
w_("\nNo commodity trial matched the 70/30 mix on a risk-adjusted basis; the best had a higher return only by taking "
   "a much deeper drawdown.\n")
w_("### Dependence on oil in 2021–2022\n")
w_("The best commodity results came from rotating into oil during its 2021–2022 rally. Calendar-year returns:\n")
w_("| Series | " + " | ".join(str(y) for y in range(2019, 2024)) + " |\n|---|" + "---|" * 5)
for t, name in (("V107", "V107 dual momentum 6m, 1x"), ("V108", "V108 same, 2x"), ("CB09", "70/30 SPY/GLD"), ("CB03", "USO")):
    w_("| %s | %s |" % (name, " | ".join("%+.0f%%" % (100 * x) for x in yr(t))))
w_("\nV107 and V108 held oil on 93% of 2021 trading days and 66% of 2022 trading days, then lost 28% and 49% in 2023. One commodity "
   "rally in a five-year window is exactly the kind of result the Deflated Sharpe test discounts.\n")
w_("### Study 2 limitations\n")
w_("- **Single data source** (Yahoo Finance; the Stooq cross-check is still blocked).")
w_("- **USO changed structure in April 2020** (from front-month to a spread of futures months, plus a 1-for-8 reverse "
   "split). Oil results before and after come from a differently built fund; every oil result is flagged.")
w_("- **FRED revisions not modelled.** Signals used today's FRED vintage, not the values as first published "
   "(release lags were modelled; revisions were not).")
w_("- **Synthetic 2x history before December 2008.** AGQ and UCO are modelled from SLV and USO before launch, with an "
   "extra cost calibrated on 2008–2018 overlap (AGQ %.1f%%, UCO %.1f%% a year). Validation used real prices only."
   % (100 * _cbm["extra_drag"]["AGQ"]["annual"], 100 * _cbm["extra_drag"]["UCO"]["annual"]))
w_("- **Same 2019–2023 validation window as Study 1**, so gold ideas were tested again on years already seen for gold.")

w_("\n## Reproducibility\n")
w_("- **Code:** `src/` (data, engine, strategies, metrics, validation, risk); `tools/` (each phase's runner and "
   "report); `tests/` (%d tests: lookahead, costs, cash interest, adjusted prices, the $1,000 switch, synthetic formula, "
   "kill rules, Monte Carlo)." % tests)
w_("- **Records:** `research_log.csv` logs every run, including failures; `config.yaml` holds every parameter; "
   "`PROGRESS.md` holds the decision history; `AUDIT.md` holds the third-party code audit.")
w_("- **Environment:** seed %d. Python %s, pandas %s, numpy %s. Data hashes are in `data/raw/download_meta.json`." % (
    cfg["project"]["random_seed"], platform.python_version(), pd.__version__, np.__version__))
w_("\n_This is a research exercise, not financial or tax advice._")
(REP / "FINAL_REPORT.md").write_text("\n".join(L) + "\n")
print("near-miss:", near, "tests:", tests, "log rows:", n_runs)
