# Statistics policy for future historical studies (DRAFT v0.2, NOT frozen)

_v0.1 2026-11-02 under owner decision R2. v0.2 the same day, after decision Q1 (approved) and a defect found while preparing the freeze (§6). **Not in force.** It becomes binding only when you approve a final version, which is then frozen by SHA-256 in the protocol register and the research memory. It changes no past result: Studies 1–4 keep their published verdicts._

## 1. Scope

- **Applies to** every historical study registered after this policy is frozen (Study 5 onward), and to every trial in it.
- **Does not apply to** the forward test (F001/F002, any F003+, or the forward observation rules GF1/GF2). Those keep their own pre-registered scoring.

## 2. Primary test for return claims: strict Deflated Sharpe

- **P1. Statistic.** The Deflated Sharpe Ratio (Bailey & López de Prado 2014), as implemented in `src/validate.py:141-162`, on each trial's validation-window excess returns.
- **P2. N is the full cumulative count.** N = every pre-registered historical trial ever run, including the study's own trials (currently 142; 145 if Study 5 runs as proposed). N is never reduced by effective-N, clustering or family arguments.
- **P3. Variance from the full pooled trial set.** The cross-trial Sharpe variance is computed over **all** pre-registered historical trials, past and current, in annualized units, and converted to the trial's return frequency. Pools restricted to one study are not allowed. **The exact pooling form is open: see §6.**
- **P4. Pass mark.** DSR ≥ 0.95.
- **P5. Inputs fixed before results.** Pool membership, the Sharpe definition (excess over the stated cash rate) and the windows are listed in the pre-registration. Past trials' values come from the stored metrics in `results/`.
- **P6. Risk claims.** A trial whose pre-registered claim is about risk (for example volatility targeting: owner decision R4a, 2026-11-02) is decided by the risk criterion written in its pre-registration, fixed before results. Its DSR under P1–P4 is still computed and reported, but it does not decide the trial. A risk-claim trial can never be described as having a return edge.

## 3. Secondary (reported, never decisive)

- **S1. Family-wise test** (SPA or StepM): **not computed** (owner decision R9, 2026-11-02: no `arch` install). Every report says "family-wise test: not computed".
- **S2. Effective N** and the DSR at effective N, for information.
- **S3. The study's own-pool DSR** (the old method), for continuity with Studies 1–4.

## 4. Disclosure

- Every result table shows the primary DSR (P1–P4) with its hurdle in annual Sharpe units, and S2–S3, each labelled as primary or secondary.
- **Reporting rule for Studies 1–4** (owner decision Q1): raw-pooled and length-adjusted values are reported side by side. All published verdicts stand unchanged. V119/V122 also failed every robustness check.

## 5. Evidence

From `reports/research_review/DSR_POOL_DIAGNOSTIC_2026-11-02.md`:
- Study 3's own pool set a hurdle of 0.389, against 0.705 for the raw full pool.
- Study 4's own pool set 0.582, against 0.710.
- No published verdict changes under any variant.

## 6. Open: the pooling form. Q1 was approved, then a defect was found before freezing

**Disclosure required by the owner.** Q1 (length-adjusted pooling) was chosen **after seeing its effect on V119/V122**: it restored their DSR to 0.999. At that point the report showed the length-adjusted column only for Study 3's trials.

**Defect found while preparing the freeze (2026-11-02).**
- The side-by-side table showed that length-adjusted pooling over *all* 142 trials makes the hurdle explode for short windows. The variance of S·√Y is 1.72, dominated by Study 3's 90-year trials (standard deviation 1.59).
- Their Sharpe differences are real asset-class differences, not luck, and multiplying by √91 magnifies them.
- **Result:** Study 1's best DSR falls from 0.727 to 0.110, and Study 4's from 0.368 to 0.020.

The policy was therefore **not frozen**. Options, with hurdles in annual Sharpe at N = 145:

| Option | Rule | 5-year window | 9-year window (Study 5) | 25 years | 91 years | Note |
|---|---|---|---|---|---|---|
| A (R2 as first approved) | Raw Sharpe variance over all trials | 0.712 | 0.712 | 0.712 | 0.712 | Strict; over-strict for long windows (Study 3 best 0.480) |
| B (Q1 as approved) | Variance of S·√Y over all trials, ÷ Y | 1.557 | 1.161 | 0.696 | 0.365 | **Defective:** long-window true dispersion inflates short-window hurdles |
| C | Variance of S·√Y over trials with windows ≤ 30 years, ÷ Y; all trials still count in N | 0.746 | 0.556 | 0.334 | 0.175 | Principled; but excluding Study 3 from the variance estimate is a rule chosen after seeing results. Study 3: 11 trials ≥ 0.95 (DSR tests Sharpe > 0, not the benchmark) |

**Recommendation: A for Study 5.**
- It is the strictest workable option for 9-year windows (0.712 against 0.556 under C).
- It was approved before any of these results were seen.
- Add one limit: any study with validation windows more than twice the pool's typical length (5–9 years) needs a policy amendment before registration. Future long-history studies would then get a reasoned rule (for example C), fixed in advance.

**Decision needed:** A, C, or another rule. After that, this draft is finalised and frozen.
