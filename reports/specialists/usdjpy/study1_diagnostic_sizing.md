# DIAGNOSTIC, SIZING BUG CHECK: USD/JPY study 1

_Run 2026-10-26T15:57:04Z. **Diagnostic only: not new trials, no N increase, no verdict changes.** The official results stay as in `study1_kill_table.md`._

## Answer first

- **Would any kill verdict differ with sizing reset to 1x at each weekly decision? NO.** All 8 trials are killed under both sizing rules.
- **Did counting cap trims as position changes (frozen K4) change any verdict? NO.**
- Always-long (UB02) validation Sharpe: 0.24 frozen, 0.24 with weekly re-sizing; its exposure at the end of 2023: 0.32x frozen, 1.00x re-sized.

## Per trial (validation 2015–2023, 1x costs)

| ID | Val Sharpe frozen | Val Sharpe re-sized | DSR frozen | DSR re-sized | Criteria failed (frozen) | Criteria failed (re-sized) | Verdict frozen / re-sized |
|---|---|---|---|---|---|---|---|
| V135 | 0.38 | 0.35 | 0.274 | 0.257 | K2, K5 | K2, K5 | KILLED / KILLED |
| V136 | 0.22 | 0.21 | 0.142 | 0.143 | K1, K2 | K1, K2 | KILLED / KILLED |
| V137 | -0.06 | -0.06 | 0.027 | 0.031 | K1, K2, K3, K5, K6 | K1, K2, K3, K5, K6 | KILLED / KILLED |
| V138 | -0.11 | -0.10 | 0.020 | 0.022 | K1, K2, K3, K5, K6 | K1, K2, K3, K5, K6 | KILLED / KILLED |
| V139 | 0.09 | 0.09 | 0.070 | 0.075 | K1, K2 | K1, K2, K5 | KILLED / KILLED |
| V140 | 0.24 | 0.24 | 0.153 | 0.164 | K2, K5 | K1, K2, K5 | KILLED / KILLED |
| V141 | -0.09 | -0.08 | 0.023 | 0.026 | K1, K2, K3, K6 | K1, K2, K3, K6 | KILLED / KILLED |
| V142 | 0.47 | 0.47 | 0.368 | 0.391 | K2, K5 | K2, K5 | KILLED / KILLED |
| UB02 | 0.24 | 0.24 | — | — | — | — | benchmark |

## K4 counting check (frozen run)

| ID | All trades (as counted) | True position changes | Median hold (days) | K4 as counted | K4 on true changes |
|---|---|---|---|---|---|
| V135 | 94 | 13 | 465 | pass | pass |
| V136 | 120 | 31 | 18 | pass | pass |
| V137 | 963 | 200 | 20 | pass | pass |
| V138 | 765 | 131 | 20 | pass | pass |
| V139 | 478 | 167 | 14 | pass | pass |
| V140 | 396 | 112 | 34 | pass | pass |
| V141 | 1180 | 215 | 14 | pass | pass |
| V142 | 907 | 131 | 14 | pass | pass |

## Notes

- The frozen rerun reproduces the official validation Sharpe ratios exactly (checked by assertion).
- Weekly re-sizing pays costs on every notional change; DSR uses the cross-trial variance of the 8 re-sized trials at N = 142.
- Criteria whose list changed between the two sizing rules: V139: K1,K2 -> K1,K2,K5; V140: K2,K5 -> K1,K2,K5.
