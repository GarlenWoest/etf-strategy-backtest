"""DIAGNOSTIC, SIZING BUG CHECK (user request 2026-10-26). Not new trials, no N increase, no verdict changes.

Reruns V135-V142 and UB02 (always long) exactly as frozen, except that an open position is reset to 1.0x equity at
each weekly decision (executed with the same one-day lag, paying costs on the change). Applies the frozen K1-K7
mechanically to both runs and reports whether any kill verdict would differ. Also checks whether the frozen K4 count
(which counted cap trims as "position changes") changed any K4 verdict.
Outputs: reports/specialists/usdjpy/study1_diagnostic_sizing.md, research_log.csv rows (phase fx1-diagnostic,
result DIAGNOSTIC), research memory record. The official study-1 results are unchanged.
Usage: .venv/bin/python tools/diag_usdjpy_sizing.py
"""
import csv
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
from src.specialists import usdjpy as U

LABEL = "DIAGNOSTIC, SIZING BUG CHECK"
cfg = load_config()
C = cfg["usdjpy_study1"]
IS0, IS1 = C["evaluation"]["in_sample"]
VA0, VA1 = C["evaluation"]["validation"]
END, N_CUM = "2023-12-29", int(C["cumulative_trials_for_dsr"])
COST, MARKUP = float(C["costs"]["one_way_fraction_of_notional"]), float(C["costs"]["rollover_markup_annual"])
STRESS = {"1998": ("1998-08-01", "1998-12-31"), "2008-09": ("2008-09-01", "2009-03-31"),
          "2011": ("2011-03-01", "2011-04-30"), "2022": ("2022-01-01", "2022-12-31")}
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
d = U.load(end=END)
trials = U.build_trials(d)
tids = [t for t, _, _, _ in trials]
weekly = U.weekly_flags(d.index)
frozen = pd.read_csv(PROJECT_ROOT / "results" / "usdjpy_study1_metrics.csv", index_col=0)


def sharpe(x):
    x = x.dropna()
    return float(x.mean() / x.std(ddof=1) * np.sqrt(252)) if x.std(ddof=1) > 0 else 0.0


def path(eq, a, b):
    prior = eq.loc[:a].iloc[:-1]
    e = eq.loc[a:b]
    return 10000 * pd.concat([prior.iloc[[-1]], e]) / prior.iloc[-1]


def metrics(target, resize):
    out = {}
    runs = {m: run_fx(d["spot"], d["tbill"], d["jp1"], target, COST * m, MARKUP * m, 10000, max_x=1.0, lag=1,
                      start=IS0, end=END, resize=weekly if resize else None) for m in (1, 2)}
    r = runs[1]
    out["is_sharpe"], out["val_sharpe"] = sharpe(r.overlay.loc[IS0:IS1]), sharpe(r.overlay.loc[VA0:VA1])
    for m in (1, 2):
        p = path(runs[m].equity, VA0, VA1)
        out["ret_x%d" % m] = float(p.iloc[-1] / p.iloc[0] - 1)
    tr = r.trades
    out["all_trades"] = int(len(tr))
    out["sign_changes"] = int((tr["from"] != tr["to"]).sum())
    p = r.position
    g = p.groupby(p.ne(p.shift(1)).cumsum()).agg(["first", "size"])
    out["median_hold"] = float(g.loc[g["first"] != 0, "size"].median())
    for s, (a, b) in STRESS.items():
        out["min_" + s] = float(path(r.equity, a, b).min())
    out["exposure_end"] = float(r.notional.iloc[-1] / r.equity.iloc[-1]) if r.equity.iloc[-1] > 0 else 0.0
    return out, r.overlay.loc[VA0:VA1]


def verdicts(df, ub02, change_col):
    """Frozen K1-K7, applied mechanically; `change_col` selects which count K4 uses."""
    k1 = (df["val_sharpe"] > 0) & (df["val_sharpe"] > ub02)
    res = {}
    for t, h, _, _ in trials:
        r = df.loc[t]
        f = []
        if not k1[t]:
            f.append("K1")
        if r["dsr"] < 0.95:
            f.append("K2")
        if r["ret_x1"] > 0 and r["ret_x2"] <= 0:
            f.append("K3")
        if not (r[change_col] >= 30 or r["median_hold"] > 63):
            f.append("K4")
        other = [o for o, hh, _, _ in trials if hh == h and o != t][0]
        if not k1[other]:
            f.append("K5")
        if r["val_sharpe"] < 0.5 * r["is_sharpe"]:
            f.append("K6")
        if any(r["min_" + s] <= 2000 for s in STRESS):
            f.append("K7")
        res[t] = f
    return res


tables = {}
for mode in ("frozen_rerun", "weekly_resize"):
    rows, val = {}, {}
    for tid, _, _, tg in trials + [("UB02", "", "", U.always_long(d))]:
        rows[tid], val[tid] = metrics(tg, mode == "weekly_resize")
    df = pd.DataFrame(rows).T
    vo = pd.DataFrame({t: val[t] for t in tids})
    sr = (vo.mean() / vo.std(ddof=1)).to_numpy()
    for t in tids:
        df.loc[t, "dsr"] = V.deflated_sharpe(vo[t].to_numpy(), sr, N_CUM)[0]
    tables[mode] = df

