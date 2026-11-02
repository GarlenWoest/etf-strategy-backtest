"""Study 5 runner: protocol research/STUDY5_PROTOCOL_v1.1.md (frozen 2026-11-02, sha256 35d1b33a...).

Run ONLY on the owner's instruction, after the 2026-11-02 16:45 ETF run and 17:02 ET financing roll are verified.
One run; no reruns except a disclosed bug fix. Data before 2024-01-01 only (asserted).

IMPLEMENTATION CHOICES (fixed and committed BEFORE any result was seen; the protocol does not state them):
 I-1 Prices: Board H.10 noon rates. GBP/USD = USD per GBP (RXI$US_N.B.UK); USD/JPY = JPY per USD (RXI_N.B.JA).
     Daily returns between consecutive available H.10 observations ("ND" holidays skipped).
 I-2 Account: $10,000 start in each window; spot-only; the whole account balance earns the 3-month T-bill
     (Board H.15) as collateral interest: rate of the previous observation x calendar days / 360, discount basis
     used as is. Daily account return = w * spot return + cash return - costs. Same for every variant (like for like).
 I-3 T1/T2 warm-up: the approved scheme starts 1990-01-02, and pre-1990 FX data is not used (A1 rejected). The first
     month-end decision with 60 in-window returns sets the start of the in-sample evaluation for BOTH scaled and
     unscaled. Validation starts 2015-01-02 with the position decided at the last 2014 month-end (in-sample data).
     Base sign = sign of the mean daily log return over 1990-01-02..2014-12-31 (computed once, recorded).
 I-4 T1/T2 timing: decision on the last H.10 day of each month; sigma60 = std(ddof=1) of the last 60 daily log returns
     up to and including that day x sqrt(252); new weight applies from the next H.10 day (execution) onward.
     "One extra FX day later" = applies from the second H.10 day after the decision.
 I-5 Costs: 0.015% x |change in weight| x equity at each trade (initial entry included), x2 / x3 for the cost checks.
 I-6 Risk metrics on daily account returns in the window: realized vol = std(ddof=1) x sqrt(252); max drawdown of the
     account equity path; worst calendar-month account return. R-1: stationary bootstrap (Politis-Romano, mean block
     5 days, paired days, 10,000 resamples, seed 20261102) of vol(unscaled) - vol(scaled); passes if the 5th
     percentile > 0. R-2: |maxDD scaled| <= 0.75 |maxDD unscaled|. R-3: loss of worst month scaled <= 0.75 x loss
     unscaled. R-5 (in-sample): point estimates only: vol, |maxDD|, worst-month loss all lower for scaled.
 I-7 K7 stress windows: those of USD/JPY study 1 (tools/run_usdjpy_study1.py STRESS) that fall inside each window,
     each rescaled to $10,000; killed if any low < $2,000.
 I-8 T3 calendar: NYSE trading days = the dates in the Ken French daily file. t = second-to-last trading day of the
     month; R = compounded (Mkt-RF + RF) from the month's first trading day through t-1. Entry at H.10 on t, exit at
     H.10 on the next NYSE trading day (t+1); "no data" if either has no H.10 rate. Event return = sign x spot return
     - 2 x 0.015% (excess return: collateral cash is earned either way). Placebo: same on the 10th trading day.
 I-9 T3 robustness "enter one day earlier": entry at H.10 on the third-to-last trading day s (R through s-1), exit
     unchanged at H.10 on the last trading day (two-day hold, still spanning the last-day 11:00 NY London fix);
     killed if its validation mean <= 0.
 I-10 T3 daily series for Sharpe/DSR: validation H.10 days, event return booked on the exit day, 0 otherwise.
 I-11 DSR (STATS_POLICY v1.0): pooled variance of annualized Sharpes of the 142 past trials (results/ metrics,
     Study 3 full-span) plus V143 (scaled overlay), V144 (scaled overlay) and V145 (I-10), N = 145, converted to daily.
 I-12 Data validation (protocol section 3, step 2): STOP if any duplicate date, unordered date, non-positive value or
     date >= 2024-01-01; everything else (gaps vs the Board calendar, stale runs of 5+ equal values, |move| > 3%) is
     reported, not a stop.
"""
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CUT = pd.Timestamp("2024-01-01")
IS0, IS1 = pd.Timestamp("1990-01-02"), pd.Timestamp("2014-12-31")
VA0, VA1 = pd.Timestamp("2015-01-02"), pd.Timestamp("2023-12-29")
COST = 0.00015
SEED = 20261102
N_CUM = 145
STRESS = {"1998": ("1998-08-01", "1998-12-31"), "2008-09": ("2008-09-01", "2009-03-31"), "2011": ("2011-03-01", "2011-04-30"),
          "2022": ("2022-01-01", "2022-12-31")}                       # tools/run_usdjpy_study1.py:44-45 (I-7)


