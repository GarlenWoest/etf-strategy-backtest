# Study 6 amendment A1 (pre-run): robustness kill condition restored

_2026-11-02. Owner instruction, made before any Study 6 computation. Amends the frozen `research/STUDY6_PROTOCOL_v1.0.md` (sha256 `31ab9993…`, register row STUDY6), which is not edited. Trial V146 has **not been run**; no Study 6 returns, statistics or rule evaluations exist. Cumulative N is **unchanged at 146**._

## Why
- **Correction, not a new design choice:** the frozen protocol conflicts with approved decision **R5**, which treats robustness checks as kill rules (as applied in `research/STUDY5_PROTOCOL_v1.1.md` §6: "R-4 (robustness, as kill rules)" and T3's "Robustness as kill rule").
- Moving Developed ex US entirely to SECONDARY (protocol §2.7 (ii)) dropped its robustness role. A1 restores that role as a sign check.

## Change
Protocol §2.5 gets a fifth kill condition:

> **5. Robustness (R5):** the trial is killed if mean(e_m) on **Developed ex US** (`kf_developed_ex_us_3f_daily`, primary statistic of §2.4, gross of costs) over **1990-07 to 2023-12** is **negative** (point estimate < 0).

- **Significance of Developed ex US stays SECONDARY:** there is no t > 3 requirement there. Its t, Newey–West t and cost comparison are reported under §2.7 (ii) as before.
- **Post-publication (i), US 2009–2023,** stays SECONDARY only: no kill condition.

## Unchanged
- Everything else in the frozen protocol: the rule (days −1..+3), window, primary t > 3 on the US series, kill conditions 1–4, costs, placebo, power and labels.
- Trial count: one trial, V146, cumulative N 146.

## Reporting
The V146 report lists kill condition 5 with its value, and labels it "A1 (pre-run amendment)".
