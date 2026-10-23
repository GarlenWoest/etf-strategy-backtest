"""Commodity study, Phases 4-6, for the 26 trials pre-registered as V093-V118 (commit a696506).

The method and kill criteria are those of the ETF study (tools/run_in_sample.py, run_phase5.py, run_phase6.py),
unchanged:
  Phase 4  in-sample run (commodity_study.evaluation_start .. dates.in_sample_end), 1x costs, risk layer off.
  Phase 5  one continuous run per series to dates.validation_end at 1x/2x/3x costs; IS and validation metrics,
           walk-forward (5y train / 1y test), bootstrap CI (10,000, seed + index), Deflated Sharpe with
           N = 118 (cumulative), stress periods, suspect-price sensitivity (UGL window).
  Phase 6  K1-K7 applied mechanically.
K1 "equal weight" for this study = CB08 (equal weight GLD/SLV/USO, monthly), the analogue of the ETF study's B09.
DSR cross-trial variance = variance of daily validation Sharpe ratios of all 118 trials (92 from
results/phase5_metrics.csv). Every result that uses oil carries the USO April-2020 flag.

Usage: .venv/bin/python tools/run_commodities.py --phase 4|5|6
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
from src import commodities as CM
from src import data as D
from src import metrics as M
from src import validate as V
from src.engine import run_backtest

base = load_config()
cfg = CM.study_cfg(base)
dates = cfg["dates"]
assert dates["holdout_locked"]
cs = cfg["commodity_study"]
EVAL, IS_END = cs["evaluation_start"], dates["in_sample_end"]
VS, VE = dates["validation_start"], dates["validation_end"]
N_CUM = int(cs["cumulative_trials_for_dsr"])
SEED = int(cfg["project"]["random_seed"])
RISK = cfg["validation"]["phase5_risk_layer"]
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
REP, RES = PROJECT_ROOT / "reports", PROJECT_ROOT / "results"
RES.mkdir(exist_ok=True)
MONTHLY = set(cs["monthly_for_k4"])
EW, MIX = "CB08", "CB09"
LOG = PROJECT_ROOT / "research_log.csv"


def series(end):
    px = CM.load_prices(cfg, end=end)
    cash = D.load_cash(cfg).loc[:end]
    closes = pd.DataFrame({t: px[t]["Close"] for t in CM.UNLEV})
    vs = CM.build_variants(closes, cash)
    with open(LOG, newline="") as fh:
        reg = [r for r in csv.DictReader(fh) if r["phase"] == "9-freeze" and r["result"] == "PRE-REGISTERED"]
    assert [(v.test_id, v.strategy, v.signal_instrument, v.trade_instrument, v.params) for v in vs] == \
        [(r["test_id"], r["strategy"], r["signal_instrument"], r["trade_instrument"], r["params"]) for r in reg]
    return px, cash, CM.benchmarks(closes.index), vs


def note(v, extra=""):
    parts = [extra] if extra else []
    if CM.uses_oil(v):
        parts.append("OIL FLAG: " + CM.USO_FLAG)
    return "; ".join(parts)


def run(px, cash, v, mult=1.0, end=VE):
    return run_backtest(px, v.targets, cash, cfg, rebalance=v.rebalance, cost_mult=mult, risk_layer=RISK,
                        start=EVAL, end=end)


def short(params):
    """Grid parameters only (drop the fixed parts of the label)."""
    keep = [p for p in params.split(";") if "=" in p and not p.startswith(("fast=", "ewmac"))]
    return ";".join(keep)


def oilmark(v):
    return " ⚑" if CM.uses_oil(v) else ""


# ================================================================ Phase 4
def phase4():
    px, cash, bench, vs = series(IS_END)
    rows = []
    for v in bench + vs:
        r = run(px, cash, v, end=IS_END)
        e = r.equity
        rows.append(dict(v=v, cagr=M.cagr(e), vol=M.ann_vol(e), sharpe=M.sharpe(e, cash), mdd=M.max_drawdown(e),
                         fills=int(r.trades["date"].nunique()) if len(r.trades) else 0,
                         inmkt=float((r.exposure > 0.01).mean())))
    with open(LOG, "a", newline="") as fh:
        w = csv.writer(fh)
        for x in rows:
            v = x["v"]
            w.writerow([v.test_id, NOW, "9-4-in-sample", v.strategy, v.signal_instrument, v.trade_instrument, v.params,
                        "%s..%s" % (EVAL, IS_END), 1, "%.6f" % x["cagr"], "%.6f" % x["vol"], "%.4f" % x["sharpe"],
                        "%.6f" % x["mdd"], x["fills"], "IN-SAMPLE-RUN", "",
                        note(v, "risk layer off; n_trades = days with fills; time_in_market=%.3f" % x["inmkt"])])
    L = ["# Commodity study, Phase 4: in-sample results (tuning data only)\n",
         "_Run %s. Window %s to %s; signals warm up from %s. 1x costs, $100 start, risk layer off. Python %s, "
         "pandas %s, numpy %s._\n" % (NOW, EVAL, IS_END, cs["calendar_start"], platform.python_version(),
                                      pd.__version__, np.__version__),
         "**In-sample numbers are not evidence of an edge.** Nothing is selected or killed here. ⚑ = uses oil: "
         + CM.USO_FLAG + " (the change falls in the validation window, not here).\n",
         "AGQ and UCO are synthetic before their launch (Dec 2008), calibrated on in-sample overlap only; see "
         "`data/clean/commodities/build_meta.json`.\n",
         "| ID | Strategy | Trades in | Params | CAGR | Vol | Sharpe | Max DD | Fill days | In market |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for x in rows:
        v = x["v"]
        L.append("| %s | %s | %s%s | %s | %.2f%% | %.1f%% | %.2f | %.1f%% | %d | %.0f%% |" % (
            v.test_id, v.strategy, v.trade_instrument.replace("|", "/"), oilmark(v), v.params.replace("|", "/"),
            100 * x["cagr"], 100 * x["vol"], x["sharpe"], 100 * x["mdd"], x["fills"], 100 * x["inmkt"]))
    (REP / "commodities_phase4_in_sample.md").write_text("\n".join(L) + "\n")
    print("phase 4 done:", len(vs), "trials,", len(bench), "benchmarks")


# ================================================================ Phase 5
def own_benchmarks(v, bh):
    if "|" in v.signal_instrument:
        return [EW]
    traded = [t for t in v.trade_instrument.split("|") if t in bh]
    return sorted(set([bh["GLD"]] + [bh[t] for t in traded]))   # signal ETF is GLD for every single-asset trial


def phase5():
    px, cash, bench, vs = series(VE)
    everything = bench + vs
    res = {m: {v.test_id: run(px, cash, v, m) for v in everything} for m in (1, 2, 3)}
    episodes = {v.test_id: V.trade_episodes(res[1][v.test_id], px) for v in everything}
    rows = {}
    for v in everything:
        r1 = res[1][v.test_id]
        d = {"test_id": v.test_id, "strategy": v.strategy, "signal": v.signal_instrument, "trade": v.trade_instrument,
             "params": v.params, "oil_flag": CM.uses_oil(v)}
        for tag, a, b in (("is", EVAL, IS_END), ("val", VS, VE)):
            d.update({"%s_%s" % (tag, k): x for k, x in V.window_metrics(r1, px, cash, a, b, episodes[v.test_id]).items()})
        for m in (2, 3):
            e = V.period_path(res[m][v.test_id].equity, VS, VE)
            d["val_cagr_x%d" % m], d["val_sharpe_x%d" % m] = M.cagr(e), M.sharpe(e, cash)
            d["val_total_return_x%d" % m] = float(e.iloc[-1] / e.iloc[0] - 1)
        rows[v.test_id] = d
    df = pd.DataFrame(rows.values()).set_index("test_id")
    bh = {v.trade_instrument: v.test_id for v in bench if v.strategy == "buy_and_hold"}
    for v in vs:
        ob = own_benchmarks(v, bh)
        df.loc[v.test_id, "own_bench"] = ",".join(ob)
        df.loc[v.test_id, "own_bench_val_sharpe"] = max(df.loc[b, "val_sharpe"] for b in ob)
        df.loc[v.test_id, "own_bench_is_sharpe"] = max(df.loc[b, "is_sharpe"] for b in ob)

    # ---- DSR at cumulative N, variance over all 118 trials
    val_ret = pd.DataFrame({v.test_id: V.period_path(res[1][v.test_id].equity, VS, VE).pct_change().dropna() for v in vs})
    rf = cash.shift(1).reindex(val_ret.index).fillna(0.0)
    val_ex = val_ret.sub(rf, axis=0)
    daily_sr_new = val_ex.mean() / val_ex.std(ddof=1)
    old = pd.read_csv(RES / "phase5_metrics.csv", index_col=0)
    old_sr = old.loc[old.index.str.startswith("V"), "val_sharpe"] / np.sqrt(252)
    assert len(old_sr) == 92
    all_sr = np.r_[old_sr.to_numpy(), daily_sr_new.to_numpy()]
    assert len(all_sr) == N_CUM
    n_eff = V.effective_trials(val_ret.to_numpy())
    for k, v in enumerate(vs):
        x = val_ex[v.test_id].to_numpy()
        lo, hi = V.bootstrap_sharpe_ci(x, int(cfg["validation"]["bootstrap"]["resamples"]), SEED + 92 + k)
        dsr, sr0 = V.deflated_sharpe(x, all_sr, N_CUM)
        dsr26, sr026 = V.deflated_sharpe(x, daily_sr_new.to_numpy(), 26)
        df.loc[v.test_id, ["val_sharpe_ci_lo", "val_sharpe_ci_hi", "dsr", "dsr_hurdle_ann", "dsr_n26", "dsr_n26_hurdle_ann"]] = \
            [lo, hi, dsr, sr0 * np.sqrt(252), dsr26, sr026 * np.sqrt(252)]

    # ---- walk-forward per group
    groups = {}
    for v in vs:
        groups.setdefault((v.strategy, v.signal_instrument, v.trade_instrument), []).append(v.test_id)
    ty = int(cfg["validation"]["walk_forward"]["train_years"])
    first_wf, last_wf = int(EVAL[:4]) + ty, int(VE[:4])
    full_ret = {tid: res[1][tid].equity.pct_change().dropna() for tid in res[1]}
    wf_rows = []
    for key, ids in groups.items():
        rets = pd.DataFrame({tid: full_ret[tid] for tid in ids})
        st, chosen = V.walk_forward(rets, cash, first_wf, last_wf, ty) if len(ids) > 1 else \
            (rets[ids[0]].loc["%d-01-01" % first_wf:], {y: ids[0] for y in range(first_wf, last_wf + 1)})
        eq = 100 * (1 + st).cumprod()
        vv = next(v for v in vs if v.test_id == ids[0])
        bsh = max(V.sharpe_from_returns(full_ret[b].loc["%d-01-01" % first_wf:], cash) for b in own_benchmarks(vv, bh))
        wf_rows.append({"group": "%s %s->%s" % key, "ids": ",".join(ids), "wf_sharpe": V.sharpe_from_returns(st, cash),
                        "wf_cagr": float((1 + st).prod() ** (252 / len(st)) - 1), "wf_max_dd": M.max_drawdown(eq),
                        "own_bench_sharpe": bsh,
                        "ew_sharpe": V.sharpe_from_returns(full_ret[EW].loc["%d-01-01" % first_wf:], cash),
                        "mix_sharpe": V.sharpe_from_returns(full_ret[MIX].loc["%d-01-01" % first_wf:], cash),
                        "chosen": " ".join("%d:%s" % (y, c) for y, c in chosen.items()), "oil_flag": CM.uses_oil(vv)})
    wf = pd.DataFrame(wf_rows)

    # ---- stress, worst day/month
    spyv = {y: float(res[1]["CB07"].equity.loc[str(y)].pct_change().std() * np.sqrt(252))
            for y in range(int(EVAL[:4]) + 1, int(VE[:4]) + 1)}
    calm = sorted(spyv, key=spyv.get)[:3]
    sp = cfg["validation"]["stress_periods"]
    stress = {"2008": tuple(sp["gfc_2008"]), "covid_2020": tuple(sp["covid_crash_2020"]), "2022": tuple(sp["stocks_and_bonds_2022"])}
    stress.update({"calm_%d" % y: ("%d-01-01" % y, "%d-12-31" % y) for y in calm})
    for v in everything:
        e = res[1][v.test_id].equity
        for name, (a, b) in stress.items():
            p = V.period_path(e, a, b)
            df.loc[v.test_id, ["stress_%s_return" % name, "stress_%s_min_value" % name, "stress_%s_max_dd" % name]] = \
                [float(p.iloc[-1] / 100 - 1), float(p.min()), M.max_drawdown(p)]
        dr = e.pct_change().dropna()
        mr = e.resample("ME").last().pct_change().dropna()
        df.loc[v.test_id, ["worst_day", "worst_day_date", "worst_month", "worst_month_date"]] = \
            [float(dr.min()), str(dr.idxmin().date()), float(mr.min()), str(mr.idxmin().strftime("%Y-%m"))]

    # ---- suspect-price sensitivity (UGL 2018-05-18..22, unresolved since Phase 2)
    px2 = dict(px)
    for t, (a, b) in cfg["data"]["suspect_prices"].items():
        if t in px2:
            px2[t] = D.interpolate_suspects(px[t], a, b)
    for v in vs:
        r = run(px2, cash, v)
        for tag, a, b in (("is", EVAL, IS_END), ("val", VS, VE)):
            df.loc[v.test_id, "interp_%s_sharpe" % tag] = M.sharpe(V.period_path(r.equity, a, b), cash)
    for tag in ("is", "val"):
        df["interp_%s_sharpe_diff" % tag] = df["interp_%s_sharpe" % tag] - df["%s_sharpe" % tag]

    df.to_csv(RES / "commodities_phase5_metrics.csv")
    wf.to_csv(RES / "commodities_phase5_walk_forward.csv", index=False)
    pd.to_pickle({"n_eff": n_eff, "calm": calm, "first_wf": first_wf, "last_wf": last_wf, "now": NOW,
                  "stress": stress, "var_all_sr_ann": float(np.var(all_sr, ddof=1) * 252)},
                 RES / "commodities_phase5_meta.pkl")
    pd.DataFrame({tid: res[1][tid].equity for tid in res[1]}).to_csv(RES / "commodities_equity_1x.csv", index_label="Date")

    with open(LOG, "a", newline="") as fh:
        w = csv.writer(fh)
        for v in everything:
            r = df.loc[v.test_id]
            for m in (1, 2, 3):
                cg = r["val_cagr"] if m == 1 else r["val_cagr_x%d" % m]
                sh = r["val_sharpe"] if m == 1 else r["val_sharpe_x%d" % m]
                ex = "risk layer off; n_trades = round trips exiting in window"
                if m == 1 and v.test_id.startswith("V"):
                    ex += "; DSR(N=118)=%.4f; boot95=[%.3f,%.3f]" % (r["dsr"], r["val_sharpe_ci_lo"], r["val_sharpe_ci_hi"])
                w.writerow([v.test_id, NOW, "9-5-validation", v.strategy, v.signal_instrument, v.trade_instrument,
                            v.params, "%s..%s" % (VS, VE), m, "%.6f" % cg, "%.6f" % r["val_ann_vol"] if m == 1 else "",
                            "%.4f" % sh, "%.6f" % r["val_max_drawdown"] if m == 1 else "",
                            int(r["val_n_round_trips"]) if m == 1 else "", "VALIDATION-RUN", "", note(v, ex)])
        for _, g in wf.iterrows():
            w.writerow(["WF:" + g["ids"], NOW, "9-5-walk-forward", g["group"], "", "", "train 5y, test 1y",
                        "%d..%d" % (first_wf, last_wf), 1, "%.6f" % g["wf_cagr"], "", "%.4f" % g["wf_sharpe"],
                        "%.6f" % g["wf_max_dd"], "", "WALK-FORWARD-RUN", "",
                        "chosen " + g["chosen"] + ("; OIL FLAG: " + CM.USO_FLAG if g["oil_flag"] else "")])
        for v in vs:
            r = df.loc[v.test_id]
            w.writerow([v.test_id, NOW, "9-5-suspect-sensitivity", v.strategy, v.signal_instrument, v.trade_instrument,
                        v.params, "%s..%s" % (EVAL, VE), 1, "", "", "%.4f" % r["interp_val_sharpe"], "", "",
                        "SENSITIVITY-RUN", "", note(v, "UGL suspect closes interpolated; is diff %+.4f, val diff %+.4f"
                                                    % (r["interp_is_sharpe_diff"], r["interp_val_sharpe_diff"]))])
    phase5_report(df, wf, vs, bench, n_eff, calm, first_wf, last_wf, stress)
    print("phase 5 done; N_eff (26 new) = %.1f" % n_eff)


def phase5_report(df, wf, vs, bench, n_eff, calm, first_wf, last_wf, stress):
    pct = lambda x: "%.1f%%" % (100 * x)
    meta_b = __import__("json").load(open(CM.CLEAN / "build_meta.json"))
    L = ["# Commodity study, Phase 5: validation (2019–2023)\n",
         "_Run %s. Continuous runs from %s; in-sample to %s, validation %s to %s. Risk layer off, $100 start. "
         "Python %s, pandas %s, numpy %s._\n" % (NOW, EVAL, IS_END, VS, VE, platform.python_version(),
                                                pd.__version__, np.__version__),
         "⚑ = uses oil. **Oil flag:** %s. Oil results before and after April 2020 come from a differently built fund.\n" % CM.USO_FLAG]
    ewv, mixv = df.loc[EW, "val_sharpe"], df.loc[MIX, "val_sharpe"]
    beat = [t for t in df.index if t.startswith("V") and df.at[t, "val_sharpe"] > ewv
            and df.at[t, "val_sharpe"] > df.at[t, "own_bench_val_sharpe"]]
    top = df[df.index.str.startswith("V")].sort_values("dsr", ascending=False).head(5)
    L.append("## Result first\n")
    L.append("- **%d of 26** trials beat both their own buy-and-hold and equal weight (GLD/SLV/USO, Sharpe %.2f) out of sample%s."
             % (len(beat), ewv, (": " + ", ".join(beat)) if beat else ""))
    L.append("- 70/30 SPY/GLD benchmark: validation Sharpe %.2f, CAGR %s, max drawdown %s." % (
        mixv, pct(df.loc[MIX, "val_cagr"]), pct(df.loc[MIX, "val_max_drawdown"])))
    L.append("- Deflated Sharpe at cumulative N = %d (hurdle: annualized Sharpe the best of %d unskilled trials would "
             "reach, %.2f). Best 5:\n" % (N_CUM, N_CUM, top["dsr_hurdle_ann"].iloc[0]))
    L.append("| ID | Strategy | Params | Val Sharpe | 95% CI | DSR (N=118) | DSR (N=26, info) |\n|---|---|---|---|---|---|---|")
    for t, r in top.iterrows():
        L.append("| %s | %s %s%s | %s | %.2f | %.2f to %.2f | %.3f | %.3f |" % (
            t, r["strategy"], r["trade"].replace("|", "/"), " ⚑" if r["oil_flag"] else "", short(r["params"]),
            r["val_sharpe"], r["val_sharpe_ci_lo"], r["val_sharpe_ci_hi"], r["dsr"], r["dsr_n26"]))
    L.append("\nEffective number of independent new trials (correlation-based, information only): %.1f.\n" % n_eff)
    L.append("## Benchmarks\n")
    L.append("| ID | Series | IS Sharpe | Val Sharpe | Val CAGR | Val max DD |\n|---|---|---|---|---|---|")
    for b in bench:
        r = df.loc[b.test_id]
        L.append("| %s | %s %s%s | %.2f | %.2f | %s | %s |" % (b.test_id, b.strategy, b.trade_instrument.replace("|", "/"),
                                                             oilmark(b), r["is_sharpe"], r["val_sharpe"], pct(r["val_cagr"]),
                                                             pct(r["val_max_drawdown"])))
    L.append("\n## All 26 trials\n")
    L.append("| ID | Strategy | Trades in | Params | IS Sharpe | Val Sharpe | Own B&H | Val CAGR | Val max DD | Round trips | "
             "Val Sharpe 2x / 3x costs | Time in market | DSR |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for v in vs:
        r = df.loc[v.test_id]
        L.append("| %s | %s | %s%s | %s | %.2f | %.2f | %.2f | %s | %s | %d | %.2f / %.2f | %.0f%% | %.3f |" % (
            v.test_id, v.strategy, v.trade_instrument.replace("|", "/"), oilmark(v), short(v.params),
            r["is_sharpe"], r["val_sharpe"], r["own_bench_val_sharpe"], pct(r["val_cagr"]), pct(r["val_max_drawdown"]),
            r["val_n_round_trips"], r["val_sharpe_x2"], r["val_sharpe_x3"], 100 * r["val_time_in_market"], r["dsr"]))
    L.append("\n## Walk-forward (train 5 years, test the next year, %d–%d)\n" % (first_wf, last_wf))
    L.append("| Group | WF Sharpe | Own B&H | Equal weight | 70/30 | WF CAGR | WF max DD | Parameter chosen each year |")
    L.append("|---|---|---|---|---|---|---|---|")
    for _, g in wf.iterrows():
        L.append("| %s%s | %.2f | %.2f | %.2f | %.2f | %s | %s | %s |" % (
            g["group"].replace("|", "/"), " ⚑" if g["oil_flag"] else "", g["wf_sharpe"], g["own_bench_sharpe"],
            g["ew_sharpe"], g["mix_sharpe"], pct(g["wf_cagr"]), pct(g["wf_max_dd"]), g["chosen"]))
    L.append("\n## Stress periods ($100 at the start of each period; lowest value reached)\n")
    names = ["2008", "covid_2020", "2022"] + ["calm_%d" % y for y in calm]
    L.append("| ID | " + " | ".join(names) + " |\n|---|" + "---|" * len(names))
    for t in list(df.index):
        r = df.loc[t]
        L.append("| %s | %s |" % (t, " | ".join("%+.0f%% (low $%.0f)" % (100 * r["stress_%s_return" % n], r["stress_%s_min_value" % n])
                                               for n in names)))
    L.append("\nCalm years are the 3 lowest SPY-volatility years: %s.\n" % ", ".join(map(str, calm)))
    L.append("## Suspect-price sensitivity\n")
    L.append("UGL's unresolved 2018-05-18..22 closes were interpolated and every trial was rerun. Largest change in "
             "validation Sharpe: %.1e; in in-sample Sharpe: %.1e (V096 and V098 held UGL that week).\n" % (df["interp_val_sharpe_diff"].abs().max(),
                                                                       df["interp_is_sharpe_diff"].abs().max()))
    L.append("## Synthetic leveraged history (AGQ, UCO before December 2008)\n")
    L.append("| Fund | Real from | Extra drag (calibrated to 2018) | Daily corr. (overlap) | Tracking error | Synthetic minus real, 2019–2023 (per year) |")
    L.append("|---|---|---|---|---|---|")
    for t in ("AGQ", "UCO"):
        L.append("| %s | %s | %.2f%% | %.3f | %.1f%% | %+.1f pp |" % (
            t, meta_b["real_start"][t], 100 * meta_b["extra_drag"][t]["annual"], meta_b["tracking"][t]["correlation"],
            100 * meta_b["tracking"][t]["tracking_error_ann"], 100 * meta_b["tracking_2019_2023"][t]["mean_diff_ann"]))
    L.append("\nThe validation window uses real AGQ/UCO prices only; the synthetic part affects in-sample and walk-forward "
             "training years before 2009.\n")
    L.append("## Method notes\n")
    L.append("- Sharpe = annualized excess return over T-bills. DSR uses the cross-trial variance of daily validation "
             "Sharpe ratios over all 118 trials (92 ETF + 26 commodity) and N = 118.")
    L.append("- FRED signals use only values released by each date: DFII10 from the 2nd trading day after its date "
             "(H.15, 4:15 pm), DTWEXBGS from the Wednesday after its week (H.10, weekly). Current FRED vintage; "
             "revisions not modelled.")
    L.append("- Bootstrap: 10,000 i.i.d. resamples of daily excess returns, seed %d + 92 + trial index." % SEED)
    (REP / "commodities_phase5_validation.md").write_text("\n".join(L) + "\n")


# ================================================================ Phase 6
def phase6():
    kc = cfg["validation"]["kill_criteria"]
    df = pd.read_csv(RES / "commodities_phase5_metrics.csv", index_col=0)
    ew, mix = df.loc[EW], df.loc[MIX]
    v = df[df.index.str.startswith("V")].copy()
    oos_years = int(VE[:4]) - int(VS[:4]) + 1
    ruin = cfg["capital"]["ruin_usd"]
    v["beats_both"] = (v["val_sharpe"] > v["own_bench_val_sharpe"]) & (v["val_sharpe"] > ew["val_sharpe"])
    v["group"] = v["strategy"] + "|" + v["signal"] + "|" + v["trade"]
    reasons = {}
    for tid, r in v.iterrows():
        why = []
        if not r["beats_both"]:
            lost = []
            if r["val_sharpe"] <= r["own_bench_val_sharpe"]:
                lost.append("own buy-and-hold %.2f" % r["own_bench_val_sharpe"])
            if r["val_sharpe"] <= ew["val_sharpe"]:
                lost.append("equal weight %.2f" % ew["val_sharpe"])
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
        order = list(v.index[v["group"] == r["group"]])
        i = order.index(tid)
        bad = [n for n in order[max(0, i - 1):i] + order[i + 1:i + 2] if not v.at[n, "beats_both"]]
        if bad:
            why.append("K5 neighbor(s) %s fail out of sample" % ",".join("%s(%s)" % (n, v.at[n, "params"].split(";")[0]
                                                                                      if not v.at[n, "strategy"].startswith("I05")
                                                                                      else v.at[n, "params"].split(";")[1])
                                                                          for n in bad))
        if r["val_sharpe"] < kc["min_oos_to_is_sharpe_ratio"] * r["is_sharpe"]:
            why.append("K6 OOS Sharpe %.2f < half of in-sample %.2f" % (r["val_sharpe"], r["is_sharpe"]))
        hit = [n for n in ("2008", "covid_2020", "2022") if r["stress_%s_min_value" % n] <= ruin]
        if hit:
            why.append("K7 fell to $20 or below in %s" % ", ".join(hit))
        reasons[tid] = why
    v["killed"] = [bool(reasons[t]) for t in v.index]
    v["reasons"] = ["; ".join(reasons[t]) for t in v.index]
    surv = list(v.index[~v["killed"]])
    crit = ["K1", "K2", "K3", "K4", "K5", "K6", "K7"]
    names = {"K1": "OOS Sharpe does not beat own buy-and-hold and equal weight",
             "K2": "Deflated Sharpe probability (N=118) below 0.95", "K3": "Profitable at 1x but not at 2x costs",
             "K4": "Too few OOS trades (<30), or <5 OOS years for monthly strategies",
             "K5": "Edge disappears one grid step away", "K6": "OOS Sharpe below half of in-sample Sharpe",
             "K7": "Fell to $20 or below in a stress period"}
    cnt = {k: sum(any(x.startswith(k) for x in reasons[t]) for t in v.index) for k in crit}
    only = {k: sum(len(reasons[t]) == 1 and reasons[t][0].startswith(k) for t in v.index) for k in crit}
    best = v.sort_values("dsr", ascending=False).iloc[0]
    bid = v.sort_values("dsr", ascending=False).index[0]
    bs = v.sort_values("val_sharpe", ascending=False).iloc[0]
    bsid = v.sort_values("val_sharpe", ascending=False).index[0]
    pct = lambda x: "%.1f%%" % (100 * x)
    L = ["# Commodity study, Phase 6: kill table\n", "## Result\n",
         "- **Survivors: %s.** %d of 26 trials survive; %d are killed.%s" % (
             "YES (" + ", ".join(surv) + ")" if surv else "NO", len(surv), 26 - len(surv),
             "" if surv else " Under the pre-agreed rules, nothing goes to the holdout, Phase 7 or Phase 10 alerts."),
         "- **Best Deflated Sharpe at cumulative N = 118: %.3f** (%s, %s %s, %s%s), against 0.95 required." % (
             best["dsr"], bid, best["strategy"], best["trade"].replace("|", "/"), short(best["params"]),
             ", uses oil ⚑" if best["oil_flag"] else ""),
         "- **Best idea vs the 70/30 SPY/GLD benchmark (validation 2019–2023):**\n",
         "| | Val Sharpe | Val CAGR | Val max DD | DSR (N=118) |\n|---|---|---|---|---|",
         "| %s (best DSR) | %.2f | %s | %s | %.3f |" % (bid, best["val_sharpe"], pct(best["val_cagr"]), pct(best["val_max_drawdown"]), best["dsr"])]
    if bsid != bid:
        L.append("| %s (best val Sharpe) | %.2f | %s | %s | %.3f |" % (bsid, bs["val_sharpe"], pct(bs["val_cagr"]),
                                                                   pct(bs["val_max_drawdown"]), bs["dsr"]))
    L += ["| 70/30 SPY/GLD (CB09) | %.2f | %s | %s | benchmark |" % (mix["val_sharpe"], pct(mix["val_cagr"]), pct(mix["val_max_drawdown"])),
          "| Equal weight GLD/SLV/USO (CB08, K1) | %.2f | %s | %s | benchmark |" % (ew["val_sharpe"], pct(ew["val_cagr"]), pct(ew["val_max_drawdown"])),
          "| GLD buy-and-hold (CB01) | %.2f | %s | %s | benchmark |" % (df.loc["CB01", "val_sharpe"], pct(df.loc["CB01", "val_cagr"]), pct(df.loc["CB01", "val_max_drawdown"])),
          "| SPY buy-and-hold (CB07) | %.2f | %s | %s | benchmark |" % (df.loc["CB07", "val_sharpe"], pct(df.loc["CB07", "val_cagr"]), pct(df.loc["CB07", "val_max_drawdown"])),
          "\n⚑ = uses oil. **Oil flag:** %s.\n" % CM.USO_FLAG,
          "| Criterion | Trials failing it | Failing only this one |\n|---|---|---|"]
    L += ["| %s %s | %d | %d |" % (k, names[k], cnt[k], only[k]) for k in crit]
    L += ["\nThe criteria are the ETF study's, applied mechanically and unchanged. K1's equal weight here is CB08 "
          "(GLD/SLV/USO, Sharpe %.2f); K2 uses N = 118. A trial is killed if any criterion fails.\n" % ew["val_sharpe"],
          "## All 26 trials\n",
          "| ID | Strategy | Trades in | Params | Val Sharpe | Own B&H | EW | DSR | Round trips | IS Sharpe | Verdict | Reasons |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for tid, r in v.iterrows():
        L.append("| %s | %s | %s%s | %s | %.2f | %.2f | %.2f | %.3f | %d | %.2f | %s | %s |" % (
            tid, r["strategy"], r["trade"].replace("|", "/"), " ⚑" if r["oil_flag"] else "", short(r["params"]), r["val_sharpe"],
            r["own_bench_val_sharpe"], ew["val_sharpe"], r["dsr"], r["val_n_round_trips"], r["is_sharpe"],
            "**KILLED**" if r["killed"] else "**PASS**", r["reasons"] or "-"))
    k2 = [t for t in v.index if len(reasons[t]) == 1 and reasons[t][0].startswith("K2")]
    L.append("\n## Closest calls (fail only K2)\n")
    L += ["- %s %s: validation Sharpe %.2f, DSR %.3f." % (t, v.at[t, "strategy"], v.at[t, "val_sharpe"], v.at[t, "dsr"]) for t in k2] or ["- none"]
    (REP / "commodities_kill_table.md").write_text("\n".join(L) + "\n")
    v[["strategy", "signal", "trade", "params", "killed", "reasons"]].to_csv(RES / "commodities_phase6_kill.csv")
    with open(LOG, "a", newline="") as fh:
        w = csv.writer(fh)
        for tid, r in v.iterrows():
            w.writerow([tid, NOW, "9-6-kill", r["strategy"], r["signal"], r["trade"], r["params"], "%s..%s" % (VS, VE), 1,
                        "%.6f" % r["val_cagr"], "%.6f" % r["val_ann_vol"], "%.4f" % r["val_sharpe"],
                        "%.6f" % r["val_max_drawdown"], int(r["val_n_round_trips"]), "KILLED" if r["killed"] else "PASS",
                        r["reasons"], "mechanical; ETF-study definitions; N=118" + ("; OIL FLAG: " + CM.USO_FLAG if r["oil_flag"] else "")])
    print("survivors:", surv)
    print({k: (cnt[k], only[k]) for k in crit})
    print("best DSR", bid, round(best["dsr"], 4), "K2-only:", k2)


def phase5_report_only():
    """Rebuild the Phase 5 report from saved results (no runs, nothing logged)."""
    _, _, bench, vs = series(VE)
    df = pd.read_csv(RES / "commodities_phase5_metrics.csv", index_col=0)
    wf = pd.read_csv(RES / "commodities_phase5_walk_forward.csv")
    m = pd.read_pickle(RES / "commodities_phase5_meta.pkl")
    global NOW
    NOW = m["now"]
    phase5_report(df, wf, vs, bench, m["n_eff"], m["calm"], m["first_wf"], m["last_wf"], m["stress"])


if __name__ == "__main__":
    if "--report-only" in sys.argv:
        phase5_report_only()
        sys.exit()
    ph = sys.argv[sys.argv.index("--phase") + 1]
    {"4": phase4, "5": phase5, "6": phase6}[ph]()
