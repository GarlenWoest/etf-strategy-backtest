"""Phase 5: validation of all 92 frozen trials (no tuning on validation data).

  1. One continuous run per variant and benchmark, evaluation_start..validation_end, at 1x/2x/3x costs,
     risk layer off. Windows are sliced from these runs.
  2. In-sample (2006-01-03..2018-12-31) and validation (2019-01-01..2023-12-31) metrics.
  3. Walk-forward per strategy group: tune on the prior 5 calendar years, test on the next year,
     2011..2023, stitched.
  4. Bootstrap 95% CI of validation Sharpe (10,000 resamples, fixed seed) and the Deflated Sharpe
     Ratio with N = 92 (also shown with the correlation-based effective N, for information).
  5. Cost sensitivity, stress periods, worst day/month, parameter heatmaps.
  6. Suspect-price sensitivity: every variant rerun with the suspect closes interpolated.
Outputs: reports/phase5_validation.md, reports/phase5_heatmap_*.png, results/phase5_metrics.csv,
rows appended to research_log.csv.

Usage: .venv/bin/python tools/run_phase5.py
"""
import copy
import csv
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from src import PROJECT_ROOT, load_config
from src import data as D
from src import metrics as M
from src import strategies as S
from src import validate as V
from src.engine import run_backtest

cfg = load_config()
dates = cfg["dates"]
assert dates["holdout_locked"]
EVAL, IS_END = dates["evaluation_start"], dates["in_sample_end"]
VAL_START, VAL_END = dates["validation_start"], dates["validation_end"]
SEED = int(cfg["project"]["random_seed"])
N_TRIALS = int(cfg["strategies"]["total_trials"])
ALL = S.UNLEV + [S.LEV[t] for t in S.UNLEV]
LEVSET = set(S.LEV.values())
RISK = cfg["validation"]["phase5_risk_layer"]
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
REP = PROJECT_ROOT / "reports"
RES = PROJECT_ROOT / "results"
RES.mkdir(exist_ok=True)

prices = {t: D.load_clean(t).loc[:VAL_END] for t in ALL}
assert max(p.index.max() for p in prices.values()) < pd.Timestamp(dates["holdout_start"])
cash = D.load_cash().loc[:VAL_END]


def variants_for(px):
    closes = pd.DataFrame({t: px[t]["Close"] for t in S.UNLEV})
    vs = S.build_variants(closes)
    idx = closes.index
    bench = []
    for i, t in enumerate(ALL):
        bench.append(S.Variant("B%02d" % (i + 1), "buy_and_hold", t, t, "",
                               S.buy_and_hold(idx, t).reindex(columns=ALL, fill_value=0.0)))
    w, flag = S.equal_weight(idx, S.UNLEV)
    bench.append(S.Variant("B09", "buy_and_hold_equal_weight", "GLD|SPY|QQQ|TLT", "GLD|SPY|QQQ|TLT", "",
                           w.reindex(columns=ALL, fill_value=0.0), flag))
    return bench, vs


def run(px, v, mult=1.0):
    return run_backtest(px, v.targets, cash, cfg, rebalance=v.rebalance, cost_mult=mult, risk_layer=RISK,
                        start=EVAL, end=VAL_END)


bench, vs = variants_for(prices)
everything = bench + vs
print("running %d series x 3 cost levels" % len(everything))
res = {m: {} for m in (1, 2, 3)}
for m in (1, 2, 3):
    for v in everything:
        res[m][v.test_id] = run(prices, v, m)
episodes = {v.test_id: V.trade_episodes(res[1][v.test_id], prices) for v in everything}

# ---------------------------------------------------------------- window metrics
rows = {}
for v in everything:
    r1 = res[1][v.test_id]
    d = {"test_id": v.test_id, "strategy": v.strategy, "signal": v.signal_instrument, "trade": v.trade_instrument,
         "params": v.params}
    for tag, a, b in (("is", EVAL, IS_END), ("val", VAL_START, VAL_END)):
        mm = V.window_metrics(r1, prices, cash, a, b, episodes[v.test_id])
        d.update({"%s_%s" % (tag, k): val for k, val in mm.items()})
    for m in (2, 3):
        e = V.period_path(res[m][v.test_id].equity, VAL_START, VAL_END)
        d["val_cagr_x%d" % m] = M.cagr(e)
        d["val_sharpe_x%d" % m] = M.sharpe(e, cash)
        d["val_total_return_x%d" % m] = float(e.iloc[-1] / e.iloc[0] - 1)
    rows[v.test_id] = d
df = pd.DataFrame(rows.values()).set_index("test_id")

# ---------------------------------------------------------------- benchmarks per variant
bh = {v.trade_instrument: v.test_id for v in bench if v.strategy == "buy_and_hold"}
EW = "B09"