# ---------------------------------------------------------------- pure functions (unit-testable on synthetic data)
def max_drawdown(eq):
    eq = np.asarray(eq, float)
    return float((eq / np.maximum.accumulate(eq) - 1).min())


def worst_month(ret):
    m = (1 + ret).groupby([ret.index.year, ret.index.month]).prod() - 1
    return float(m.min())


def ann_vol(ret):
    return float(np.std(np.asarray(ret, float), ddof=1) * math.sqrt(252))


def stationary_bootstrap_idx(n, mean_block, rng):
    """Politis-Romano stationary bootstrap indices: a new block starts with probability 1/mean_block (always at 0)."""
    starts = rng.random(n) < 1.0 / mean_block
    starts[0] = True
    jumps = rng.integers(0, n, size=n)
    ar = np.arange(n)
    last = np.maximum.accumulate(np.where(starts, ar, 0))           # position where the current block started
    return (jumps[last] + (ar - last)) % n


def boot_vol_diff(r_unscaled, r_scaled, reps=10000, block=5, seed=SEED):
    a, b = np.asarray(r_unscaled, float), np.asarray(r_scaled, float)
    rng = np.random.default_rng(seed)
    out = np.empty(reps)
    for k in range(reps):
        i = stationary_bootstrap_idx(len(a), block, rng)
        out[k] = (np.std(a[i], ddof=1) - np.std(b[i], ddof=1)) * math.sqrt(252)
    return float(np.percentile(out, 5)), float(np.percentile(out, 95))


def simulate(px, rf_rate, weights, cost_mult=1.0, equity0=10000.0):
    """px: H.10 prices (index = days); weights: target weight per day (applies to the return from that day to the next);
    rf_rate: percent per year on the same index (previous observation used). Returns daily account returns (index = day of
    the return's end) and the equity path."""
    p = px.to_numpy(float)
    w = weights.to_numpy(float)
    days = px.index
    rf = rf_rate.reindex(days).ffill().to_numpy(float)
    eq = [equity0]
    rets, cashr = [], []
    prev_w = 0.0
    for i in range(len(p) - 1):
        e = eq[-1]
        cost = abs(w[i] - prev_w) * e * COST * cost_mult
        prev_w = w[i]
        cash = e * (rf[i] / 100.0) * (days[i + 1] - days[i]).days / 360.0
        pnl = e * w[i] * (p[i + 1] / p[i] - 1)
        e2 = e + pnl + cash - cost
        rets.append(e2 / e - 1)
        cashr.append(cash / e)
        eq.append(e2)
    r = pd.Series(rets, index=days[1:])
    return r, pd.Series(eq, index=days), pd.Series(cashr, index=days[1:])


def vol_target_weights(px, sign, start, end, delay=1, target=0.10, unscaled=False):
    """Weights on H.10 days in [start, end]: month-end decisions, applied from the delay-th H.10 day after the decision."""
    lr = np.log(px / px.shift(1))
    days = px.index
    w = pd.Series(np.nan, index=days)
    me = px.groupby([days.year, days.month]).tail(1).index           # last H.10 day of each month
    for d in me:
        win = lr.loc[IS0:d].dropna()                                    # in-window returns only (I-3)
        if len(win) < 60:
            continue
        sig = float(win.iloc[-60:].std(ddof=1) * math.sqrt(252))
        x = 1.0 if unscaled else min(1.0, target / sig)
        pos = days.get_loc(d) + delay
        if pos < len(days):
            w.iloc[pos] = sign * x
    w = w.ffill()
    return w.loc[start:end]


