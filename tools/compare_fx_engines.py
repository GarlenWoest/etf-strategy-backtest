"""ENGINE COMPARISON, DIAGNOSTIC (Priority 1, 2026-10-26). Not new trials, no N increase, no verdict changes.

Runs the frozen USD/JPY study-1 targets (V135-V142 and UB02 always-long) through
  v1  src/fx_engine.run_fx          (engine of record; must reproduce the official validation Sharpe ratios exactly)
  v2  src/fx_engine_v2.run_balance  (future-use engine: currency balances, re-size to target at each weekly decision,
                                     cap at every close, labelled trades)
on the same pre-2024 data, and reports how the corrections (D1 ratchet, D2 K4 counting, D3 implicit daily re-sizing)
move each number and whether the frozen K1-K7 would give a different verdict under v2. The official results stay
as in reports/specialists/usdjpy/study1_kill_table.md.
Outputs: reports/specialists/fx_engine_v2_comparison.md, research_log.csv rows (phase fx-engine-v2-diagnostic,
result DIAGNOSTIC), one research-memory record.
Usage: .venv/bin/python tools/compare_fx_engines.py
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
from src.fx_engine_v2 import ENGINE_VERSION, holding_days, position_changes, run_balance, trade_counts
from src.memory import Ledger, RESEARCH
from src.specialists import usdjpy as U

LABEL = "ENGINE COMPARISON v1 vs v2, DIAGNOSTIC"
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
frozen = pd.read_csv(PROJECT_ROOT / "results" / "usdjpy_study1_metrics.csv", index_col=0)
TARGETS = {t: tg for t, _, _, tg in trials}
TARGETS["UB02"] = U.always_long(d)


def sharpe(x):
    x = x.dropna()
    return float(x.mean() / x.std(ddof=1) * np.sqrt(252)) if x.std(ddof=1) > 0 else 0.0


def path(eq, a, b):
    prior = eq.loc[:a].iloc[:-1]
    e = eq.loc[a:b]
    return 10000 * pd.concat([prior.iloc[[-1]], e]) / prior.iloc[-1]


def run(engine, tg, m):
    if engine == "v1":
        r = run_fx(d["spot"], d["tbill"], d["jp1"], tg, COST * m, MARKUP * m, 10000, max_x=1.0, lag=1, start=IS0, end=END)
        expo = r.notional / r.equity
        p = r.position
        g = p.groupby(p.ne(p.shift(1)).cumsum()).agg(["first", "size"])
        hold = g.loc[g["first"] != 0, "size"]
        tr = r.trades
        counted = int(len(tr))                                        # how the frozen run counted K4
        true_changes = int((tr["from"] != tr["to"]).sum())
        kinds = {"all trades": counted}
    else:
        r = run_balance(d["spot"], d["tbill"], d["jp1"], tg, COST * m, MARKUP * m, 10000, max_x=1.0, lag=1, band=0.0, cap_tolerance=0.0, cap_reset=None,
                        invert=True, start=IS0, end=END)
        expo = r.exposure_x
        hold = holding_days(r)
        counted = true_changes = position_changes(r)
        kinds = trade_counts(r)
    return r, expo, hold, counted, true_changes, kinds


def metrics(engine, tg):
    o = {}
    runs = {m: run(engine, tg, m) for m in (1, 2)}
    r, expo, hold, counted, true_changes, kinds = runs[1]
    o["is_sharpe"], o["val_sharpe"] = sharpe(r.overlay.loc[IS0:IS1]), sharpe(r.overlay.loc[VA0:VA1])
    for m in (1, 2):
        p = path(runs[m][0].equity, VA0, VA1)
        o["ret_x%d" % m] = float(p.iloc[-1] / p.iloc[0] - 1)
    o["k4_count"], o["true_changes"] = counted, true_changes
    o["median_hold"] = float(hold.median()) if len(hold) else 0.0
    held = expo[expo.abs() > 1e-9].abs()
    o["mean_abs_expo_held"] = float(held.mean()) if len(held) else 0.0
    o["expo_end"] = float(expo.iloc[-1])
    o["max_abs_expo"] = float(expo.abs().max())
    o["costs_usd"] = float(r.trades["cost_usd"].sum())
    o["kinds"] = kinds
    for s, (a, b) in STRESS.items():
        o["min_" + s] = float(path(r.equity, a, b).min())
    return o, r.overlay.loc[VA0:VA1]


def table(engine):
    rows, val = {}, {}
    for t, tg in TARGETS.items():
        rows[t], val[t] = metrics(engine, tg)
    df = pd.DataFrame(rows).T
    vo = pd.DataFrame({t: val[t] for t in tids})
    sr = (vo.mean() / vo.std(ddof=1)).to_numpy()
    for t in tids:
        df.loc[t, "dsr"] = V.deflated_sharpe(vo[t].to_numpy(), sr, N_CUM)[0]
    return df


def verdicts(df):
    k1 = {t: df.loc[t, "val_sharpe"] > 0 and df.loc[t, "val_sharpe"] > df.loc["UB02", "val_sharpe"] for t in tids}
    out = {}
    for t, h, _, _ in trials:
        r, f = df.loc[t], []
        if not k1[t]:
            f.append("K1")
        if r["dsr"] < 0.95:
            f.append("K2")
        if r["ret_x1"] > 0 and r["ret_x2"] <= 0:
            f.append("K3")
        if not (r["k4_count"] >= 30 or r["median_hold"] > 63):
            f.append("K4")
        if not k1[[o for o, hh, _, _ in trials if hh == h and o != t][0]]:
            f.append("K5")
        if r["val_sharpe"] < 0.5 * r["is_sharpe"]:
            f.append("K6")
        if any(r["min_" + s] <= 2000 for s in STRESS):
            f.append("K7")
        out[t] = f
    return out


v1, v2 = table("v1"), table("v2")
assert np.allclose(v1.loc[tids, "val_sharpe"].astype(float), frozen.loc[tids, "val_sharpe"].astype(float), atol=1e-9), \
    "v1 no longer reproduces the official study-1 results"
k1, k2 = verdicts(v1), verdicts(v2)
changed = [t for t in tids if bool(k1[t]) != bool(k2[t])]

L = ["# %s: USD/JPY study 1 targets\n" % LABEL,
     "_Run %s. Engine v2: `%s`. **Diagnostic only: not new trials, no N increase, no verdict changes.** The official "
     "results stay as in `usdjpy/study1_kill_table.md`; v1 reproduced them exactly (checked by assertion)._\n" % (NOW, ENGINE_VERSION),
     "## Answer first\n",
     "- **Would any frozen kill verdict differ under engine v2? %s.** %s" % (
         "YES" if changed else "NO", ("Differences: %s." % ", ".join(changed)) if changed else
         "All 8 trials are killed under both engines."),
     "- **Sizing (D1):** always-long held %.2fx of equity on average under v1 (%.2fx at the end of 2023) and %.2fx under v2 "
     "(%.2fx at the end)." % (v1.loc["UB02", "mean_abs_expo_held"], v1.loc["UB02", "expo_end"],
                               v2.loc["UB02", "mean_abs_expo_held"], v2.loc["UB02", "expo_end"]),
     "- **K4 counting (D2):** v1's frozen count included cap trims; v2 counts only open/close/reverse (table 2).",
     "- **Always-long validation Sharpe:** %.2f (v1) vs %.2f (v2). Best trial Deflated Sharpe at N = 142: %.2f (v1, %s) vs "
     "%.2f (v2, %s); the bar is 0.95.\n" % (v1.loc["UB02", "val_sharpe"], v2.loc["UB02", "val_sharpe"],
                                            v1.loc[tids, "dsr"].max(), v1.loc[tids, "dsr"].astype(float).idxmax(),
                                            v2.loc[tids, "dsr"].max(), v2.loc[tids, "dsr"].astype(float).idxmax()),
     "## 1. Per trial, validation 2015–2023, 1x costs\n",
     "| ID | Val Sharpe v1 | Val Sharpe v2 | DSR v1 | DSR v2 | Mean exposure held v1 / v2 | Criteria failed v1 | Criteria failed v2 |",
     "|---|---|---|---|---|---|---|---|"]
for t in tids:
    L.append("| %s | %.2f | %.2f | %.3f | %.3f | %.2fx / %.2fx | %s | %s |" % (
        t, v1.loc[t, "val_sharpe"], v2.loc[t, "val_sharpe"], v1.loc[t, "dsr"], v2.loc[t, "dsr"],
        v1.loc[t, "mean_abs_expo_held"], v2.loc[t, "mean_abs_expo_held"], ", ".join(k1[t]) or "-", ", ".join(k2[t]) or "-"))
L.append("| UB02 | %.2f | %.2f | — | — | %.2fx / %.2fx | benchmark | benchmark |" % (
    v1.loc["UB02", "val_sharpe"], v2.loc["UB02", "val_sharpe"], v1.loc["UB02", "mean_abs_expo_held"], v2.loc["UB02", "mean_abs_expo_held"]))
L += ["\n## 2. Trades, 1991–2023 (in-sample + validation)\n",
      "| ID | v1 trades (frozen K4 count) | v1 true direction changes | v2 open/close/reverse | v2 re-sizes | v2 cap trims | "
      "Costs v1 / v2 (USD) | Max exposure v1 / v2 |", "|---|---|---|---|---|---|---|---|"]
for t in tids + ["UB02"]:
    a, b = v1.loc[t], v2.loc[t]
    kb = b["kinds"]
    L.append("| %s | %d | %d | %d | %d | %d | %.0f / %.0f | %.2fx / %.2fx |" % (
        t, a["k4_count"], a["true_changes"], kb["open"] + kb["close"] + kb["reverse"], kb["resize"], kb["cap_trim"],
        a["costs_usd"], b["costs_usd"], a["max_abs_expo"], b["max_abs_expo"]))
L += ["\n## Notes\n",
      "- v2 settings (this run; not the later defaults): re-size to the target at every weekly decision (band 0), strict cap 1x at every close (cap_tolerance 0), same costs "
      "(0.015% one-way, 0.75%/yr rollover markup), same lag (1 FX day), same data and rates (DTB3, JGB 1Y proxy).",
      "- A re-size or cap trim pays costs on the traded amount; v2's higher trade count is mostly small re-sizes.",
      "- v2's daily P&L differs from v1 even with identical exposure because v1 re-sizes the yen leg every day for free "
      "(D3); over one day after entry the two engines agree (unit test).",
      "- Criteria lists are applied mechanically for this diagnostic only; they are not new verdicts."]
out = PROJECT_ROOT / "reports" / "specialists" / "fx_engine_v2_comparison.md"
out.write_text("\n".join(L) + "\n")

with open(PROJECT_ROOT / "research_log.csv", "a", newline="") as fh:
    w = csv.writer(fh)
    for t in tids + ["UB02"]:
        r = v2.loc[t]
        w.writerow([t, NOW, "fx-engine-v2-diagnostic", LABEL, "USDJPY", "USDJPY", "engine v2; weekly re-size to target; band 0",
                    "%s..%s" % (VA0, VA1), 1, "", "", "%.4f" % r["val_sharpe"], "", int(r["true_changes"]), "DIAGNOSTIC", "",
                    "not a trial; no N increase; official verdict unchanged" + ("; DSR(N=142)=%.4f" % r["dsr"] if t != "UB02" else "")])
led = Ledger(RESEARCH)
led.append("result", {"market": "usdjpy", "label": LABEL, "engine": ENGINE_VERSION,
                      "verdict_would_differ_under_v2": changed,
                      "val_sharpe_v1": {t: round(float(v1.loc[t, "val_sharpe"]), 4) for t in tids + ["UB02"]},
                      "val_sharpe_v2": {t: round(float(v2.loc[t, "val_sharpe"]), 4) for t in tids + ["UB02"]},
                      "dsr_v2": {t: round(float(v2.loc[t, "dsr"]), 4) for t in tids},
                      "always_long_mean_exposure": {"v1": round(float(v1.loc["UB02", "mean_abs_expo_held"]), 3),
                                                    "v2": round(float(v2.loc["UB02", "mean_abs_expo_held"]), 3)},
                      "note": "diagnostic only; official results unchanged; v2 is for future pre-registered experiments",
                      "report": str(out.relative_to(PROJECT_ROOT))})
assert led.verify() is None
print("\n".join(L))