def own_benchmarks(v):
    """Buy-and-hold IDs of the same instrument(s): signal ETF and traded ETF; multi-asset -> equal weight."""
    if "|" in v.signal_instrument:
        return [EW]
    traded = [t for t in v.trade_instrument.split("|") if t in bh]
    return sorted(set([bh[v.signal_instrument]] + [bh[t] for t in traded]))


df["own_bench"] = ""
for v in vs:
    ob = own_benchmarks(v)
    df.at[v.test_id, "own_bench"] = ",".join(ob)
    df.at[v.test_id, "own_bench_val_sharpe"] = max(df.loc[b, "val_sharpe"] for b in ob)
    df.at[v.test_id, "own_bench_is_sharpe"] = max(df.loc[b, "is_sharpe"] for b in ob)
ew_val, ew_is = df.loc[EW, "val_sharpe"], df.loc[EW, "is_sharpe"]
spy_val = df.loc[bh["SPY"], "val_sharpe"]

# ---------------------------------------------------------------- daily OOS returns, bootstrap, DSR
def daily_val_returns(tid, m=1):
    e = V.period_path(res[m][tid].equity, VAL_START, VAL_END)
    return e.pct_change().dropna()


val_ret = pd.DataFrame({v.test_id: daily_val_returns(v.test_id) for v in vs})
rf = cash.shift(1).reindex(val_ret.index).fillna(0.0)
val_ex = val_ret.sub(rf, axis=0)
daily_sr = val_ex.mean() / val_ex.std(ddof=1)
n_eff = V.effective_trials(val_ret.to_numpy())
for k, v in enumerate(vs):
    x = val_ex[v.test_id].to_numpy()
    lo, hi = V.bootstrap_sharpe_ci(x, int(cfg["validation"]["bootstrap"]["resamples"]), SEED + k)
    dsr, sr0 = V.deflated_sharpe(x, daily_sr.to_numpy(), N_TRIALS)
    dsr_eff, sr0_eff = V.deflated_sharpe(x, daily_sr.to_numpy(), max(2, int(round(n_eff))))
    df.loc[v.test_id, ["val_sharpe_ci_lo", "val_sharpe_ci_hi", "dsr", "dsr_hurdle_ann", "dsr_eff_n",
                       "dsr_eff_hurdle_ann"]] = [lo, hi, dsr, sr0 * np.sqrt(252), dsr_eff, sr0_eff * np.sqrt(252)]

# ---------------------------------------------------------------- walk-forward per group
groups = {}
for v in vs:
    key = (v.strategy, v.signal_instrument, v.trade_instrument)
    groups.setdefault(key, []).append(v.test_id)
first_wf, last_wf = int(EVAL[:4]) + int(cfg["validation"]["walk_forward"]["train_years"]), int(VAL_END[:4])
wf_rows = []
full_ret = {tid: res[1][tid].equity.pct_change().dropna() for tid in res[1]}
for key, ids in groups.items():
    rets = pd.DataFrame({tid: full_ret[tid] for tid in ids})
    if len(ids) > 1:
        st, chosen = V.walk_forward(rets, cash, first_wf, last_wf, int(cfg["validation"]["walk_forward"]["train_years"]))
    else:
        st = rets[ids[0]].loc["%d-01-01" % first_wf:]
        chosen = {y: ids[0] for y in range(first_wf, last_wf + 1)}
    eq = 100 * (1 + st).cumprod()
    bids = own_benchmarks(next(v for v in vs if v.test_id == ids[0]))
    bsh = max(V.sharpe_from_returns(full_ret[b].loc["%d-01-01" % first_wf:], cash) for b in bids)
    wf_rows.append({"group": "%s %s->%s" % key, "ids": ",".join(ids), "wf_sharpe": V.sharpe_from_returns(st, cash),
                    "wf_cagr": float((1 + st).prod() ** (252 / len(st)) - 1), "wf_max_dd": M.max_drawdown(eq),
                    "own_bench_sharpe": bsh,
                    "ew_sharpe": V.sharpe_from_returns(full_ret[EW].loc["%d-01-01" % first_wf:], cash),
                    "chosen": " ".join("%d:%s" % (y, c) for y, c in chosen.items())})
wf = pd.DataFrame(wf_rows)

# ---------------------------------------------------------------- stress periods, worst day / month
spy_vol = {y: float(res[1][bh["SPY"]].equity.loc[str(y)].pct_change().std() * np.sqrt(252))
           for y in range(int(EVAL[:4]), int(VAL_END[:4]) + 1)}
calm = sorted(spy_vol, key=spy_vol.get)[:3]
stress = {"2008": ("2008-01-01", "2008-12-31"), "covid_2020": tuple(cfg["validation"]["stress_periods"]["covid_crash_2020"]),
          "2022": ("2022-01-01", "2022-12-31")}
