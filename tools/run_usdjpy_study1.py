"""USD/JPY study 1: run the 8 trials pre-registered in research/USDJPY_PREREGISTRATION.md (V135-V142, commit 2aae894)
exactly as frozen in config.yaml `usdjpy_study1`. Nothing here may be changed after results are seen.

One continuous run per trial and benchmark, 1991-01-02..2023-12-29 (warm-up from 1990), sliced into in-sample
(..2014-12-31) and validation (2015-01-01..). Sharpe = annualized overlay return (equity return minus cash return,
i.e. excess over T-bills). Definitions carried over from Studies 1-3 where the pre-registration is silent:
  K3 "profitable" = total return of the $10,000 ledger over the validation window (as in Studies 1-3)
  K7 window paths are rescaled to $10,000 at the close before each window (as `period_path` in Studies 1-3)
  bootstrap: 10,000 i.i.d. resamples, seed project_seed + 134 + trial index (continuing the earlier seeds)
  walk-forward: per hypothesis, choose the grid value with the best overlay Sharpe over the prior 5 calendar years
Outputs: reports/specialists/usdjpy/study1_kill_table.md, results/usdjpy_study1_metrics.csv, research_log.csv rows
(phases fx1-run, fx1-walk-forward, fx1-kill), research memory records.
Usage: .venv/bin/python tools/run_usdjpy_study1.py
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
from src import validate as V
from src.fx_engine import run_fx
from src.memory import Ledger, RESEARCH
from src.specialists import require_active
from src.specialists import usdjpy as U

cfg = load_config()
require_active("usdjpy", cfg)
C = cfg["usdjpy_study1"]
assert C["frozen"] and cfg["specialists"]["usdjpy"]["periods"]["holdout_locked"]
N_CUM = int(C["cumulative_trials_for_dsr"])
IS0, IS1 = C["evaluation"]["in_sample"]
VA0, VA1 = C["evaluation"]["validation"]
END = "2023-12-29"
COST, MARKUP = float(C["costs"]["one_way_fraction_of_notional"]), float(C["costs"]["rollover_markup_annual"])
START_USD = float(C["sizing"]["start_usd"])
SEED = int(cfg["project"]["random_seed"])
STRESS = {"1998": ("1998-08-01", "1998-12-31"), "2008-09": ("2008-09-01", "2009-03-31"),
          "2011": ("2011-03-01", "2011-04-30"), "2022": ("2022-01-01", "2022-12-31")}
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
LOG = PROJECT_ROOT / "research_log.csv"

d = U.load(end=END)
assert d.index.max() < pd.Timestamp(cfg["dates"]["holdout_start"])
trials = U.build_trials(d)
with open(LOG, newline="") as fh:
    reg = [(r["test_id"], r["strategy"], r["params"]) for r in csv.DictReader(fh)
           if r["phase"] == "fx1-freeze" and r["result"] == "PRE-REGISTERED"]
assert [(t, h, p) for t, h, p, _ in trials] == reg, "trial list differs from the frozen registry"
bench = [("UB01", "flat (cash only)", pd.Series(0.0, index=d.index)), ("UB02", "always long USD/JPY 1x", U.always_long(d))]


def run(target, mult=1.0, lag=1):
    return run_fx(d["spot"], d["tbill"], d["jp1"], target, COST * mult, MARKUP * mult, START_USD,
                  max_x=float(C["sizing"]["max_gross_notional_x"]), lag=lag, start=IS0, end=END)


def sharpe(x):
    x = x.dropna()
    return float(x.mean() / x.std(ddof=1) * np.sqrt(252)) if x.std(ddof=1) > 0 else 0.0


def window_path(eq, a, b):
    prior = eq.loc[:a].iloc[:-1]
    e = eq.loc[a:b]
    base = prior.iloc[-1] if len(prior) else e.iloc[0]
    return START_USD * pd.concat([prior.iloc[[-1]], e]) / base if len(prior) else START_USD * e / base


def max_dd(e):
    return float((e / e.cummax() - 1).min())


def holding_periods(res):
    p = res.position
    chg = p.ne(p.shift(1)).cumsum()
    runs = p.groupby(chg).agg(["first", "size"])
    return runs.loc[runs["first"] != 0, "size"]


rows, runs = {}, {}
for tid, name, params, tg in [(t, h, p, s) for t, h, p, s in trials] + [(b, n, "", s) for b, n, s in bench]:
    r1, r2, r3, rl = run(tg, 1), run(tg, 2), run(tg, 3), run(tg, 1, lag=2)
    runs[tid] = r1
    o = r1.overlay
    hp = holding_periods(r1)
    row = {"test_id": tid, "hypothesis": name, "params": params,
           "is_sharpe": sharpe(o.loc[IS0:IS1]), "val_sharpe": sharpe(o.loc[VA0:VA1]),
           "val_sharpe_x2": sharpe(r2.overlay.loc[VA0:VA1]), "val_sharpe_x3": sharpe(r3.overlay.loc[VA0:VA1]),
           "val_sharpe_lag2": sharpe(rl.overlay.loc[VA0:VA1]),
           "val_overlay_ann": float(o.loc[VA0:VA1].mean() * 252), "is_overlay_ann": float(o.loc[IS0:IS1].mean() * 252)}
    for tag, rr in (("x1", r1), ("x2", r2)):
        p = window_path(rr.equity, VA0, VA1)
        row["val_total_return_%s" % tag] = float(p.iloc[-1] / p.iloc[0] - 1)
    pv = window_path(r1.equity, VA0, VA1)
    row["val_max_dd"] = max_dd(pv)
    row["val_cagr"] = float((pv.iloc[-1] / pv.iloc[0]) ** (252 / (len(pv) - 1)) - 1)
    row["position_changes"] = int(len(r1.trades))
    row["median_hold_days"] = float(hp.median()) if len(hp) else float("nan")
    row["time_in_market_val"] = float((r1.position.loc[VA0:VA1] != 0).mean())
    row["share_long_val"] = float((r1.position.loc[VA0:VA1] > 0).mean())
    for s, (a, b) in STRESS.items():
        w = window_path(r1.equity, a, b)
        row["stress_%s_min" % s] = float(w.min())
        row["stress_%s_ret" % s] = float(w.iloc[-1] / w.iloc[0] - 1)
    rows[tid] = row
df = pd.DataFrame(rows.values()).set_index("test_id")
tids = [t for t, _, _, _ in trials]

# ---- DSR at cumulative N, bootstrap CI, effective N
val_over = pd.DataFrame({t: runs[t].overlay.loc[VA0:VA1] for t in tids})
dsr_sr = (val_over.mean() / val_over.std(ddof=1)).to_numpy()
for k, t in enumerate(tids):
    x = val_over[t].to_numpy()
    dsr, sr0 = V.deflated_sharpe(x, dsr_sr, N_CUM)
    lo, hi = V.bootstrap_sharpe_ci(x, 10000, SEED + 134 + k)
    df.loc[t, ["dsr", "dsr_hurdle_ann", "ci_lo", "ci_hi"]] = [dsr, sr0 * np.sqrt(252), lo, hi]
n_eff = V.effective_trials(val_over.to_numpy())

# ---- walk-forward per hypothesis (2 grid values each), 1996..2023
zero = pd.Series(0.0, index=d.index)


def walk_forward_nan_safe(returns, first, last, train=5):
    """As src.validate.walk_forward, but a window where a grid value never traded (undefined Sharpe) counts as
    Sharpe 0 instead of raising; ties go to the first column, as in the original."""
    pieces, chosen = [], {}
    for y in range(first, last + 1):
        tr = returns.loc["%d-01-01" % (y - train):"%d-12-31" % (y - 1)]
        sh = (tr.mean() / tr.std()).fillna(0.0)
        best = sh.idxmax()
        chosen[y] = best
        pieces.append(returns.loc["%d-01-01" % y:"%d-12-31" % y, best])
    return pd.concat(pieces), chosen


wf = []
for hyp in dict.fromkeys(h for _, h, _, _ in trials):
    ids = [t for t, h, _, _ in trials if h == hyp]
    rets = pd.DataFrame({t: runs[t].overlay for t in ids}).loc[IS0:END]
    st, chosen = walk_forward_nan_safe(rets, 1996, 2023, 5)
    wf.append({"hypothesis": hyp, "ids": ",".join(ids), "wf_sharpe_1996_2023": sharpe(st),
               "wf_sharpe_2015_2023": sharpe(st.loc[VA0:VA1]), "ub02_sharpe_2015_2023": sharpe(runs["UB02"].overlay.loc[VA0:VA1]),
               "chosen": " ".join("%d:%s" % (y, c) for y, c in chosen.items())})
wf = pd.DataFrame(wf)

# ---- kill criteria K1-K7 (config usdjpy_study1.kill_criteria)
ub02 = df.loc["UB02", "val_sharpe"]
kc = cfg["validation"]["kill_criteria"]
df["passes_k1"] = (df["val_sharpe"] > 0) & (df["val_sharpe"] > ub02)
reasons = {}
for t, h, p, _ in trials:
    r = df.loc[t]
    why = []
    if not r["passes_k1"]:
        lost = [s for s, ok in (("flat 0.00", r["val_sharpe"] > 0), ("always-long %.2f" % ub02, r["val_sharpe"] > ub02)) if not ok]
        why.append("K1 val Sharpe %.2f does not beat %s" % (r["val_sharpe"], " and ".join(lost)))
    if r["dsr"] < kc["min_deflated_sharpe_probability"]:
        why.append("K2 DSR %.3f < 0.95" % r["dsr"])
    if r["val_total_return_x1"] > 0 and r["val_total_return_x2"] <= 0:
        why.append("K3 profitable at 1x (%+.1f%%) but not at 2x (%+.1f%%)" % (100 * r["val_total_return_x1"], 100 * r["val_total_return_x2"]))
    slow = r["median_hold_days"] > 63
    if not (r["position_changes"] >= 30 or slow):
        why.append("K4 %d position changes < 30 and median hold %.0f days <= 63" % (r["position_changes"], r["median_hold_days"]))
    other = [o for o, hh, _, _ in trials if hh == h and o != t]
    if other and not df.loc[other[0], "passes_k1"]:
        why.append("K5 neighbour %s fails K1" % other[0])
    if r["val_sharpe"] < kc["min_oos_to_is_sharpe_ratio"] * r["is_sharpe"]:
        why.append("K6 val Sharpe %.2f < half of in-sample %.2f" % (r["val_sharpe"], r["is_sharpe"]))
    hit = [s for s in STRESS if r["stress_%s_min" % s] <= 0.2 * START_USD]
    if hit:
        why.append("K7 fell to $2,000 or below in %s" % ", ".join(hit))
    reasons[t] = why
df["killed"] = [bool(reasons[t]) if t in reasons else np.nan for t in df.index]
df["reasons"] = ["; ".join(reasons[t]) if t in reasons else "" for t in df.index]
surv = [t for t in tids if not reasons[t]]
best = df.loc[tids, "dsr"].astype(float).idxmax()
(PROJECT_ROOT / "results").mkdir(exist_ok=True)
df.to_csv(PROJECT_ROOT / "results" / "usdjpy_study1_metrics.csv")
wf.to_csv(PROJECT_ROOT / "results" / "usdjpy_study1_walk_forward.csv", index=False)

# ---- research log
with open(LOG, "a", newline="") as fh:
    w = csv.writer(fh)
    for t in tids + ["UB01", "UB02"]:
        r = df.loc[t]
        name = r["hypothesis"]
        w.writerow([t, NOW, "fx1-run", name, "USDJPY", "USDJPY", r["params"], "%s..%s" % (IS0, IS1), 1, "", "",
                    "%.4f" % r["is_sharpe"], "", int(r["position_changes"]), "IN-SAMPLE-RUN", "", "overlay Sharpe; $10,000 ledger"])
        for m, sh in ((1, r["val_sharpe"]), (2, r["val_sharpe_x2"]), (3, r["val_sharpe_x3"])):
            w.writerow([t, NOW, "fx1-run", name, "USDJPY", "USDJPY", r["params"], "%s..%s" % (VA0, VA1), m,
                        "%.6f" % r["val_cagr"] if m == 1 else "", "", "%.4f" % sh, "%.6f" % r["val_max_dd"] if m == 1 else "",
                        "", "VALIDATION-RUN", "", ("DSR(N=142)=%.4f; boot95=[%.3f,%.3f]" % (r["dsr"], r["ci_lo"], r["ci_hi"]))
                        if m == 1 and t.startswith("V") else ""])
    for _, g in wf.iterrows():
        w.writerow(["WF:" + g["ids"], NOW, "fx1-walk-forward", g["hypothesis"], "USDJPY", "USDJPY", "train 5y, test 1y",
                    "1996..2023", 1, "", "", "%.4f" % g["wf_sharpe_1996_2023"], "", "", "WALK-FORWARD-RUN", "", "chosen " + g["chosen"]])
    for t in tids:
        r = df.loc[t]
        w.writerow([t, NOW, "fx1-kill", r["hypothesis"], "USDJPY", "USDJPY", r["params"], "%s..%s" % (VA0, VA1), 1,
                    "%.6f" % r["val_cagr"], "", "%.4f" % r["val_sharpe"], "%.6f" % r["val_max_dd"], int(r["position_changes"]),
                    "KILLED" if reasons[t] else "PASS", r["reasons"], "mechanical; pre-registered criteria; N=142"])

# ---- research memory
L = Ledger(RESEARCH)
for t in tids:
    r = df.loc[t]
    L.append("result", {"market": "usdjpy", "test_id": t, "hypothesis": r["hypothesis"], "params": r["params"],
                        "is_sharpe": round(r["is_sharpe"], 4), "val_sharpe": round(r["val_sharpe"], 4),
                        "val_sharpe_always_long": round(ub02, 4), "dsr_N142": round(float(r["dsr"]), 4),
                        "verdict": "KILLED" if reasons[t] else "PASS", "reasons": r["reasons"],
                        "report": "reports/specialists/usdjpy/study1_kill_table.md"})
L.append("result" if not surv else "promising_unconfirmed",
         {"market": "usdjpy", "study": "USD/JPY study 1 (V135-V142)", "survivors": surv, "best_dsr": [best, round(float(df.loc[best, "dsr"]), 4)],
          "cumulative_N": N_CUM, "note": "single-pair evidence is weaker than multi-currency portfolio evidence"})
for t in tids:
    if reasons[t]:
        L.append("rejection", {"market": "usdjpy", "test_id": t, "hypothesis": df.loc[t, "hypothesis"], "params": df.loc[t, "params"],
                               "reason": df.loc[t, "reasons"], "retest_only_with": "a materially new hypothesis or new data"})
assert L.verify() is None

# ---- report
f2 = lambda x: "%.2f" % x
pct = lambda x: "%+.1f%%" % (100 * x)
Lr = ["# USD/JPY study 1: results and kill table (V135–V142)\n",
      "_Run %s. Pre-registered in commit 2aae894 (`research/USDJPY_PREREGISTRATION.md`); run exactly as frozen. "
      "Python %s, pandas %s, numpy %s._\n" % (NOW, platform.python_version(), pd.__version__, np.__version__),
      "## Result first\n",
      "- **Survivors: %s.** %d of 8 trials pass all of K1–K7%s." % ("YES (%s)" % ", ".join(surv) if surv else "NO", len(surv),
                                                                   "" if surv else "; nothing goes further"),
      "- **Best Deflated Sharpe at N = 142: %.3f** (%s, %s %s), against 0.95 required. Hurdle: an annualized Sharpe of "
      "about %.2f is what the best of 142 unskilled trials would reach over these 9 years." % (
          df.loc[best, "dsr"], best, df.loc[best, "hypothesis"], df.loc[best, "params"].split(";")[0], df.loc[best, "dsr_hurdle_ann"]),
      "- **Benchmarks, validation 2015–2023:** flat (UB01) Sharpe 0.00 by construction; always long USD/JPY 1x (UB02) "
      "Sharpe **%s** (overlay %s a year)." % (f2(ub02), pct(df.loc["UB02", "val_overlay_ann"])),
      "- **Single-pair caveat:** the strongest carry and momentum evidence is cross-sectional across many currencies; "
      "single-pair results were expected to be weaker (Burnside, Eichenbaum & Rebelo 2008).\n",
      "## Each trial against both benchmarks (validation 2015–2023, 1x costs)\n",
      "| ID | Hypothesis | Params | Val Sharpe | vs flat (0) | vs always-long (%s) | DSR (N=142) | 95%% CI | IS Sharpe | Verdict |" % f2(ub02),
      "|---|---|---|---|---|---|---|---|---|---|"]
for t in tids:
    r = df.loc[t]
    Lr.append("| %s | %s | %s | %s | %s | %s | %.3f | %s to %s | %s | %s |" % (
        t, r["hypothesis"], r["params"].split(";")[0], f2(r["val_sharpe"]), "beats" if r["val_sharpe"] > 0 else "**loses**",
        "beats" if r["val_sharpe"] > ub02 else "**loses**", r["dsr"], f2(r["ci_lo"]), f2(r["ci_hi"]), f2(r["is_sharpe"]),
        "**KILLED**" if reasons[t] else "**PASS**"))
Lr += ["\n## Kill reasons (mechanical; criteria from `config.yaml usdjpy_study1.kill_criteria`)\n",
       "| ID | Reasons |", "|---|---|"]
Lr += ["| %s | %s |" % (t, df.loc[t, "reasons"] or "-") for t in tids]
Lr += ["\n## Detail\n",
       "| ID | IS overlay/yr | Val overlay/yr | Val Sharpe 2x / 3x costs | Val Sharpe lag 2 | Val ledger return 1x / 2x | Val max DD | Position changes | Median hold (days) | In market (val) | Long share (val) |",
       "|---|---|---|---|---|---|---|---|---|---|---|"]
for t in tids + ["UB02"]:
    r = df.loc[t]
    Lr.append("| %s | %s | %s | %s / %s | %s | %s / %s | %.1f%% | %d | %.0f | %.0f%% | %.0f%% |" % (
        t, pct(r["is_overlay_ann"]), pct(r["val_overlay_ann"]), f2(r["val_sharpe_x2"]), f2(r["val_sharpe_x3"]), f2(r["val_sharpe_lag2"]),
        pct(r["val_total_return_x1"]), pct(r["val_total_return_x2"]), 100 * r["val_max_dd"], r["position_changes"],
        r["median_hold_days"], 100 * r["time_in_market_val"], 100 * r["share_long_val"]))
Lr += ["\n## Stress windows ($10,000 at the start of each window; lowest value)\n",
       "| ID | " + " | ".join(STRESS) + " |", "|---|" + "---|" * len(STRESS)]
for t in tids + ["UB02"]:
    r = df.loc[t]
    Lr.append("| %s | %s |" % (t, " | ".join("%s (low $%.0f)" % (pct(r["stress_%s_ret" % s]), r["stress_%s_min" % s]) for s in STRESS)))
Lr += ["\n## Walk-forward (choose the grid value with the best prior-5-year Sharpe; test the next year)\n",
       "| Hypothesis | Trials | WF Sharpe 1996–2023 | WF Sharpe 2015–2023 | Always-long 2015–2023 | Choices |", "|---|---|---|---|---|---|"]
Lr += ["| %s | %s | %s | %s | %s | %s |" % (g["hypothesis"], g["ids"], f2(g["wf_sharpe_1996_2023"]), f2(g["wf_sharpe_2015_2023"]),
                                          f2(g["ub02_sharpe_2015_2023"]), g["chosen"]) for _, g in wf.iterrows()]
Lr += ["\nEffective number of independent trials among the 8 (correlation-based, information only): %.1f.\n" % n_eff,
       "## Method notes\n",
       "- Sharpe = annualized daily overlay return (equity return minus cash return at DTB3), i.e. excess over T-bills.",
       "- Costs: 0.015% of notional each way plus a 0.75%/yr rollover markup; 2x/3x multiply both.",
       "- K3 uses the $10,000 ledger's total validation return (as in Studies 1–3); K7 rescales each stress window to $10,000.",
       "- Prices: FRED DEXJPUS noon NY; US yields lagged 2 FX days, JGB and VIX 1 day; decisions weekly; execution next "
       "FX day (lag 1); lag 2 reported as robustness.",
       "- The 2024+ holdout was not opened; data end 2023-12-29.",
       "\n## Known issue found after the frozen run (not corrected, per the pre-registration)\n",
       "The frozen sizing rule re-sizes a position only when the target changes or the notional exceeds 1x equity. When "
       "equity dips, the cap shrinks the notional, and it never grows back: always-long (UB02) exposure fell from 1.0x to "
       "about 0.39x by 2015 and 0.32x by 2023, and slow trials such as V135 (median hold 465 days) are affected similarly. "
       "Sharpe-based criteria (K1, K2, K6) are largely scale-invariant and every Deflated Sharpe is far below 0.95, so the "
       "verdict is very unlikely to change, but this has not been verified. Dollar figures (ledger returns, stress lows) "
       "are understated for long holds. Recorded as an error in the research memory; a later study should pre-register "
       "symmetric re-sizing.",
       "\nV140 passes K1 by 0.0008 Sharpe (0.2379 vs 0.2371); applied as frozen, and it is killed by K2 and K5."]
(PROJECT_ROOT / "reports" / "specialists" / "usdjpy" / "study1_kill_table.md").write_text("\n".join(Lr) + "\n")
print("\n".join(Lr[3:20]))
