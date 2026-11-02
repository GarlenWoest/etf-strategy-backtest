# Statistics policy for historical studies, v1.1 (FROZEN)

_Frozen 2026-11-02 under owner decision 4 (2026-11-02): **t > 3 primary at full cumulative N; Romano–Wolf and DSR reported only.** Freeze hash, date and commit are recorded in `research/PROTOCOL_REGISTER.csv` and the research memory, before any Study 6 data is downloaded. It applies to studies registered after this freeze (Study 6 onward). **Study 5 stays under v1.0** (registered before; no retroactive change). Draft: `research/STATS_POLICY_v1.1_DRAFT.md` (kept)._

## Changes from v1.0

| | v1.0 | v1.1 |
|---|---|---|
| Primary test | DSR ≥ 0.95 at full cumulative N, raw pooled variance | **t-statistic > 3.0** on the trial's pre-registered test-window excess returns (Harvey, Liu & Zhu 2016 [OV]), at **full cumulative N**: the threshold is fixed and does not fall as N grows |
| DSR | Primary | **Reported only** (within-family variance) |
| Romano–Wolf StepM | Not computed | **Reported only** over the full cumulative family, when the bootstrap is available; never decisive |
| Variance for the DSR | Pooled across all trials | **Within family:** the trial's own hypothesis family across studies (e.g. FX trend, equity calendar), not pooled across asset classes |
| N | Full cumulative | Unchanged: full cumulative N is counted and reported; t > 3 is the decision |
| Risk-claim trials (P6) | Fixed pre-registered thresholds | Unchanged |
| Window limit (P7) | 2.5–10 years without amendment | **Amended:** windows over 10 years are allowed **with a written amendment** stating the window, why it is untouched, and the regime split reported |
| Family-wise test implementation | Not computed (no `arch`, R9) | StepM needs a bootstrap. Either an in-house stationary bootstrap (as in `tools/run_study5.py`, tested), or `arch` after an install approval. t > 3 needs neither |

## Rules carried over from v1.0 unchanged

- P5: inputs fixed before results.
- P6: risk-claim trials are decided by fixed pre-registered thresholds, and count in N.
- Disclosure (§4): every table shows the primary test, its threshold in annual Sharpe for the window, and the reported-only statistics, each labelled.

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

## Decisions recorded at freeze

- **Primary test:** t > 3, on the test-window excess returns named in each pre-registration.
- **Reported only:** Romano–Wolf StepM and the DSR (within-family variance).
- **P7:** windows over 10 years are allowed with a written amendment in the study's pre-registration.
- **Family definitions for the within-family DSR:** by economic mechanism, named in each pre-registration.
