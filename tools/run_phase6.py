"""Phase 6: apply the kill criteria mechanically to all 92 trials. No criterion is changed.

Definitions (approved by the user 2026-10-22, exactly as written in PROGRESS.md):
  K1 OOS Sharpe = validation (2019-2023) Sharpe; must beat BOTH its own buy-and-hold and equal weight.
  K2 Deflated Sharpe probability with N = 92 must be >= 0.95.
  K3 "Profitable" = total return > 0; killed if profitable at 1x costs but not at 2x.
  K4 Trades = round trips exiting in the validation window; need >= 30. Monthly strategies
     (S5, S6, P2) instead need >= 5 years of OOS data (validation = 5 calendar years, 2019-2023).
  K5 Edge disappears one grid step away: killed if a neighboring parameter value in the same group
     (same strategy, signal and traded instrument) fails to beat both benchmarks out of sample.
  K6 OOS Sharpe < 0.5 x in-sample Sharpe.
  K7 Stress: a $100 account falls to $20 or below in 2008, the 2020 crash or 2022.
Writes reports/kill_table.md and appends one row per trial to research_log.csv.

Usage: .venv/bin/python tools/run_phase6.py
"""
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src import PROJECT_ROOT, load_config

cfg = load_config()
kc = cfg["validation"]["kill_criteria"]
df = pd.read_csv(PROJECT_ROOT / "results" / "phase5_metrics.csv", index_col=0)
meta = pd.read_pickle(PROJECT_ROOT / "results" / "phase5_meta.pkl")
ew = meta["ew_val"]
v = df[df.index.str.startswith("V")].copy()
MONTHLY = {"S5_rotation", "S6_leveraged_rotation", "P2_multi_asset_trend"}
oos_years = int(cfg["dates"]["validation_end"][:4]) - int(cfg["dates"]["validation_start"][:4]) + 1   # calendar years
ruin = cfg["capital"]["ruin_usd"]
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

v["beats_both"] = (v["val_sharpe"] > v["own_bench_val_sharpe"]) & (v["val_sharpe"] > ew)
v["group"] = v["strategy"] + "|" + v["signal"] + "|" + v["trade"]
reasons = {}
for tid, r in v.iterrows():
    why = []
    if not r["beats_both"]:
        lost = []
        if r["val_sharpe"] <= r["own_bench_val_sharpe"]:
            lost.append("own buy-and-hold %.2f" % r["own_bench_val_sharpe"])
        if r["val_sharpe"] <= ew:
            lost.append("equal weight %.2f" % ew)
        why.append("K1 OOS Sharpe %.2f does not beat %s" % (r["val_sharpe"], " and ".join(lost)))
    if r["dsr"] < kc["min_deflated_sharpe_probability"]:
        why.append("K2 DSR %.3f < 0.95" % r["dsr"])
    if r["val_total_return"] > 0 and r["val_total_return_x2"] <= 0:
        why.append("K3 profitable at 1x (%+.1f%%) but not at 2x (%+.1f%%)" % (100 * r["val_total_return"],
                                                                             100 * r["val_total_return_x2"]))
    if r["strategy"] in MONTHLY:
        if oos_years < kc["min_oos_years_for_monthly_rotation"]:
            why.append("K4 only %d OOS years (monthly)" % oos_years)
    elif r["val_n_round_trips"] < kc["min_oos_trades"]:
        why.append("K4 %d OOS round trips < 30" % r["val_n_round_trips"])
    grp = v[v["group"] == r["group"]]
    order = list(grp.index)                       # registry order = grid order
    i = order.index(tid)
    bad = [n for n in order[max(0, i - 1):i] + order[i + 1:i + 2] if not v.at[n, "beats_both"]]
    if bad:
        why.append("K5 neighbor(s) %s fail out of sample" % ",".join("%s(%s)" % (n, v.at[n, "params"].split(";")[0]
                                                                          if not v.at[n, "strategy"].startswith("P1")
                                                                          else v.at[n, "params"].split(";")[-1])
                                                                   for n in bad))
    if r["val_sharpe"] < kc["min_oos_to_is_sharpe_ratio"] * r["is_sharpe"]:
        why.append("K6 OOS Sharpe %.2f < half of in-sample %.2f" % (r["val_sharpe"], r["is_sharpe"]))
    lows = {n: r["stress_%s_min_value" % n] for n in ("2008", "covid_2020", "2022")}
    hit = [n for n, x in lows.items() if x <= ruin]
    if hit:
        why.append("K7 fell to $20 or below in %s" % ", ".join(hit))
    reasons[tid] = why
v["killed"] = [bool(reasons[t]) for t in v.index]
v["reasons"] = ["; ".join(reasons[t]) for t in v.index]
survivors = list(v.index[~v["killed"]])