fr, wr = tables["frozen_rerun"], tables["weekly_resize"]
# consistency: the rerun of the frozen rule must reproduce the official numbers
assert np.allclose(fr.loc[tids, "val_sharpe"].astype(float), frozen.loc[tids, "val_sharpe"].astype(float), atol=1e-9)
v_off = verdicts(fr, fr.loc["UB02", "val_sharpe"], "all_trades")        # official counting (as frozen run did)
v_k4 = verdicts(fr, fr.loc["UB02", "val_sharpe"], "sign_changes")       # K4 on true position changes
v_rs = verdicts(wr, wr.loc["UB02", "val_sharpe"], "sign_changes")       # weekly re-size
killed = lambda v: {t: bool(v[t]) for t in v}
diff_resize = [t for t in tids if killed(v_off)[t] != killed(v_rs)[t]]
diff_k4 = [t for t in tids if killed(v_off)[t] != killed(v_k4)[t]]
crit_changes = {t: (v_off[t], v_rs[t]) for t in tids if v_off[t] != v_rs[t]}

L = ["# %s: USD/JPY study 1\n" % LABEL,
     "_Run %s. **Diagnostic only: not new trials, no N increase, no verdict changes.** The official results stay as in "
     "`study1_kill_table.md`._\n" % NOW,
     "## Answer first\n",
     "- **Would any kill verdict differ with sizing reset to 1x at each weekly decision? %s.** %s" % (
         "YES" if diff_resize else "NO", ("Differences: %s." % ", ".join(diff_resize)) if diff_resize else
         "All 8 trials are killed under both sizing rules."),
     "- **Did counting cap trims as position changes (frozen K4) change any verdict? %s.**" % ("YES: " + ", ".join(diff_k4) if diff_k4 else "NO"),
     "- Always-long (UB02) validation Sharpe: %.2f frozen, %.2f with weekly re-sizing; its exposure at the end of 2023: "
     "%.2fx frozen, %.2fx re-sized.\n" % (fr.loc["UB02", "val_sharpe"], wr.loc["UB02", "val_sharpe"], fr.loc["UB02", "exposure_end"], wr.loc["UB02", "exposure_end"]),
     "## Per trial (validation 2015–2023, 1x costs)\n",
     "| ID | Val Sharpe frozen | Val Sharpe re-sized | DSR frozen | DSR re-sized | Criteria failed (frozen) | Criteria failed (re-sized) | Verdict frozen / re-sized |",
     "|---|---|---|---|---|---|---|---|"]
for t in tids:
    L.append("| %s | %.2f | %.2f | %.3f | %.3f | %s | %s | %s / %s |" % (
        t, fr.loc[t, "val_sharpe"], wr.loc[t, "val_sharpe"], fr.loc[t, "dsr"], wr.loc[t, "dsr"], ", ".join(v_off[t]) or "-",
        ", ".join(v_rs[t]) or "-", "KILLED" if v_off[t] else "PASS", "KILLED" if v_rs[t] else "PASS"))
L.append("| UB02 | %.2f | %.2f | — | — | — | — | benchmark |" % (fr.loc["UB02", "val_sharpe"], wr.loc["UB02", "val_sharpe"]))
L += ["\n## K4 counting check (frozen run)\n",
      "| ID | All trades (as counted) | True position changes | Median hold (days) | K4 as counted | K4 on true changes |", "|---|---|---|---|---|---|"]
for t in tids:
    r = fr.loc[t]
    L.append("| %s | %d | %d | %.0f | %s | %s |" % (t, r["all_trades"], r["sign_changes"], r["median_hold"],
                                                 "fail" if "K4" in v_off[t] else "pass", "fail" if "K4" in v_k4[t] else "pass"))
L += ["\n## Notes\n",
      "- The frozen rerun reproduces the official validation Sharpe ratios exactly (checked by assertion).",
      "- Weekly re-sizing pays costs on every notional change; DSR uses the cross-trial variance of the 8 re-sized trials at N = 142.",
      "- Criteria whose list changed between the two sizing rules: %s." % (
          "; ".join("%s: %s -> %s" % (t, ",".join(a) or "-", ",".join(b) or "-") for t, (a, b) in crit_changes.items()) or "none")]
out = PROJECT_ROOT / "reports" / "specialists" / "usdjpy" / "study1_diagnostic_sizing.md"
out.write_text("\n".join(L) + "\n")

with open(PROJECT_ROOT / "research_log.csv", "a", newline="") as fh:
    w = csv.writer(fh)
    for t in tids + ["UB02"]:
        r = wr.loc[t]
        w.writerow([t, NOW, "fx1-diagnostic", LABEL, "USDJPY", "USDJPY", "weekly re-size to 1x", "%s..%s" % (VA0, VA1), 1,
                    "", "", "%.4f" % r["val_sharpe"], "", int(r["sign_changes"]), "DIAGNOSTIC", "",
                    "not a trial; no N increase; official verdict unchanged" + ("; DSR(N=142)=%.4f" % r["dsr"] if t != "UB02" else "")])
led = Ledger(RESEARCH)
led.append("result", {"market": "usdjpy", "label": LABEL, "study": "USD/JPY study 1",
                      "verdict_would_differ_with_weekly_resize": diff_resize, "k4_trim_counting_changed_verdicts": diff_k4,
                      "val_sharpe_resized": {t: round(float(wr.loc[t, "val_sharpe"]), 4) for t in tids + ["UB02"]},
                      "dsr_resized": {t: round(float(wr.loc[t, "dsr"]), 4) for t in tids},
                      "note": "diagnostic only; official results unchanged", "report": str(out.relative_to(PROJECT_ROOT))})
assert led.verify() is None
print("\n".join(L))