# ---------------------------------------------------------------- data
def load():
    def h10(name):
        d = pd.read_csv(ROOT / "data/raw/board_h10/%s.csv" % name, parse_dates=["date"])
        return d
    gbp, jpy = h10("board_h10_usd_per_gbp"), h10("board_h10_jpy_per_usd")
    tb = pd.read_csv(ROOT / "data/raw/board_h15/board_h15_tbill_3m_secondary.csv", parse_dates=["date"])
    kf = pd.read_csv(ROOT / "data/raw/r8_kenfrench_daily/kf_factors_daily.csv", parse_dates=["date"])
    return gbp, jpy, tb, kf


def validate(df, name):
    """I-12. Returns (report dict, stop reasons)."""
    from src import clock
    stop = []
    if df["date"].duplicated().any():
        stop.append("duplicate dates")
    if not df["date"].is_monotonic_increasing:
        stop.append("dates out of order")
    if (df["date"] >= CUT).any():
        stop.append("2024+ dates present")
    v = df.dropna(subset=["value"])
    if (v["value"] <= 0).any():
        stop.append("non-positive values")
    s = v.set_index("date")["value"].loc[IS0:VA1]
    wd = pd.bdate_range(IS0, VA1)
    missing = wd.difference(s.index)
    hol = set()
    for y in range(IS0.year, VA1.year + 1):
        hol |= set(clock.us_board_holidays(y))
    unexplained = [d for d in missing if d.date() not in hol]
    runs, run = 0, 1
    vals = s.to_numpy()
    for i in range(1, len(vals)):
        run = run + 1 if vals[i] == vals[i - 1] else 1
        runs += run == 5
    lr = np.log(s / s.shift(1)).dropna()
    big = int((lr.abs() > math.log(1.03)).sum())
    return {"series": name, "obs_1990_2023": int(len(s)), "weekdays_without_value": int(len(missing)),
            "of_which_not_board_holidays": int(len(unexplained)), "stale_runs_5plus": int(runs),
            "moves_over_3pct": big, "first": str(s.index[0].date()), "last": str(s.index[-1].date())}, stop


# ---------------------------------------------------------------- trials
def risk_trial(px, tb, label):
    lr = np.log(px / px.shift(1)).loc[IS0:IS1].dropna()
    sign = 1.0 if lr.mean() > 0 else -1.0
    out = {"base_sign": sign, "is_mean_daily_logret_sign": "positive" if sign > 0 else "negative"}

    def window(a, b, delay=1, cm=1.0):
        ws = vol_target_weights(px, sign, a, b, delay=delay)
        wu = vol_target_weights(px, sign, a, b, delay=delay, unscaled=True)
        st = max(ws.first_valid_index(), wu.first_valid_index())
        ws, wu = ws.loc[st:], wu.loc[st:]
        p = px.loc[st:b]
        rs, es, cs = simulate(p, tb, ws, cm)
        ru, eu, _ = simulate(p, tb, wu, cm)
        return dict(start=str(st.date()), rs=rs, ru=ru, es=es, eu=eu, cs=cs)

    def metrics(w):
        return dict(vol_s=ann_vol(w["rs"]), vol_u=ann_vol(w["ru"]), mdd_s=max_drawdown(w["es"]), mdd_u=max_drawdown(w["eu"]),
                    wm_s=worst_month(w["rs"]), wm_u=worst_month(w["ru"]))

    def rtest(w, boot=True):
        m = metrics(w)
        lo, hi = boot_vol_diff(w["ru"], w["rs"]) if boot else (float("nan"), float("nan"))
        r1 = m["vol_s"] < m["vol_u"] and (lo > 0 if boot else True)
        r2 = abs(m["mdd_s"]) <= 0.75 * abs(m["mdd_u"])
        r3 = max(0.0, -m["wm_s"]) <= 0.75 * max(0.0, -m["wm_u"])
        return dict(m, boot_p5=lo, boot_p95=hi, R1=r1, R2=r2, R3=r3)

    val = window(VA0, VA1)
    out["val"] = rtest(val)
    out["val_start"] = val["start"]
    out["cost2"] = rtest(window(VA0, VA1, cm=2.0))
    out["cost3"] = rtest(window(VA0, VA1, cm=3.0))
    out["delay"] = rtest(window(VA0, VA1, delay=2))
    isw = window(IS0, IS1)
    m = metrics(isw)
    out["is"] = dict(m, R5=m["vol_s"] < m["vol_u"] and abs(m["mdd_s"]) < abs(m["mdd_u"]) and m["wm_s"] > m["wm_u"])
    out["is_start"] = isw["start"]
    # K7 stress windows (I-7)
    stress = STRESS
    lows = {}
    for k, (a, b) in stress.items():
        for wname, w in (("val", val), ("is", isw)):
            e = w["es"].loc[a:b]
            if len(e) > 1:
                lows["%s_%s" % (wname, k)] = float((e / e.iloc[0] * 10000).min())
    out["k7_lows"] = lows
    out["K7"] = all(v >= 2000 for v in lows.values())
    over = val["rs"] - val["cs"]                                       # overlay = account return minus cash earned
    out["val_sharpe_scaled_overlay"] = float(over.mean() / over.std(ddof=1) * math.sqrt(252))
    out["val_overlay_daily"] = over
    out["PASS"] = all(out[k]["R1"] and out[k]["R2"] and out[k]["R3"] for k in ("val", "cost2", "cost3", "delay")) and out["is"]["R5"] and out["K7"]
    return out


