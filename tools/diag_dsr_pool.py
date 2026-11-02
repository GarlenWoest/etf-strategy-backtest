"""DIAGNOSTIC (owner approval R6, 2026-11-02): how the Deflated Sharpe of Studies 1-4 depends on the
cross-trial variance pool. Reads only the stored metrics in results/ (pre-2024 studies); loads no price data,
runs no backtest, adds no trial, changes no verdict, writes nothing to research_log.csv or the memory ledger.

Method. For each trial the stored DSR is PSR = Phi((sr - sr0) * k), with k = sqrt(T-1)/sqrt(1 - skew*sr +
(kurt-1)/4*sr^2) (src/validate.py:150-162). k does not depend on sr0, so in annual units
z = (S - H) * K with K recovered from the stored DSR, the stored annualized Sharpe S and the stored hurdle H.
A new hurdle H' (from another variance pool or N) then gives DSR' = Phi((S - H') * K) exactly.
Check: Studies 1 and 2 store a second DSR with a different N; solving both equations for S must reproduce
the stored Sharpe.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
EG = 0.5772156649015329


def f_n(n):
    z = stats.norm.ppf
    return (1 - EG) * z(1 - 1.0 / n) + EG * z(1 - 1.0 / (n * math.e))


def ids(df, lo, hi):
    return [i for i in df.index if i.startswith("V") and lo <= int(i[1:]) <= hi]


s1 = pd.read_csv(R / "phase5_metrics.csv", index_col=0)
s2 = pd.read_csv(R / "commodities_phase5_metrics.csv", index_col=0)
s3 = pd.read_csv(R / "study3_metrics.csv", index_col=0)
s4 = pd.read_csv(R / "usdjpy_study1_metrics.csv", index_col=0)

rows = []
for study, df, col, lo, hi, n_orig in ((1, s1, "val_sharpe", 1, 92, 92), (2, s2, "val_sharpe", 93, 118, 118),
                                       (3, s3, "full_sharpe", 119, 134, 134), (4, s4, "val_sharpe", 135, 142, 142)):
    for t in ids(df, lo, hi):
        S, d, H = float(df.at[t, col]), float(df.at[t, "dsr"]), float(df.at[t, "dsr_hurdle_ann"])
        if study == 3:
            years = (pd.Timestamp("2018-12-31") - pd.Timestamp(df.at[t, "full_start"])).days / 365.25
        else:
            years = {1: 5.0, 2: 5.0, 4: 9.0}[study]          # validation 2019-2023 / 2015-2023
        z = stats.norm.ppf(min(max(d, 1e-15), 1 - 1e-15))
        rows.append(dict(id=t, study=study, S=S, dsr=d, H=H, K=z / (S - H), n_orig=n_orig, years=years))
T = pd.DataFrame(rows).set_index("id")
assert len(T) == 142, len(T)

# ---- consistency check on Studies 1/2 (second stored DSR at another N)
chk = []
for df, alt_d, alt_h in ((s1, "dsr_eff_n", "dsr_eff_hurdle_ann"), (s2, "dsr_n26", "dsr_n26_hurdle_ann")):
    for t in [i for i in df.index if i in T.index]:
        z1, z2 = stats.norm.ppf(df.at[t, "dsr"]), stats.norm.ppf(df.at[t, alt_d])
        h1, h2 = df.at[t, "dsr_hurdle_ann"], df.at[t, alt_h]
        chk.append(abs((z1 * h2 - z2 * h1) / (z1 - z2) - T.at[t, "S"]))
max_err = float(np.max(chk))

# ---- variance pools (annualized Sharpe units)
pools = {1: T[T.study == 1].S, 2: T[T.study <= 2].S, 3: T[T.study == 3].S, 4: T[T.study == 4].S}
var_orig = {k: float(np.var(v, ddof=1)) for k, v in pools.items()}
var_all = float(np.var(T.S, ddof=1))
var_z = float(np.var(T.S * np.sqrt(T.years), ddof=1))       # length-standardized: SR_ann * sqrt(years) ~ N(0,1) under null


def hurdle(var, n):
    return math.sqrt(var) * f_n(n)


T["H_check"] = [hurdle(var_orig[s], n) for s, n in zip(T.study, T.n_orig)]
T["H_pool_Norig"] = [hurdle(var_all, n) for n in T.n_orig]
T["H_policy"] = hurdle(var_all, 142)
T["H_lenstd"] = [hurdle(var_z / y, 142) for y in T.years]
for c, h in (("dsr_pool_Norig", "H_pool_Norig"), ("dsr_policy", "H_policy"), ("dsr_lenstd", "H_lenstd")):
    T[c] = stats.norm.cdf((T.S - T[h]) * T.K)
T.to_csv(ROOT / "reports" / "research_review" / "dsr_pool_diagnostic.csv")

# ---- report
out = []
w = out.append
w("# DIAGNOSTIC: Deflated Sharpe variance pool (Studies 1–4)\n")
w("_Run %s. **Diagnostic only (approval R6):** stored metrics in `results/` only; no price data loaded, no backtest, "
  "no new trials, no N change, no verdict change. Official results stay as published. Tool: `tools/diag_dsr_pool.py`._\n"
  % pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"))
w("## Checks\n")
w("- Recovered hurdles reproduce the stored ones: max |difference| %.2e (annual Sharpe units)."
  % float((T.H_check - T.H).abs().max()))
w("- Studies 1–2 store a second DSR at another N; solving both for the Sharpe reproduces the stored Sharpe within %.2e." % max_err)
w("- Study 3 uses monthly data; its Sharpe and hurdle are annualized with √12 (as stored). Study 3's `full_sharpe` is assumed to be the Sharpe the DSR used (same span; not separately checkable).\n")
w("## Variance pools (cross-trial variance of annualized Sharpe ratios)\n")
w("| Study | Pool used | Trials in pool | Variance | Hurdle at its N (annual Sharpe) |\n|---|---|---|---|---|")
for s, name in ((1, "Study 1 only"), (2, "Studies 1+2"), (3, "Study 3 only (monthly, 1927–2018)"), (4, "Study 4 only")):
    w("| %d | %s | %d | %.4f | %.3f (N=%d) |" % (s, name, len(pools[s]), var_orig[s], hurdle(var_orig[s], T[T.study == s].n_orig.iloc[0]), T[T.study == s].n_orig.iloc[0]))
w("| all | **Pooled, all 142 (policy R2)** | 142 | %.4f | %.3f (N=142) |\n" % (var_all, hurdle(var_all, 142)))
w("## Effect by study\n")
w("| Study | Hurdle as run | Hurdle, pooled variance, same N | Hurdle, policy (pooled, N=142) | Max DSR as run | Max DSR pooled, same N | Max DSR policy | Trials ≥ 0.95 as run / policy |\n|---|---|---|---|---|---|---|---|")
for s in (1, 2, 3, 4):
    x = T[T.study == s]
    w("| %d | %.3f | %.3f | %.3f | %.3f | %.3f | %.3f | %d / %d |" % (
        s, x.H.iloc[0], x.H_pool_Norig.iloc[0], x.H_policy.iloc[0], x.dsr.max(), x.dsr_pool_Norig.max(), x.dsr_policy.max(),
        int((x.dsr >= 0.95).sum()), int((x.dsr_policy >= 0.95).sum())))
w("\n## Side by side: raw-pooled vs length-adjusted pooled (both full pool, N = 142; owner decision Q1)\n")
w("| Study | Max DSR as run | Max DSR raw-pooled | Max DSR length-adjusted | Trials ≥ 0.95: as run / raw / length-adjusted |\n|---|---|---|---|---|")
for s in (1, 2, 3, 4):
    x = T[T.study == s]
    w("| %d | %.3f | %.3f | %.3f | %d / %d / %d |" % (s, x.dsr.max(), x.dsr_policy.max(), x.dsr_lenstd.max(),
      int((x.dsr >= 0.95).sum()), int((x.dsr_policy >= 0.95).sum()), int((x.dsr_lenstd >= 0.95).sum())))
w("\nTrials at or above 0.95 under the length-adjusted policy: %s. **All published verdicts stand unchanged**: Studies 1, 2 and 4 are killed on other criteria too; V119/V122 also failed every robustness check (`reports/study3_longhist.md:9`)." % (", ".join(T.index[T.dsr_lenstd >= 0.95]) or "none"))
w("\n## Trials with the largest change (as run → policy)\n")
w("| ID | Study | Sharpe | DSR as run | DSR pooled, same N | DSR policy | DSR length-standardized (see note) |\n|---|---|---|---|---|---|---|")
T["chg"] = (T.dsr - T.dsr_policy).abs()
for t, r in T.sort_values("chg", ascending=False).head(12).iterrows():
    w("| %s | %d | %.2f | %.3f | %.3f | %.3f | %.3f |" % (t, r.study, r.S, r.dsr, r.dsr_pool_Norig, r.dsr_policy, r.dsr_lenstd))
w("\n## Note: pooling Sharpe ratios estimated over different lengths\n")
w("Under the null a Sharpe estimated over Y years has a standard deviation of about 1/√Y, so 5-year Sharpes (Studies 1–2) are "
  "about 4× noisier than 90-year ones (Study 3). Pooling them raw (the approved R2 wording) gives every trial the noise of the "
  "short-window trials. The last column shows a length-standardized variant (variance of S·√Y pooled, then divided by each "
  "trial's Y). It is shown for information; R2 is unchanged until you decide (see the policy draft, open question Q1).\n")
(ROOT / "reports" / "research_review" / "DSR_POOL_DIAGNOSTIC_2026-11-02.md").write_text("\n".join(out) + "\n")
print("\n".join(out))
