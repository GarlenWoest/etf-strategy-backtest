"""Study 6 runner: one trial, V146 turn-of-month (TOM) equity.

Protocol research/STUDY6_PROTOCOL_v1.0.md (frozen 2026-11-02, sha256 31ab9993...) plus amendment
research/STUDY6_AMENDMENT_A1.md (frozen pre-run, sha256 a35a1942...). STATS_POLICY v1.1 (t > 3 primary).
Run ONLY on the owner's instruction. One run; no reruns except a disclosed bug fix. Data before 2024-01-01 only (asserted).

IMPLEMENTATION CHOICES (fixed and committed BEFORE any result was seen; the protocol does not state them):
 I-1 Calendar: trading days = the dates in each Ken French daily file (US file for the US series, Developed ex US
     file for that series). For calendar month M with trading days d_1..d_k: day -1 = d_k; days +1, +2, +3 = the
     first three trading days of month M+1. Turn m (labelled by month M) is in a window if its day -1 and day +3
     both lie inside it. Window 1990-07-02..2023-12-29, so the first turn is July 1990 and the last November 2023
     (the December 2023 turn needs January 2024: excluded).
 I-2 e_m = mean(Mkt-RF on days -1, +1, +2, +3) - mean(Mkt-RF on d_4 .. d_{k-1} of month M), i.e. from the previous
     turn's +4 to this turn's -2. Mkt-RF is already an excess return (decimal). Gross of costs.
 I-3 Primary: plain t = mean(e) / (std(e, ddof=1) / sqrt(n)); pass needs t > 3.0. Newey-West t (Bartlett, lag 3)
     reported. One-sided p from the normal for the Romano-Wolf line (single trial: equal to the plain test).
 I-4 Kill 2 (costs): strategy daily excess = Mkt-RF on TOM days, 0 otherwise (RF earned in cash). One-way cost
     charged twice per turn: the entry (close of day -2) on day -1's return and the exit (close of day +3) on day +3's
     return, at the frozen Study 3 stock schedule by the trade date (0.34% to 1992-12-31, 0.11% 1993-2002, 0.07% from
     2003) x multiplier. Strategy figure = mean net daily excess over TOM days x 252; always long = mean daily excess
     over every trading day from turn 1's day -1 to the last turn's day +3, x 252 (no costs: one entry in 33.5 years).
     Killed if strategy < always long at 2x costs. 1x and 3x reported.
 I-5 Placebo: with i the index of day -1 in the trading calendar, placebo days are indices i+10 .. i+13 (the same
     4-day block shifted +10 trading days). Placebo e_m = mean(placebo days) - the same comparison mean as e_m.
     Killed if mean(placebo e) >= mean(e) (US).
 I-6 Halves (kill 4, US): turns with day -1 in 1990-07..2006-12 and 2007-01..2023-12; killed if either half's
     mean(e) has the opposite sign of the full-window mean (a zero half counts as opposite).
 I-7 Kill 5 (A1): Developed ex US full-window mean(e) < 0.
 I-8 Secondaries (cannot change the verdict): (i) US turns with day -1 in 2009-01..2023-12; (ii) Developed ex US full
     window. Each: n, mean, t, Newey-West t, and the I-4 cost comparison at 1x and 2x.
 I-9 Sharpe and DSR (reported only): daily net 1x strategy excess series over the I-4 span. The "calendar" family has
     one trial, so a cross-trial variance does not exist. The variance used for the expected maximum is the sampling
     variance of this trial's daily Sharpe estimate (1/T), i.e. the dispersion of null trials; N = 146. Stated.
 I-10 Data validation: STOP if any duplicate date, unordered date, date >= 2024-01-01, or missing Mkt-RF/RF inside the
     window. Otherwise reported only.
"""
import hashlib
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
W0, W1 = pd.Timestamp("1990-07-02"), pd.Timestamp("2023-12-29")
HALF1_END = pd.Timestamp("2006-12-31")
POST0 = pd.Timestamp("2009-01-01")
N_CUM = 146
FROZEN = {"research/STUDY6_PROTOCOL_v1.0.md": "31ab99937eeefbb40e8c9366af2b132764b312d7b598e60acf63fa4439db8773",
          "research/STUDY6_AMENDMENT_A1.md": "a35a194213decec588ac84651f59ec04259a294b1cc1f31390054f10aa4933c8"}