def g1_events(px, kf, which, thr, start, end, early=False):
    """Return list of (exit_date, signed spot return) and counts. which: 'g1' (2nd-to-last) or 'placebo' (10th day)."""
    td = kf["date"]
    mk = (kf.set_index("date")["Mkt-RF"] + kf.set_index("date")["RF"])
    by = td.groupby([td.dt.year, td.dt.month])
    ev, nodata, triggers = [], 0, 0
    pxs = px
    for (y, m), g in by:
        days = list(g)
        if len(days) < 12:
            continue
        if which == "g1":
            t = days[-3] if early else days[-2]
            exit_d = days[-1] if early else days[-1]
        else:
            t = days[9]
            exit_d = days[10]
        i = days.index(t)
        if i == 0:
            continue
        R = float((1 + mk.loc[days[0]:days[i - 1]]).prod() - 1)
        if not (start <= exit_d <= end):
            continue
        if R >= thr:
            s = 1.0
        elif R <= -thr:
            s = -1.0
        else:
            continue
        triggers += 1
        if t not in pxs.index or exit_d not in pxs.index:
            nodata += 1
            continue
        ev.append((exit_d, s * (pxs.loc[exit_d] / pxs.loc[t] - 1)))
    return ev, nodata, triggers


def g1_trial(px, kf):
    def mean(evs, cm=1.0):
        r = [x[1] - 2 * COST * cm for x in evs]
        return (float(np.mean(r)) if r else float("nan")), r
    out = {}
    v, nd, trg = g1_events(px, kf, "g1", 0.02, VA0, VA1)
    i, ndi, trgi = g1_events(px, kf, "g1", 0.02, IS0, IS1)
    pl, ndp, _ = g1_events(px, kf, "placebo", 0.02, VA0, VA1)
    out["val_events"], out["val_nodata"], out["val_triggers"] = len(v), nd, trg
    out["is_events"], out["is_nodata"] = len(i), ndi
    out["val_mean"], vr = mean(v)
    out["val_sd"] = float(np.std(vr, ddof=1))
    out["val_t"] = out["val_mean"] / (out["val_sd"] / math.sqrt(len(vr)))
    out["is_mean"], _ = mean(i)
    out["placebo_mean"], _ = mean(pl)
    out["placebo_events"] = len(pl)
    out["val_mean_x2"], _ = mean(v, 2.0)
    out["val_mean_x3"], _ = mean(v, 3.0)
    out["val_mean_thr015"], _ = mean(g1_events(px, kf, "g1", 0.015, VA0, VA1)[0])
    out["val_mean_thr03"], _ = mean(g1_events(px, kf, "g1", 0.03, VA0, VA1)[0])
    out["val_mean_early"], _ = mean(g1_events(px, kf, "g1", 0.02, VA0, VA1, early=True)[0])
    days = px.loc[VA0:VA1].index
    daily = pd.Series(0.0, index=days)
    for d, r in v:
        daily.loc[d] += r - 2 * COST
    out["val_daily"] = daily
    eq = (1 + daily).cumprod() * 10000
    out["K7_low"] = float(eq.min())
    s = np.sign(out["val_mean"])
    out["K1"] = out["val_mean"] > 0 and out["val_mean"] > out["placebo_mean"]
    out["K3"] = out["val_mean_x2"] > 0 and out["val_mean_x3"] > 0
    out["K4"] = len(v) >= 30
    out["K5"] = np.sign(out["val_mean_thr015"]) == s and np.sign(out["val_mean_thr03"]) == s
    out["K6"] = (out["val_mean"] >= 0.5 * out["is_mean"]) if out["is_mean"] > 0 else None
    out["K7"] = out["K7_low"] >= 2000
    out["ROB_early"] = out["val_mean_early"] > 0
    return out


