# Statistics policy v1.1: DRAFT (not frozen)

_Draft 2026-11-02 at the owner's request ("research reset"). v1.0 (`research/STATS_POLICY_v1.0.md`, frozen 2026-11-02) stays in force until you approve v1.1. v1.1 must be **frozen before any new data is touched** for a study it governs. Study 5 was registered under v1.0 and keeps v1.0 (no retroactive change)._

## Changes from v1.0

| | v1.0 (frozen) | v1.1 (draft) |
|---|---|---|
| Primary test | DSR ≥ 0.95 at full cumulative N, raw pooled variance | **Either** t-statistic **> 3.0** on the trial's validation excess returns (Harvey, Liu & Zhu 2016, "…and the Cross-Section of Expected Returns", *RFS* [OV: venue and threshold to verify]), **or** the Romano–Wolf stepdown (StepM) over the full cumulative family (N trials) at family-wise 5%. The study's pre-registration names one, before results |
| DSR | Primary | **Reported only** |
| Variance for the DSR | Pooled across all trials | **Within family:** the trial's own hypothesis family across studies (e.g. FX trend, equity calendar), not pooled across asset classes |
| N | Full cumulative | Unchanged: full cumulative N for StepM; t > 3 needs no N |
| Risk-claim trials (P6) | Fixed pre-registered thresholds | Unchanged |
| Window limit (P7) | 2.5–10 years without amendment | **Amended:** windows over 10 years are allowed **with a written amendment** stating the window, why it is untouched, and the regime split reported |
| Family-wise test implementation | Not computed (no `arch`, R9) | StepM needs a bootstrap. Either an in-house stationary bootstrap (as in `tools/run_study5.py`, tested), or `arch` after an install approval. t > 3 needs neither |

## Hurdle Sharpe (annualized), computed 2026-11-02

v1.0 numbers use N = 145 and the pooled variance 0.0718, so the expected-maximum hurdle is SR0 = 0.712. DSR ≥ 0.95 then needs SR ≈ SR0 + 1.645/√Y (normal returns). v1.1's t > 3 needs SR > 3/√Y. For reference, a one-sided 5% Bonferroni bound at N = 145 (z = 3.39) is shown; StepM is never stricter than Bonferroni.

| Years | v1.0 (DSR ≥ 0.95, N = 145) | v1.1 t > 3 | Bonferroni bound, N = 145 (≥ StepM) |
|---|---|---|---|
| 9 | **1.26** | **1.00** | 1.13 |
| 20 | **1.08** | **0.67** | 0.76 |
| 34 | **0.99** | **0.51** | 0.58 |

**Reading:**
- v1.0's hurdle barely falls with longer windows, because the pooled expected maximum (0.71) dominates.
- v1.1's falls as 1/√Y, so long, untouched windows become decisive.
- At 34 years, a strategy with a true Sharpe of 0.5 is still borderline (t ≈ 2.9).

## Open questions before freezing

1. t > 3 or StepM as the default primary (recommendation: **t > 3 primary, StepM reported**: simple, needs no bootstrap or install, and is near the Bonferroni bound for N ≈ 150).
2. Family definitions for the within-family DSR variance (proposal: by economic mechanism, e.g. "time-series trend", "carry", "calendar", "volatility targeting", "reversal").
3. Whether v1.1 also applies to risk-claim trials' Sharpe reporting (proposal: reported only, as in v1.0 P6).