# ---- counts per criterion
crit = ["K1", "K2", "K3", "K4", "K5", "K6", "K7"]
names = {"K1": "OOS Sharpe does not beat own buy-and-hold and equal weight",
         "K2": "Deflated Sharpe probability (N=92) below 0.95",
         "K3": "Profitable at 1x but not at 2x costs",
         "K4": "Too few OOS trades (<30), or <5 OOS years for monthly strategies",
         "K5": "Edge disappears one grid step away",
         "K6": "OOS Sharpe below half of in-sample Sharpe",
         "K7": "Fell to $20 or below in a stress period"}
cnt = {k: sum(any(x.startswith(k) for x in reasons[t]) for t in v.index) for k in crit}
only = {k: sum(len(reasons[t]) == 1 and reasons[t][0].startswith(k) for t in v.index) for k in crit}

L = []
w = L.append
w("# Phase 6: kill table\n")
w("## Result\n")
w("**%d of %d trials survive. %d are killed.**%s\n" % (len(survivors), len(v), len(v) - len(survivors),
  " Survivors: " + ", ".join(survivors) if survivors else
  " **Nothing here beat the benchmarks robustly enough to trust.** Under the pre-agreed rules, no strategy goes to "
  "the holdout, Phase 7 or paper trading. The honest answer is that holding the equal-weight index portfolio was as "
  "good as anything tested."))
w("| Criterion | Trials failing it | Trials failing only this one |\n|---|---|---|")
for k in crit:
    w("| %s %s | %d | %d |" % (k, names[k], cnt[k], only[k]))
w("\nThe criteria were applied mechanically, with the definitions you approved on 2026-10-22 and none changed:")
w("- K1: validation Sharpe must beat both its own buy-and-hold and equal weight (%.2f)." % ew)
w("- K2: DSR with N = 92 must be at least 0.95.")
w("- K3: total return above 0 counts as profitable.")
w("- K4: at least 30 round trips; monthly S5/S6/P2 need 5 OOS years (2019–2023 = %d calendar years, so they pass K4)." % oos_years)
w("- K5: grid neighbors within the same strategy, signal and instrument must also beat both benchmarks.")
w("- K6: OOS Sharpe at least half of in-sample.")
w("- K7: no fall to $20 from $100 in 2008, the 2020 crash or 2022.")
w("\nA trial is killed if ANY criterion fails. Inputs: `results/phase5_metrics.csv` (Phase 5, 1x costs unless stated).\n")
w("## All 92 trials\n")
w("| ID | Strategy | Signal→Trades in | Params | Val Sharpe | Own B&H | EW | DSR | Round trips | IS Sharpe | Verdict | Reasons |")
w("|---|---|---|---|---|---|---|---|---|---|---|---|")
for tid, r in v.iterrows():
    w("| %s | %s | %s→%s | %s | %.2f | %.2f | %.2f | %.3f | %d | %.2f | %s | %s |" % (
        tid, r["strategy"], r["signal"].replace("|", "/"), r["trade"].replace("|", "/"),
        r["params"].replace("|", "/"), r["val_sharpe"], r["own_bench_val_sharpe"], ew, r["dsr"],
        r["val_n_round_trips"], r["is_sharpe"], "**KILLED**" if r["killed"] else "**PASS**", r["reasons"] or "-"))
w("\n## Closest calls\n")
w("Trials that fail only K2 (the DSR) and pass everything else:\n")
k2only = [t for t in v.index if len(reasons[t]) == 1 and reasons[t][0].startswith("K2")]
for t in k2only:
    w("- %s %s %s: validation Sharpe %.2f, DSR %.3f." % (t, v.at[t, "strategy"], v.at[t, "params"].split(";")[0],
                                                          v.at[t, "val_sharpe"], v.at[t, "dsr"]))
if not k2only:
    w("- none")
(PROJECT_ROOT / "reports" / "kill_table.md").write_text("\n".join(L) + "\n")
v[["strategy", "signal", "trade", "params", "killed", "reasons"]].to_csv(PROJECT_ROOT / "results" / "phase6_kill.csv")

with open(PROJECT_ROOT / "research_log.csv", "a", newline="") as fh:
    wr = csv.writer(fh)
    for tid, r in v.iterrows():
        wr.writerow([tid, NOW, "6-kill", r["strategy"], r["signal"], r["trade"], r["params"],
                     "%s..%s" % (cfg["dates"]["validation_start"], cfg["dates"]["validation_end"]), 1,
                     "%.6f" % r["val_cagr"], "%.6f" % r["val_ann_vol"], "%.4f" % r["val_sharpe"],
                     "%.6f" % r["val_max_drawdown"], int(r["val_n_round_trips"]),
                     "KILLED" if r["killed"] else "PASS", r["reasons"], "mechanical; definitions approved 2026-10-22"])
print("survivors:", survivors)
print({k: (cnt[k], only[k]) for k in crit})
print("K2-only:", k2only)
