# ENGINE COMPARISON v1 vs v2, DIAGNOSTIC: USD/JPY study 1 targets

_Run 2026-10-26T16:20:02Z. Engine v2: `fx_engine_v2 1.0 (2026-10-26)`. **Diagnostic only: not new trials, no N increase, no verdict changes.** The official results stay as in `usdjpy/study1_kill_table.md`; v1 reproduced them exactly (checked by assertion)._

## Answer first

- **Would any frozen kill verdict differ under engine v2? NO.** All 8 trials are killed under both engines.
- **Sizing (D1):** always-long held 0.52x of equity on average under v1 (0.32x at the end of 2023) and 0.99x under v2 (1.00x at the end).
- **K4 counting (D2):** v1's frozen count included cap trims; v2 counts only open/close/reverse (table 2).
- **Always-long validation Sharpe:** 0.24 (v1) vs 0.24 (v2). Best trial Deflated Sharpe at N = 142: 0.37 (v1, V142) vs 0.39 (v2, V142); the bar is 0.95.

## 1. Per trial, validation 2015–2023, 1x costs

| ID | Val Sharpe v1 | Val Sharpe v2 | DSR v1 | DSR v2 | Mean exposure held v1 / v2 | Criteria failed v1 | Criteria failed v2 |
|---|---|---|---|---|---|---|---|
| V135 | 0.38 | 0.35 | 0.274 | 0.257 | 0.77x / 0.99x | K2, K5 | K2, K5 |
| V136 | 0.22 | 0.21 | 0.142 | 0.142 | 0.67x / 0.99x | K1, K2 | K1, K2 |
| V137 | -0.06 | -0.06 | 0.027 | 0.031 | 0.96x / 1.00x | K1, K2, K3, K5, K6 | K1, K2, K3, K5, K6 |
| V138 | -0.11 | -0.10 | 0.020 | 0.022 | 0.95x / 1.00x | K1, K2, K3, K5, K6 | K1, K2, K3, K5, K6 |
| V139 | 0.09 | 0.09 | 0.070 | 0.076 | 0.96x / 0.99x | K1, K2 | K1, K2, K5 |
| V140 | 0.24 | 0.24 | 0.153 | 0.163 | 0.95x / 0.99x | K2, K5 | K1, K2, K5 |
| V141 | -0.09 | -0.09 | 0.023 | 0.025 | 0.97x / 1.00x | K1, K2, K3, K6 | K1, K2, K3, K6 |
| V142 | 0.47 | 0.47 | 0.368 | 0.390 | 0.96x / 1.00x | K2, K5 | K2, K5 |
| UB02 | 0.24 | 0.24 | — | — | 0.52x / 0.99x | benchmark | benchmark |

## 2. Trades, 1991–2023 (in-sample + validation)

| ID | v1 trades (frozen K4 count) | v1 true direction changes | v2 open/close/reverse | v2 re-sizes | v2 cap trims | Costs v1 / v2 (USD) | Max exposure v1 / v2 |
|---|---|---|---|---|---|---|---|
| V135 | 94 | 13 | 13 | 1048 | 1410 | 36 / 141 | 1.00x / 1.00x |
| V136 | 120 | 31 | 31 | 1089 | 1475 | 79 / 179 | 1.00x / 1.00x |
| V137 | 963 | 200 | 200 | 1521 | 4076 | 1719 / 1820 | 1.00x / 1.00x |
| V138 | 765 | 131 | 131 | 1590 | 4056 | 440 / 476 | 1.00x / 1.00x |
| V139 | 478 | 167 | 167 | 764 | 1162 | 404 / 466 | 1.00x / 1.00x |
| V140 | 396 | 112 | 112 | 813 | 1162 | 298 / 369 | 1.00x / 1.00x |
| V141 | 1180 | 215 | 215 | 1506 | 4286 | 1208 / 1314 | 1.00x / 1.00x |
| V142 | 907 | 131 | 131 | 1590 | 4240 | 384 / 419 | 1.00x / 1.00x |
| UB02 | 61 | 1 | 1 | 1720 | 2338 | 2 / 117 | 1.00x / 1.00x |

## Notes

- v2 settings: re-size to the target at every weekly decision (band 0), cap 1x at every close, same costs (0.015% one-way, 0.75%/yr rollover markup), same lag (1 FX day), same data and rates (DTB3, JGB 1Y proxy).
- A re-size or cap trim pays costs on the traded amount; v2's higher trade count is mostly small re-sizes.
- v2's daily P&L differs from v1 even with identical exposure because v1 re-sizes the yen leg every day for free (D3); over one day after entry the two engines agree (unit test).
- Criteria lists are applied mechanically for this diagnostic only; they are not new verdicts.
