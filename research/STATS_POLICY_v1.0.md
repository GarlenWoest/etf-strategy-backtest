# Statistics policy for historical studies, v1.0 (FROZEN)

_Frozen 2026-11-02 under owner decisions R2, Q1 (approved, then withdrawn), the pooling decision (option A), and P6 with two conditions, all of 2026-11-02. The freeze hash, date and commit are recorded in `research/PROTOCOL_REGISTER.csv` and the research memory. Any change is a new version with its own hash, written before the study it affects is registered. **This policy changes no past result:** Studies 1–4 keep their published verdicts. Drafts v0.1/v0.2: `research/STATS_POLICY_DRAFT.md` (kept)._

## 1. Scope

- **Applies to** every historical study registered after 2026-11-02 (Study 5 onward), and to every trial in it.
- **Does not apply to** forward rules (F001/F002, any F003+, and the GF1/GF2 observation rules). Those keep their own pre-registered scoring.

## 2. Primary test for return claims: strict Deflated Sharpe

- **P1. Statistic.** The Deflated Sharpe Ratio (Bailey & López de Prado 2014), as implemented in `src/validate.py:141-162`, on each trial's validation-window excess returns.
- **P2. N is the full cumulative count.** N = every pre-registered historical trial ever run, including the study's own trials (142 before Study 5). N is never reduced by effective-N, clustering or family arguments.
- **P3. Variance from the full pooled trial set, raw (option A).**
  - The cross-trial variance is the sample variance (ddof = 1) of the **annualized** Sharpe ratios of **all** pre-registered historical trials: every past trial, using the Sharpe its study reported (`results/` metrics; for Study 3 the full-span Sharpe), plus the current study's trials.
  - It is converted to the trial's return frequency (÷ 252 for daily, ÷ 12 for monthly) before computing the expected maximum.
  - No length adjustment is applied, and no study-only pool is allowed.
  - Reference value before Study 5: variance 0.0718, hurdle ≈ 0.712 annual Sharpe at N = 145 (`reports/research_review/DSR_POOL_DIAGNOSTIC_2026-11-02.md`; `tools/diag_dsr_pool.py`).
- **P4. Pass mark.** DSR ≥ 0.95.
- **P5. Inputs fixed before results.** Pool membership, the Sharpe definition (excess over the stated cash rate) and the windows are listed in the pre-registration.
- **P6. Risk claims.** A trial whose pre-registered claim is about risk (for example volatility targeting) is decided by the risk criterion written in its pre-registration. Its DSR is computed and reported but does not decide the trial. Two conditions apply:
  - **(a)** risk-claim trials **count in cumulative N** like any trial, and their Sharpe ratios join the P3 pool;
  - **(b)** their pass thresholds are **fixed numbers** written in the protocol before any run.

  A risk-claim pass is reported as "reduced risk", never as an edge.
- **P7. Window-length limit.**
  - The pool median test-window length is **5 years** (Studies 1–2: 5 years, 118 trials; Study 4: 9 years, 8 trials; Study 3: about 91 years, 16 trials).
  - Any study whose test (validation) windows are **more than 2× longer or shorter** than that median (outside 2.5–10 years) needs a **written amendment to this policy before registration**, stating how its hurdle is computed.
  - The median is recomputed from the pool at each registration.

## 3. Secondary (reported, never decisive)

- **S1. Family-wise test** (SPA or StepM): not computed (owner decision R9). Every report says "family-wise test: not computed".
- **S2. Effective N** and the DSR at effective N, for information.
- **S3. The study's own-pool DSR** (the method of Studies 1–4), for continuity.

## 4. Disclosure

- Every result table shows the P1–P4 DSR with its hurdle in annual Sharpe units, and S1–S3, each labelled primary or secondary.
- **Studies 1–4:** raw-pooled and length-adjusted DSRs are reported side by side (`reports/research_review/DSR_POOL_DIAGNOSTIC_2026-11-02.md`). All published verdicts stand unchanged; V119/V122 also failed every robustness check.

## 5. Decision record (required disclosure)

- **Q1, approved then withdrawn.**
  - Length-adjusted pooling (variance of S·√Y over all trials, divided by each trial's Y) was approved on 2026-11-02 **after seeing its effect on V119/V122**: it restored their DSR to 0.999.
  - The table shown at that time listed the length-adjusted column only for Study 3's trials.
  - Preparing the freeze, the full side-by-side table showed the variance of S·√Y was 1.72, dominated by Study 3's 90-year trials (standard deviation 1.59). Their Sharpe differences are real asset-class differences, not luck, and multiplying by √91 magnifies them.
  - That raised the hurdle to 1.55 annual Sharpe for 5-year windows and 1.16 for 9-year windows: Study 1's best DSR fell from 0.727 to 0.110, and Study 4's from 0.368 to 0.020.
  - **Q1 was withdrawn for that reason.**
- **Option C, rejected.** Length-adjusted pooling restricted to windows ≤ 30 years was rejected because its cut-off was chosen after seeing results.
- **Option A, adopted.** It was the original R2 decision, made before any of these results were seen. P7 handles studies whose windows differ greatly from the pool's.
