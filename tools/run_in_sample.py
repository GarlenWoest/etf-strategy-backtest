"""Phase 4: run all 92 frozen trials and the 9 benchmarks on in-sample data only.

Signals use clean data from dates.common_start (warm-up). Evaluation runs from
dates.evaluation_start to dates.in_sample_end at 1x costs with the risk layer off
(validation.phase5_risk_layer = false). Every variant is appended to research_log.csv,
equity curves go to results/phase4_in_sample_equity.csv (not tracked), and the summary
goes to reports/phase4_in_sample.md.

Usage: .venv/bin/python tools/run_in_sample.py
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
from src import metrics as M
from src import strategies as S
from src.engine import run_backtest

cfg = load_config()
assert cfg["dates"]["holdout_locked"]
START, END = cfg["dates"]["evaluation_start"], cfg["dates"]["in_sample_end"]
ALL = S.UNLEV + [S.LEV[t] for t in S.UNLEV]
prices = {t: D.load_clean(t).loc[:END] for t in ALL}           # nothing after the in-sample end is loaded
cash = D.load_cash().loc[:END]
closes = pd.DataFrame({t: prices[t]["Close"] for t in S.UNLEV})
risk_on = cfg["validation"]["phase5_risk_layer"]


def evaluate(targets, rebalance=None):
    r = run_backtest(prices, targets, cash, cfg, rebalance=rebalance, risk_layer=risk_on, start=START, end=END)
    e = r.equity
    order_days = r.trades["date"].nunique() if len(r.trades) else 0
    return e, {"cagr": M.cagr(e), "ann_vol": M.ann_vol(e), "sharpe": M.sharpe(e, cash), "max_drawdown": M.max_drawdown(e),
               "n_trades": int(order_days), "time_in_market": float((r.exposure > 0.01).mean())}


now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
rows, curves = [], {}
idx = closes.index
bench = [("B%02d" % (i + 1), "buy_and_hold", t, t, S.buy_and_hold(idx, t).reindex(columns=ALL, fill_value=0.0), None)
         for i, t in enumerate(ALL)]
w, flag = S.equal_weight(idx, S.UNLEV)
bench.append(("B09", "buy_and_hold_equal_weight", "GLD|SPY|QQQ|TLT", "GLD|SPY|QQQ|TLT",
              w.reindex(columns=ALL, fill_value=0.0), flag))
for tid, strat, sig, trade, tg, reb in bench:
    e, m = evaluate(tg, reb)
    curves[tid] = e
    rows.append(dict(test_id=tid, strategy=strat, signal_instrument=sig, trade_instrument=trade, params="", **m))
for v in S.build_variants(closes):
    e, m = evaluate(v.targets, v.rebalance)
    curves[v.test_id] = e
    rows.append(dict(test_id=v.test_id, strategy=v.strategy, signal_instrument=v.signal_instrument,
                     trade_instrument=v.trade_instrument, params=v.params, **m))

# research log: one row per variant, nothing skipped
period = "%s..%s" % (START, END)
with open(PROJECT_ROOT / "research_log.csv", "a", newline="") as fh:
    wr = csv.writer(fh)
    for r in rows:
        wr.writerow([r["test_id"], now, "4-in-sample", r["strategy"], r["signal_instrument"], r["trade_instrument"],
                     r["params"], period, 1, "%.6f" % r["cagr"], "%.6f" % r["ann_vol"], "%.4f" % r["sharpe"],
                     "%.6f" % r["max_drawdown"], r["n_trades"], "IN-SAMPLE-RUN", "",
                     "risk layer off; n_trades = days with fills; time_in_market=%.3f" % r["time_in_market"]])

out = PROJECT_ROOT / "results"
out.mkdir(exist_ok=True)
pd.DataFrame(curves).to_csv(out / "phase4_in_sample_equity.csv", index_label="Date")

df = pd.DataFrame(rows)
L = []
w_ = L.append
w_("# Phase 4: in-sample results (tuning data only)\n")
w_("_Run %s. Window %s to %s (%.2f years); signals warm up from %s. 1x costs, $100 start, risk layer off. "
   "Python %s, pandas %s, numpy %s. No random numbers used._\n"
   % (now, START, END, M.years(curves["B01"].index), cfg["dates"]["common_start"], platform.python_version(),
      pd.__version__, np.__version__))
w_("**These are in-sample numbers: the data any tuning would be done on.** They are not evidence of an edge. "
   "Nothing is selected or killed here. Phase 5 adds validation (2019–2023), walk-forward, the full metric set, "
   "the Deflated Sharpe Ratio, and the 2x/3x cost runs. Sharpe is the annualized excess return over T-bills.\n")
w_("`n_trades` = number of days with at least one fill (entries, exits, switches and rebalances). The Phase 6 "
   "30-trade rule will count completed round trips; that count is added in Phase 5.\n")
w_("## Benchmarks\n")
w_("| ID | Instrument | CAGR | Vol | Sharpe | Max DD |\n|---|---|---|---|---|---|")
for r in rows[:9]:
    w_("| %s | %s | %.2f%% | %.1f%% | %.2f | %.1f%% |" % (r["test_id"], r["trade_instrument"], r["cagr"] * 100,
                                                      r["ann_vol"] * 100, r["sharpe"], r["max_drawdown"] * 100))
w_("\n## All 92 trials\n")
w_("| ID | Strategy | Signal | Trades in | Params | CAGR | Vol | Sharpe | Max DD | Fill days | In market |")
w_("|---|---|---|---|---|---|---|---|---|---|---|")
for r in rows[9:]:
    w_("| %s | %s | %s | %s | %s | %.2f%% | %.1f%% | %.2f | %.1f%% | %d | %.0f%% |" % (
        r["test_id"], r["strategy"], r["signal_instrument"], r["trade_instrument"], r["params"], r["cagr"] * 100,
        r["ann_vol"] * 100, r["sharpe"], r["max_drawdown"] * 100, r["n_trades"], r["time_in_market"] * 100))
fam = df.iloc[9:].groupby("strategy")[["cagr", "sharpe", "max_drawdown"]].agg(["median", "min", "max"])
w_("\n## By family (median / min / max over each family's variants)\n")
w_("| Family | CAGR median | CAGR range | Sharpe median | Sharpe range | Max DD median | Worst Max DD |")
w_("|---|---|---|---|---|---|---|")
for name, f in fam.iterrows():
    w_("| %s | %.2f%% | %.2f%% to %.2f%% | %.2f | %.2f to %.2f | %.1f%% | %.1f%% |" % (
        name, f[("cagr", "median")] * 100, f[("cagr", "min")] * 100, f[("cagr", "max")] * 100,
        f[("sharpe", "median")], f[("sharpe", "min")], f[("sharpe", "max")], f[("max_drawdown", "median")] * 100,
        f[("max_drawdown", "min")] * 100))
(PROJECT_ROOT / "reports" / "phase4_in_sample.md").write_text("\n".join(L) + "\n")
print("variants run:", len(rows) - 9, "benchmarks:", 9)