def one_way_cost(date):
    """Frozen Study 3 stock schedule (config.yaml study3_longhist costs_one_way.stocks)."""
    if date <= pd.Timestamp("1992-12-31"):
        return 0.0034
    if date <= pd.Timestamp("2002-12-31"):
        return 0.0011
    return 0.0007


def turns(dates, w0=W0, w1=W1):
    """I-1/I-2/I-5. dates: sorted DatetimeIndex of trading days. Returns a list of dicts with index positions:
    tom (4 indices), comp (comparison indices), placebo (4 indices or None), month label, day -1 date."""
    dates = pd.DatetimeIndex(dates)
    per = dates.to_period("M")
    out = []
    starts = np.flatnonzero(np.r_[True, per[1:] != per[:-1]])          # first index of each month
    for a, b in zip(starts[:-1], starts[1:]):
        i = b - 1                                                       # day -1 = last trading day of month
        if b + 2 >= len(dates):
            break
        tom = [i, b, b + 1, b + 2]
        if per[b + 2] != per[b]:                                        # month with < 3 trading days: not possible in practice
            continue
        if dates[i] < w0 or dates[b + 2] > w1:
            continue
        comp = list(range(a + 3, i))                                    # d_4 .. d_{k-1}
        plc = [i + 10, i + 11, i + 12, i + 13] if i + 13 < len(dates) and dates[i + 13] <= w1 else None
        out.append({"month": str(per[i]), "day_m1": dates[i], "tom": tom, "comp": comp, "placebo": plc})
    return out


def e_series(x, tl, placebo=False):
    """x: numpy array of daily excess returns aligned to the calendar. Returns e_m per turn (NaN-free)."""
    out = []
    for t in tl:
        days = t["placebo"] if placebo else t["tom"]
        if days is None:
            continue
        out.append(x[days].mean() - x[t["comp"]].mean())
    return np.array(out)


def t_plain(e):
    return float(e.mean() / (e.std(ddof=1) / math.sqrt(len(e))))


def t_newey_west(e, lag=3):
    e = np.asarray(e, float)
    n, u = len(e), e - e.mean()
    s = u @ u / n
    for k in range(1, lag + 1):
        s += 2 * (1 - k / (lag + 1)) * (u[k:] @ u[:-k]) / n
    return float(e.mean() / math.sqrt(s / n))


def strategy_daily(x, dates, tl, cost_mult):
    """I-4: net daily excess series over the span turn1 day -1 .. last turn day +3, and the in-market mask."""
    lo, hi = tl[0]["tom"][0], tl[-1]["tom"][-1]
    r = np.zeros(hi - lo + 1)
    inm = np.zeros(hi - lo + 1, bool)
    for t in tl:
        for j in t["tom"]:
            r[j - lo] = x[j]
            inm[j - lo] = True
        r[t["tom"][0] - lo] -= cost_mult * one_way_cost(dates[t["tom"][0] - 1])     # entry at close of day -2
        r[t["tom"][-1] - lo] -= cost_mult * one_way_cost(dates[t["tom"][-1]])       # exit at close of day +3
    return r, inm, x[lo:hi + 1]


def cost_check(x, dates, tl, mult):
    r, inm, allx = strategy_daily(x, dates, tl, mult)
    s, a = float(r[inm].mean() * 252), float(allx.mean() * 252)
    return {"mult": mult, "tom_ann_excess_per_time_in_market": s, "always_long_ann_excess": a, "tom_lower": s < a}


def summary(x, dates, tl):
    e = e_series(x, tl)
    return {"n_turns": int(len(e)), "mean_e": float(e.mean()), "sd_e": float(e.std(ddof=1)), "t": t_plain(e),
            "t_newey_west_lag3": t_newey_west(e), "first_turn": tl[0]["month"], "last_turn": tl[-1]["month"],
            "cost_1x": cost_check(x, dates, tl, 1), "cost_2x": cost_check(x, dates, tl, 2), "cost_3x": cost_check(x, dates, tl, 3)}