def past_sharpes():
    R = ROOT / "results"
    s1 = pd.read_csv(R / "phase5_metrics.csv", index_col=0)
    s2 = pd.read_csv(R / "commodities_phase5_metrics.csv", index_col=0)
    s3 = pd.read_csv(R / "study3_metrics.csv", index_col=0)
    s4 = pd.read_csv(R / "usdjpy_study1_metrics.csv", index_col=0)
    v = []
    for df, col, lo, hi in ((s1, "val_sharpe", 1, 92), (s2, "val_sharpe", 93, 118), (s3, "full_sharpe", 119, 134), (s4, "val_sharpe", 135, 142)):
        v += [float(df.at[t, col]) for t in df.index if t.startswith("V") and lo <= int(t[1:]) <= hi]
    assert len(v) == 142
    return v


def main():
    from src import validate as V
    gbp, jpy, tb, kf = load()
    for d in (gbp, jpy, tb, kf):
        assert (d["date"] < CUT).all()
    vrep, stops = [], []
    for df, name in ((gbp, "USD per GBP (Board H.10)"), (jpy, "JPY per USD (Board H.10)")):
        r, s = validate(df, name)
        vrep.append(r)
        stops += ["%s: %s" % (name, x) for x in s]
    if stops:
        print("STOP: data validation failed:", stops)
        print(json.dumps(vrep, indent=1))
        sys.exit(2)
    px_g = gbp.dropna(subset=["value"]).set_index("date")["value"]
    px_j = jpy.dropna(subset=["value"]).set_index("date")["value"]
    tbs = tb.dropna(subset=["value"]).set_index("date")["value"]
    t1, t2, t3 = risk_trial(px_g, tbs, "V143"), risk_trial(px_j, tbs, "V144"), g1_trial(px_g, kf)
    # DSR (I-10, I-11)
    sh3 = float(t3["val_daily"].mean() / t3["val_daily"].std(ddof=1) * math.sqrt(252))
    pool = past_sharpes() + [t1["val_sharpe_scaled_overlay"], t2["val_sharpe_scaled_overlay"], sh3]
    daily_pool = np.array(pool) / math.sqrt(252)
    res = {}
    for k, x in (("V143", t1["val_overlay_daily"]), ("V144", t2["val_overlay_daily"]), ("V145", t3["val_daily"])):
        d, sr0 = V.deflated_sharpe(x.to_numpy(), daily_pool, N_CUM)
        res[k] = (d, sr0 * math.sqrt(252))
    t3["K2"] = res["V145"][0] >= 0.95
    t3["PASS"] = all([t3["K1"], t3["K2"], t3["K3"], t3["K4"], t3["K5"], t3["K6"] is not False, t3["K7"], t3["ROB_early"]])
    return dict(validation=vrep, t1=t1, t2=t2, t3=t3, dsr=res, sharpe_v145=sh3, pool_var=float(np.var(pool, ddof=1)))


if __name__ == "__main__":
    if "--run" not in sys.argv:
        sys.exit("refusing to run without --run (owner instruction required)")
    out = main()
    import pickle
    p = ROOT / "results" / "study5_run.pkl"
    pickle.dump(out, open(p, "wb"))
    print("saved", p)