for y in calm:
    stress["calm_%d" % y] = ("%d-01-01" % y, "%d-12-31" % y)
for v in everything:
    e = res[1][v.test_id].equity
    for name, (a, b) in stress.items():
        p = V.period_path(e, a, b)
        df.loc[v.test_id, "stress_%s_return" % name] = float(p.iloc[-1] / 100 - 1)
        df.loc[v.test_id, "stress_%s_min_value" % name] = float(p.min())
        df.loc[v.test_id, "stress_%s_max_dd" % name] = M.max_drawdown(p)
    dr = e.pct_change().dropna()
    mr = e.resample("ME").last().pct_change().dropna()
    df.loc[v.test_id, ["worst_day", "worst_day_date", "worst_month", "worst_month_date"]] = [
        float(dr.min()), str(dr.idxmin().date()), float(mr.min()), str(mr.idxmin().strftime("%Y-%m"))]

# ---------------------------------------------------------------- suspect-price sensitivity
px2 = {t: p.copy() for t, p in prices.items()}
for t, (a, b) in cfg["data"]["suspect_prices"].items():
    px2[t] = D.interpolate_suspects(prices[t], a, b)
_, vs2 = variants_for(px2)
for v in vs2:
    r = run(px2, v)
    for tag, a, b in (("is", EVAL, IS_END), ("val", VAL_START, VAL_END)):
        p = V.period_path(r.equity, a, b)
        df.loc[v.test_id, "interp_%s_sharpe" % tag] = M.sharpe(p, cash)
        df.loc[v.test_id, "interp_%s_cagr" % tag] = M.cagr(p)
for tag in ("is", "val"):
    df["interp_%s_sharpe_diff" % tag] = df["interp_%s_sharpe" % tag] - df["%s_sharpe" % tag]

df.to_csv(RES / "phase5_metrics.csv")
wf.to_csv(RES / "phase5_walk_forward.csv", index=False)

# heatmaps are drawn by tools/make_phase5_report.py from results/phase5_metrics.csv
heatmaps = []

# ---------------------------------------------------------------- research log
with open(PROJECT_ROOT / "research_log.csv", "a", newline="") as fh:
    w = csv.writer(fh)
    for v in everything:
        r = df.loc[v.test_id]
        for m in (1, 2, 3):
            cg = r["val_cagr"] if m == 1 else r["val_cagr_x%d" % m]
            sh = r["val_sharpe"] if m == 1 else r["val_sharpe_x%d" % m]
            note = "risk layer off; n_trades = round trips exiting in window"
            if m == 1 and v.test_id.startswith("V"):
                note += "; DSR(N=92)=%.4f; boot95=[%.3f,%.3f]" % (r["dsr"], r["val_sharpe_ci_lo"], r["val_sharpe_ci_hi"])
            w.writerow([v.test_id, NOW, "5-validation", v.strategy, v.signal_instrument, v.trade_instrument, v.params,
                        "%s..%s" % (VAL_START, VAL_END), m, "%.6f" % cg, "%.6f" % r["val_ann_vol"] if m == 1 else "",
                        "%.4f" % sh, "%.6f" % r["val_max_drawdown"] if m == 1 else "",
                        int(r["val_n_round_trips"]) if m == 1 else "", "VALIDATION-RUN", "", note])
    for _, g in wf.iterrows():
        w.writerow(["WF:" + g["ids"], NOW, "5-walk-forward", g["group"], "", "", "train 5y, test 1y",
                    "%d..%d" % (first_wf, last_wf), 1, "%.6f" % g["wf_cagr"], "", "%.4f" % g["wf_sharpe"],
                    "%.6f" % g["wf_max_dd"], "", "WALK-FORWARD-RUN", "", "chosen " + g["chosen"]])
    for v in vs:
        r = df.loc[v.test_id]
        w.writerow([v.test_id, NOW, "5-suspect-sensitivity", v.strategy, v.signal_instrument, v.trade_instrument,
                    v.params, "%s..%s" % (EVAL, VAL_END), 1, "", "", "%.4f" % r["interp_val_sharpe"], "", "",
                    "SENSITIVITY-RUN", "", "suspect closes interpolated; is_sharpe diff %+.4f, val_sharpe diff %+.4f"
                    % (r["interp_is_sharpe_diff"], r["interp_val_sharpe_diff"])])
print("done; N_eff = %.1f" % n_eff)
pd.to_pickle({"n_eff": n_eff, "calm": calm, "spy_vol": spy_vol, "first_wf": first_wf, "last_wf": last_wf,
              "now": NOW, "ew_val": ew_val, "ew_is": ew_is, "spy_val": spy_val, "heatmaps": heatmaps,
              "stress": stress}, RES / "phase5_meta.pkl")
