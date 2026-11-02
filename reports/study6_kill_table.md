# Study 6: V146 turn-of-month equity, kill table and report (run 2026-11-02 22:25 UTC, after Study 5)

_Protocol `research/STUDY6_PROTOCOL_v1.0.md` (frozen, sha256 `31ab9993…`) + amendment A1 (frozen pre-run, sha256 `a35a1942…`; both hash-checked by the runner). STATS_POLICY v1.1 (t > 3 primary). One trial, cumulative N = 146. Data: Ken French daily US and Developed ex US, 1990-07-02..2023-12-29; 2024+ locked. Runner `tools/run_study6.py` (implementation choices I-1..I-10 fixed before the run). One run, no reruns. Label: **weak confirmation: published-sample overlap**._

## Verdict

**V146: FAIL (killed)** on **K1** (t 1.84 ≤ 3.0) and **K2** (costs at 2×). K3, K4 and K5 (A1) pass.

## Primary and kill conditions (US unless stated; e_m = TOM-day mean minus rest-of-month mean, daily excess, gross)

| | Value | Result |
|---|---|---|
| Month-turns | 401 (1990-07..2023-11; the December 2023 turn needs 2024 and is excluded) | — |
| mean(e_m), sd | +0.054% per day, 0.584% | — |
| **K1** plain t > 3.0 (primary) | **t = 1.84** (Newey–West lag 3: 1.86) | **fail** |
| **K2** TOM net per unit of time in market vs always long, at 2× costs | TOM **−6.0%** a year vs always long +9.0% (1×: +6.8% vs +9.0%; 3×: −18.8%) | **fail** (also lower at 1×) |
| **K3** placebo (+10 trading days) mean(e_m) ≥ TOM | placebo +0.035% < TOM +0.054% | pass |
| **K4** sign reversal in a half | 1990-07..2006-12: +0.091% (198 turns); 2007-01..2023-12: +0.018% (203) | pass (both positive) |
| **K5** (A1) Developed ex US mean(e_m) < 0 | +0.084% | pass |

## SECONDARY (pre-registered; cannot change the V146 verdict)

| | Turns | mean(e_m) | t (NW) | TOM net vs always long, 1× / 2× costs |
|---|---|---|---|---|
| (i) US post-publication 2009-01..2023-11 | 179 | +0.021% | 0.49 (0.55) | +9.1% vs +14.3% / +0.3% vs +14.3% |
| (ii) Developed ex US 1990-07..2023-11 | 401 | +0.084% | **3.05** (3.22) | **+8.2% vs +3.8%** / −4.6% vs +3.8% |

- **(ii) clears t > 3 on its own, but it is SECONDARY** and cannot change the verdict. It is also mostly within the published international samples, and it loses to always long at 2× costs.
- **(i) has t 0.49**, with power 0.16 at d = 0.15 (protocol §2.8). Read as consistent with decay, not as a refutation.
- **Halves:** the US effect fell from +0.091% to +0.018% per day.

## Statistics (STATS_POLICY v1.1; reported only)

| | Value | Label |
|---|---|---|
| Primary t (US) | 1.84 vs threshold 3.0 | **primary** |
| Net 1× strategy Sharpe (annual, daily series incl. cash days) | 0.17 | reported |
| DSR at N = 146 (I-9: a one-trial "calendar" family, so null dispersion 1/T is used as the variance) | 0.045 (hurdle 0.46 annual Sharpe) | reported |
| Romano–Wolf (single trial = plain test), one-sided p | 0.033 | reported |
| Turnover | 24.1 one-way trades a year | reported |

## Reading
- **The US turn-of-month effect is positive in both halves but not significant** at the pre-registered threshold. After the frozen stock costs (0.07–0.34% one-way, 24 trades a year) it does not beat always long, even at 1× costs.
- **Developed ex US:** the effect is larger and nominally significant, but secondary.
- No forward rule, gate or position is affected.
