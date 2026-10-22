"""INFORMATIONAL track (not validated, failed DSR): Phase 7A Monte Carlo on V073, V074 and the
equal-weight, SPY and UPRO benchmarks. Every trial was killed in Phase 6; this run exists only
because the user asked for it, and every output says so.

Inputs: daily returns over the validation period only (2019-01-01..2023-12-31, 1x costs, from one
continuous engine run starting 2006-01-03), with the daily T-bill rate of the same days.
Monte Carlo: 10,000 paths, 20-day circular block bootstrap of (return, T-bill) pairs, $100 start,
30-year horizon, fixed seed; sizes 20%/50%/100% below $1,000 (rest in T-bills); $0/$50/$100 a month;
from the first close at $1,000 the Phase 7B caps and kill switch apply (2% per-trade rule not modelled).

Usage: .venv/bin/python tools/run_info_phase7a.py               (simulate, log, report)
       .venv/bin/python tools/run_info_phase7a.py --report-only (rebuild the report from saved results)
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
from src import data as D
from src import strategies as S
from src import validate as V
from src.engine import run_backtest

LABEL = "INFORMATIONAL: not validated, failed DSR"
cfg = load_config()
assert cfg["dates"]["holdout_locked"]
dates = cfg["dates"]
VS, VE = dates["validation_start"], dates["validation_end"]
ALL = S.UNLEV + [S.LEV[t] for t in S.UNLEV]
prices = {t: D.load_clean(t).loc[:VE] for t in ALL}
cash = D.load_cash().loc[:VE]
closes = pd.DataFrame({t: prices[t]["Close"] for t in S.UNLEV})
vs = {v.test_id: v for v in S.build_variants(closes)}
idx = closes.index
w, flag = S.equal_weight(idx, S.UNLEV)
p7b = cfg["risk"]["phase_7b"]
series = {
    "V073 P2 6-month 1x": (vs["V073"].targets, vs["V073"].rebalance, 1.0),
    "V074 P2 6-month leveraged": (vs["V074"].targets, vs["V074"].rebalance, 1.0),   # 25% slices < 30% cap
    "Equal weight (benchmark)": (w.reindex(columns=ALL, fill_value=0.0), flag, 1.0),
    "SPY buy-and-hold (benchmark)": (S.buy_and_hold(idx, "SPY").reindex(columns=ALL, fill_value=0.0), None,
                                     p7b["max_weight_any_instrument"]),
    "UPRO buy-and-hold (benchmark)": (S.buy_and_hold(idx, "UPRO").reindex(columns=ALL, fill_value=0.0), None,
                                      p7b["max_weight_single_leveraged_etf"]),
}
mc = cfg["validation"]["monte_carlo"]
SIZES = cfg["validation"]["phase7a_position_sizes"]
MONTHLY = cfg["capital"]["monthly_contributions_usd"]
YEARS = 30
SEED = int(cfg["project"]["random_seed"])
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

REPORT_ONLY = "--report-only" in sys.argv
rows = []
for k, (name, (tg, reb, cap)) in enumerate([] if REPORT_ONLY else series.items()):
    r = run_backtest(prices, tg, cash, cfg, rebalance=reb, risk_layer=False, start=dates["evaluation_start"], end=VE)
    path = V.period_path(r.equity, VS, VE)
    ret = path.pct_change().dropna()
    rc = cash.shift(1).reindex(ret.index).fillna(0.0)       # same-night T-bill rate as the engine uses
    sample = {"sample_cagr": float(path.iloc[-1] / 100) ** (252 / len(ret)) - 1,
              "sample_vol": float(ret.std() * np.sqrt(252))}
    for size in SIZES:
        for m in MONTHLY:
            o = V.monte_carlo(ret.to_numpy(), rc.to_numpy(), size, m, cap, cfg, int(mc["paths"]),
                              int(mc["block_length_days"]), YEARS, SEED + k)    # same draws for every size/contribution
            rows.append({"series": name, "size": size, "monthly": m, "cap_after_1000": cap, **sample,
                         "p_reach_before_20": o["p_reach_before_ruin"], "p_20_first": o["p_ruin_first"],
                         "p_neither_30y": o["p_neither"],
                         **{"p_reach_within_%sy" % y: p for y, p in o["p_reach_within"].items()},
                         **{"t_reach_p%d_years" % q: t for q, t in o["time_to_target_years"].items()},
                         **{"value_%dy_p%d" % (y, q): val for y, d in o["values"].items() for q, val in d.items()},
                         "p_killed_after_1000": o["p_killed"]})
out = PROJECT_ROOT / "results"
if REPORT_ONLY:
    df = pd.read_csv(out / "INFORMATIONAL_phase7a_mc.csv")
    if "run_at" in df:
        NOW = str(df["run_at"].iloc[0])
    else:                                     # first run predates the run_at column: take it from the log
        with open(PROJECT_ROOT / "research_log.csv", newline="") as fh:
            NOW = next(r["timestamp_utc"] for r in csv.DictReader(fh) if r["phase"] == "7A-INFORMATIONAL")
        df.assign(run_at=NOW).to_csv(out / "INFORMATIONAL_phase7a_mc.csv", index=False)
else:
    df = pd.DataFrame(rows)
    df.assign(label=LABEL, run_at=NOW).to_csv(out / "INFORMATIONAL_phase7a_mc.csv", index=False)

with open(PROJECT_ROOT / "research_log.csv", "a", newline="") as fh:
    wr = csv.writer(fh)
    for r in rows:                            # empty in --report-only mode: nothing is logged twice
        wr.writerow(["INFO:" + r["series"].split(" ")[0], NOW, "7A-INFORMATIONAL", r["series"], "", "",
                     "size=%.0f%%;monthly=$%d" % (100 * r["size"], r["monthly"]), "%s..%s resampled" % (VS, VE), 1,
                     "", "", "", "", "", LABEL, "",
                     "P(1000 before 20)=%.4f; P(20 first)=%.4f; median years to 1000=%s" % (
                         r["p_reach_before_20"], r["p_20_first"],
                         "%.2f" % r["t_reach_p50_years"] if np.isfinite(r["t_reach_p50_years"]) else ">30")])


def yrs(x):
    return "%.1f" % x if np.isfinite(x) else ">30"


def pc(x):
    return "%.0f%%" % (100 * x) if x >= 0.005 or x == 0 else "<1%"


names = list(series)
base = df[df["monthly"] == 0]
L = []
w_ = L.append
w_("# %s\n" % LABEL)
w_("# Phase 7A Monte Carlo: two killed strategies and three benchmarks\n")
w_("> **NOT VALIDATED: FAILED DSR.** All 92 trials were killed in Phase 6. V073 and V074 failed only the Deflated "
   "Sharpe test (0.727 and 0.669, both below 0.95). Their 2019–2023 results may be luck from testing 92 variants. "
   "This page exists because you asked for it. It is not a recommendation and not a basis for real money.\n")
w_("## In plain English (no monthly additions)\n")
w_("Chance that $100 grows to $1,000 **before** it falls to $20 (within the 30-year simulation), and the median "
   "number of years to reach $1,000. Each column is how much of the account is in the strategy (the rest earns "
   "T-bills).\n")
w_("| | 20% in: chance | 20% in: median years | 50% in: chance | 50% in: median years | 100% in: chance | 100% in: median years |")
w_("|---|---|---|---|---|---|---|")
for n in names:
    cells = []
    for s in SIZES:
        r = base[(base["series"] == n) & (base["size"] == s)].iloc[0]
        cells += [pc(r["p_reach_before_20"]), yrs(r["t_reach_p50_years"])]
    w_("| **%s** | %s |" % (n, " | ".join(cells)))
w_("\n\">30\" means fewer than half of the paths reached $1,000 within the 30-year simulation.\n")
w_("**All-in (100%), no monthly additions:**\n")
for n in names:
    r = base[(base["series"] == n) & (base["size"] == 1.0)].iloc[0]
    w_("- **%s:** out of 100 people running this, about %d reach $1,000 within 3 years and about %d within 10 years; "
       "about %d fall to $20 first." % (n, round(100 * r["p_reach_within_3y"]), round(100 * r["p_reach_within_10y"]),
                                        round(100 * r["p_20_first"])))
w_("\n**How to read this:** these odds come from replaying 2019–2023 over and over in random 20-day chunks. That was "
   "a good period for stocks (SPY +15.8% a year, UPRO +27% a year). The simulation assumes the next decades look "
   "like those five years. They may not. The UPRO line shows how leverage turns a good period into large but fragile "
   "odds. The equal-weight line is the realistic no-skill baseline.\n")

w_("## Detail\n")
w_("Sample used: daily returns 2019-01-02 to 2023-12-29 at 1x costs, with the T-bill rate of the same days.\n")
w_("| Series | Sample CAGR | Sample volatility | Exposure after $1,000 (Phase 7B cap) |\n|---|---|---|---|")
for n in names:
    r = df[df["series"] == n].iloc[0]
    w_("| %s | %.1f%% | %.1f%% | %.0f%% |" % (n, 100 * r["sample_cagr"], 100 * r["sample_vol"], 100 * r["cap_after_1000"]))
for m in MONTHLY:
    w_("\n### $%d added per month\n" % m)
    w_("| Series | Size | P($1,000 before $20) | P($20 first) | Neither in 30y | Years to $1,000 (10th / median / 90th) | "
       "Value after 1y (10th / median / 90th) | After 2y | After 3y | P(kill switch after $1,000) |")
    w_("|---|---|---|---|---|---|---|---|---|---|")
    for n in names:
        for s in SIZES:
            r = df[(df["series"] == n) & (df["size"] == s) & (df["monthly"] == m)].iloc[0]
            val = lambda y: "$%.0f / $%.0f / $%.0f" % (r["value_%dy_p10" % y], r["value_%dy_p50" % y], r["value_%dy_p90" % y])
            w_("| %s | %.0f%% | %s | %s | %s | %s / %s / %s | %s | %s | %s | %s |" % (
                n, 100 * s, pc(r["p_reach_before_20"]), pc(r["p_20_first"]), pc(r["p_neither_30y"]),
                yrs(r["t_reach_p10_years"]), yrs(r["t_reach_p50_years"]), yrs(r["t_reach_p90_years"]),
                val(1), val(2), val(3), pc(r["p_killed_after_1000"])))

w_("\n## Method and limits\n")
w_("- 10,000 paths per cell, a 20-day circular block bootstrap of validation-period daily (return, T-bill) pairs, "
   "and a 30-year horizon.")
w_("- Seed %d + series index; the same random draws are used for every size and contribution level of a series, so "
   "comparisons within a series are like for like." % SEED)
w_("- **Below $1,000:** a constant fraction (20/50/100%%) is in the strategy and the rest earns T-bills. Exposure is "
   "rebalanced daily. That rebalancing is not charged costs and ignores the $1 minimum order, which flatters the "
   "20%% and 50%% cells slightly. No stops, caps or kill switch apply (your rule).")
w_("- **From the first close at or above $1,000:** Phase 7B applies permanently. Exposure is capped (SPY 50%%, UPRO "
   "30%%; the multi-asset series already hold 25%% slices), and a −20%% drop from the post-$1,000 peak moves the "
   "account to cash for good. The 2%% per-trade rule is not modelled; it is designed in Phase 7B.")
w_("- Contributions arrive every 21 trading days and count toward $1,000. Paths keep running after touching $20 "
   "(an aggressive account has no kill switch), so 1/2/3-year values include recoveries funded by contributions.")
w_("- Taxes are not included here.")
w_("- Python %s, pandas %s, numpy %s. Run %s." % (platform.python_version(), pd.__version__, np.__version__, NOW))
(PROJECT_ROOT / "reports" / "INFORMATIONAL_phase7a_monte_carlo.md").write_text("\n".join(L) + "\n")
print("\n".join(L[:22]))