def evaluate(us, exus):
    """us, exus: DataFrames with date, Mkt-RF, RF (validated). Returns the full V146 result dict."""
    xu, du = us["Mkt-RF"].to_numpy(float), pd.DatetimeIndex(us["date"])
    xe, de = exus["Mkt-RF"].to_numpy(float), pd.DatetimeIndex(exus["date"])
    tu, te = turns(du), turns(de)
    prim = summary(xu, du, tu)
    e = e_series(xu, tu)
    pe = e_series(xu, [t for t in tu if t["placebo"] is not None], placebo=True)
    m1 = np.array([t["day_m1"] <= HALF1_END for t in tu])
    h1, h2 = float(e[m1].mean()), float(e[~m1].mean())
    sgn = np.sign(prim["mean_e"])
    ex = summary(xe, de, te)
    post = [t for t in tu if t["day_m1"] >= POST0]
    kills = {
        "K1_t_le_3": not prim["t"] > 3.0,
        "K2_costs_2x": prim["cost_2x"]["tom_lower"],
        "K3_placebo_ge_tom": float(pe.mean()) >= prim["mean_e"],
        "K4_half_reversal": bool(np.sign(h1) != sgn or np.sign(h2) != sgn),
        "K5_A1_exus_negative": ex["mean_e"] < 0,
    }
    r, inm, _ = strategy_daily(xu, du, tu, 1)
    sr = float(r.mean() / r.std(ddof=1))
    from src import validate as V
    var_null = 1.0 / len(r)                                             # I-9
    sr0 = V.expected_max_sharpe(var_null, N_CUM)
    dsr = V.probabilistic_sharpe(sr, sr0, len(r), float(stats.skew(r)), float(stats.kurtosis(r, fisher=False)))
    return {
        "trial": "V146", "primary_us": prim,
        "placebo_us": {"n_turns": int(len(pe)), "mean_e": float(pe.mean())},
        "halves_us": {"1990-07..2006-12": h1, "2007-01..2023-12": h2, "n": [int(m1.sum()), int((~m1).sum())]},
        "kills": kills, "PASS": not any(kills.values()),
        "secondary_i_us_2009_2023": summary(xu, du, post),
        "secondary_ii_developed_ex_us": ex,
        "reported_only": {"sharpe_net_1x_ann": sr * math.sqrt(252), "dsr": float(dsr), "sr0_ann": sr0 * math.sqrt(252),
                          "dsr_variance_note": "I-9: one-trial family; null dispersion 1/T used", "N": N_CUM,
                          "romano_wolf_one_sided_p": float(1 - stats.norm.cdf(prim["t"])),
                          "turnover_one_way_trades_per_year": 2 * prim["n_turns"] / ((du[tu[-1]["tom"][-1]] - du[tu[0]["tom"][0]]).days / 365.25)},
    }


def validate_df(df, name):
    """I-10."""
    stop = []
    if df["date"].duplicated().any():
        stop.append("duplicate dates")
    if not df["date"].is_monotonic_increasing:
        stop.append("dates out of order")
    if (df["date"] >= CUT).any():
        stop.append("2024+ dates present")
    w = df[(df["date"] >= W0) & (df["date"] <= W1)]
    if w[["Mkt-RF", "RF"]].isna().any().any():
        stop.append("missing values in window")
    return {"series": name, "rows_in_window": int(len(w)), "first": str(w["date"].iloc[0].date()),
            "last": str(w["date"].iloc[-1].date())}, stop


def check_frozen():
    bad = [p for p, h in FROZEN.items() if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h]
    if bad:
        sys.exit("STOP: frozen document hash mismatch: %s" % bad)


def main():
    check_frozen()
    us = pd.read_csv(ROOT / "data/raw/r8_kenfrench_daily/kf_factors_daily.csv", parse_dates=["date"])
    ex = pd.read_csv(ROOT / "data/raw/study6/kf_developed_ex_us_3f_daily.csv", parse_dates=["date"])
    vrep, stops = [], []
    for df, name in ((us, "US (Ken French daily)"), (ex, "Developed ex US (Ken French daily)")):
        r, s = validate_df(df, name)
        vrep.append(r)
        stops += ["%s: %s" % (name, x) for x in s]
    if stops:
        print("STOP: data validation failed:", stops)
        sys.exit(2)
    out = evaluate(us, ex)
    out["validation"] = vrep
    out["run_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return out


if __name__ == "__main__":
    if "--run" not in sys.argv:
        sys.exit("refusing to run without --run (owner instruction required)")
    res = main()
    p = ROOT / "results" / "study6_run.json"
    p.write_text(json.dumps(res, indent=1, default=str) + "\n")
    print("saved", p)
