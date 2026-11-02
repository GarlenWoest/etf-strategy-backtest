# Study 5: kill table and report (run 2026-11-02, after the 17:22 ET checks)

_Protocol `research/STUDY5_PROTOCOL_v1.1.md` (frozen, sha256 `35d1b33a…`), STATS_POLICY v1.0 (frozen). Trials V143–V145, cumulative N = 145. Data: Board H.10 noon rates, Board H.15 3-month bill, Ken French daily; 1990-01-02..2023-12-29; 2024+ locked. Runner `tools/run_study5.py` (implementation choices I-1..I-12 fixed before the run). **Spot-only: every figure excludes carry.** Family-wise test: not computed (R9)._

**Run record.**
- **Gate:** the 16:45 ETF run passed, and the 17:02 roll passed (booked at the 17:17 scan after a DELAYED quote at 17:02; amounts verified).
- **First attempt:** crashed in `load()` before any data was read (a path precedence bug; no output). It was fixed in commit `bba033e` as a disclosed bug fix.
- **Second attempt:** the one run reported here.

## Verdicts

| Trial | Claim | Verdict | Failed on |
|---|---|---|---|
| **V143** H5-B vol-target overlay, GBP/USD | Risk | **FAIL** | R-2, R-3 (and under R-4: R-2, R-3 at 2×/3× costs and delay), R-5 |
| **V144** H5-B vol-target overlay, USD/JPY (weak confirmation: years seen in aggregate by Study 4) | Risk | **FAIL** | R-2, R-3 (and under R-4: same) |
| **V145** G1 month-end equity-hedge flow, GBP/USD | Return | **FAIL** (killed) | K2 only (DSR 0.19 < 0.95) |

As registered in advance, V145's expected outcome was rejection.

## V143 / V144: risk criteria (validation 2015-01-02..2023-12-29, scaled vs unscaled; excludes carry)

| | V143 GBP/USD scaled | unscaled | V144 USD/JPY scaled | unscaled |
|---|---|---|---|---|
| Base sign (IS mean daily log return) | −1 (short GBP) | | −1 (short USD) | |
| Realized vol (ann.) | 9.08% | 9.76% | 8.17% | 9.09% |
| R-1 bootstrap 5th / 95th pct of vol(unscaled) − vol(scaled) | 0.50 / 0.89 pp | | 0.72 / 1.13 pp | |
| **R-1** (lower, 5th pct > 0) | **pass** | | **pass** | |
| Max drawdown | −19.44% | −19.76% | −30.00% | −31.81% |
| **R-2** (≥ 25% smaller; needs ≤ 14.82% / 23.86%) | **fail** (1.6% smaller) | | **fail** (5.7% smaller) | |
| Worst calendar month | −5.47% | −5.86% | −8.30% | −8.22% |
| **R-3** (loss ≥ 25% smaller; needs ≤ 4.39% / 6.17%) | **fail** (6.6% smaller) | | **fail** (1.0% larger) | |
| **R-4** at 2× costs, 3× costs, one extra FX day | R-1 pass; R-2/R-3 fail in all three | | R-1 pass; R-2/R-3 fail in all three | |
| **R-5** in-sample direction (IS from 1990-04-02): vol / \|maxDD\| / worst month lower | **fail** (vol 8.42 < 9.40, but maxDD −27.57 vs −27.36 worse; worst month −5.62 vs −8.50 better) | | **pass** (9.48 < 10.89; −38.61 vs −39.14; −7.57 vs −9.47) | |
| **K7** stress lows (≥ $2,000 of $10,000) | pass (lowest $9,501, IS 1998) | | pass (lowest $7,910, val 2022) | |
| Overlay validation Sharpe (reported only; excludes carry) | 0.18 | | −0.28 | |

**Reading:** volatility targeting reduced realized volatility in both pairs, and that reduction is robust to costs and a delay. It did **not** reduce drawdowns or the worst month by the pre-registered 25% margins. A pass would have meant "reduced risk", never "has an edge"; neither passed.

## V145: return criteria (validation 2015-01-02..2023-12-29; excludes carry)

| Criterion | Value | Result |
|---|---|---|
| Events | 72 triggers, 70 with data (2 no-data); IS 188 (+1 no-data) | — |
| **K1** mean net excess per event > 0 and > placebo | +0.094% vs placebo −0.006% (56 events) | pass |
| **K2** DSR ≥ 0.95 at N = 145 (pooled variance, hurdle 0.72 annual Sharpe) | **DSR 0.19**; Sharpe 0.44 (daily series I-10) | **fail** |
| **K3** mean > 0 at 2× and 3× costs | +0.064% / +0.034% | pass |
| **K4** ≥ 30 validation events | 70 | pass |
| **K5** thresholds ±0.015 / ±0.03 keep the sign | +0.053% / +0.067% | pass |
| **K6** validation mean ≥ ½ in-sample mean (IS > 0) | 0.094% vs ½ × 0.051% | pass |
| **K7** no fall to 20% of capital | low $9,901 | pass |
| Robustness: entry one day earlier keeps the sign | +0.105% | pass |
| Validation t of the per-event mean (reported) | 1.33 (sd 0.59% per event) | — |

**Reading:** the sign is consistent across every robustness check, but the effect is far from the multiple-testing hurdle (t 1.33). The month-end flow result is a **non-confirmation**, not evidence of no effect.

## Statistics (policy §4)

| | V143 | V144 | V145 | Label |
|---|---|---|---|---|
| **P1–P4 DSR**, N = 145, raw pooled variance 0.0741 (annual Sharpe²), hurdle **0.72** annual Sharpe | 0.050 | 0.001 | 0.189 | **primary** (decisive only for V145; V143/V144 are risk claims, Sharpe reported only, P6) |
| S1 family-wise test | not computed | not computed | not computed | secondary |
| S2 effective N of Study 5's trials (participation ratio, 2,246 aligned days) | 2.88 | | | secondary |
| S3 own-pool DSR (N = 3, Study 5 variance; hurdle 0.31 annual Sharpe) | 0.342 | 0.040 | 0.660 | secondary |

## What follows (owner decisions; nothing changes automatically)
- No forward rule, gate or position is affected. Study 5 was historical only.
- **Next, already authorized:** the post-hoc supplementary for V143/V144 (vs a constant exposure at the same average weight), labelled POST-HOC and unable to change these verdicts.
