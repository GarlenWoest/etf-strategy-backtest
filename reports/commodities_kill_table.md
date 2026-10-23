# Commodity study, Phase 6: kill table

## Result

- **Survivors: NO.** 0 of 26 trials survive; 26 are killed. Under the pre-agreed rules, nothing goes to the holdout, Phase 7 or Phase 10 alerts.
- **Best Deflated Sharpe at cumulative N = 118: 0.430** (V108, I04_dual_momentum winner_leveraged, lookback_months=6, uses oil ⚑), against 0.95 required.
- **Best idea vs the 70/30 SPY/GLD benchmark (validation 2019–2023):**

| | Val Sharpe | Val CAGR | Val max DD | DSR (N=118) |
|---|---|---|---|---|
| V108 (best DSR) | 0.63 | 23.7% | -66.9% | 0.430 |
| 70/30 SPY/GLD (CB09) | 0.82 | 14.4% | -25.2% | benchmark |
| Equal weight GLD/SLV/USO (CB08, K1) | 0.42 | 9.0% | -40.7% | benchmark |
| GLD buy-and-hold (CB01) | 0.56 | 9.6% | -22.0% | benchmark |
| SPY buy-and-hold (CB07) | 0.72 | 15.8% | -33.7% | benchmark |

⚑ = uses oil. **Oil flag:** USO structure change Apr-2020 (front-month -> multi-month futures; 1:8 reverse split 2020-04-29).

| Criterion | Trials failing it | Failing only this one |
|---|---|---|
| K1 OOS Sharpe does not beat own buy-and-hold and equal weight | 20 | 0 |
| K2 Deflated Sharpe probability (N=118) below 0.95 | 26 | 2 |
| K3 Profitable at 1x but not at 2x costs | 0 | 0 |
| K4 Too few OOS trades (<30), or <5 OOS years for monthly strategies | 13 | 0 |
| K5 Edge disappears one grid step away | 18 | 0 |
| K6 OOS Sharpe below half of in-sample Sharpe | 6 | 0 |
| K7 Fell to $20 or below in a stress period | 0 | 0 |

The criteria are the ETF study's, applied mechanically and unchanged. K1's equal weight here is CB08 (GLD/SLV/USO, Sharpe 0.42); K2 uses N = 118. A trial is killed if any criterion fails.

## All 26 trials

| ID | Strategy | Trades in | Params | Val Sharpe | Own B&H | EW | DSR | Round trips | IS Sharpe | Verdict | Reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V093 | I01_tsmom_basket | GLD/SLV/USO ⚑ | lookback_months=3 | 0.33 | 0.42 | 0.42 | 0.202 | 27 | -0.17 | **KILLED** | K1 OOS Sharpe 0.33 does not beat own buy-and-hold 0.42 and equal weight 0.42; K2 DSR 0.202 < 0.95 |
| V094 | I01_tsmom_basket | UGL/AGQ/UCO ⚑ | lookback_months=3 | 0.27 | 0.42 | 0.42 | 0.164 | 27 | -0.20 | **KILLED** | K1 OOS Sharpe 0.27 does not beat own buy-and-hold 0.42 and equal weight 0.42; K2 DSR 0.164 < 0.95 |
| V095 | I01_tsmom_basket | GLD/SLV/USO ⚑ | lookback_months=6 | 0.57 | 0.42 | 0.42 | 0.377 | 20 | 0.35 | **KILLED** | K2 DSR 0.377 < 0.95; K5 neighbor(s) V093(lookback_months=3),V097(lookback_months=12) fail out of sample |
| V096 | I01_tsmom_basket | UGL/AGQ/UCO ⚑ | lookback_months=6 | 0.48 | 0.42 | 0.42 | 0.309 | 20 | 0.31 | **KILLED** | K2 DSR 0.309 < 0.95; K5 neighbor(s) V094(lookback_months=3),V098(lookback_months=12) fail out of sample |
| V097 | I01_tsmom_basket | GLD/SLV/USO ⚑ | lookback_months=12 | 0.32 | 0.42 | 0.42 | 0.195 | 13 | -0.01 | **KILLED** | K1 OOS Sharpe 0.32 does not beat own buy-and-hold 0.42 and equal weight 0.42; K2 DSR 0.195 < 0.95 |
| V098 | I01_tsmom_basket | UGL/AGQ/UCO ⚑ | lookback_months=12 | 0.26 | 0.42 | 0.42 | 0.162 | 13 | -0.05 | **KILLED** | K1 OOS Sharpe 0.26 does not beat own buy-and-hold 0.42 and equal weight 0.42; K2 DSR 0.162 < 0.95 |
| V099 | I03_vol_scaled_trend | GLD | target_vol=15% | 0.17 | 0.56 | 0.42 | 0.118 | 9 | 0.25 | **KILLED** | K1 OOS Sharpe 0.17 does not beat own buy-and-hold 0.56 and equal weight 0.42; K2 DSR 0.118 < 0.95; K4 9 OOS round trips < 30; K5 neighbor(s) V100(target_vol=20%) fail out of sample |
| V100 | I03_vol_scaled_trend | GLD | target_vol=20% | 0.15 | 0.56 | 0.42 | 0.107 | 10 | 0.29 | **KILLED** | K1 OOS Sharpe 0.15 does not beat own buy-and-hold 0.56 and equal weight 0.42; K2 DSR 0.107 < 0.95; K4 10 OOS round trips < 30; K5 neighbor(s) V099(target_vol=15%),V101(target_vol=25%) fail out of sample |
| V101 | I03_vol_scaled_trend | GLD | target_vol=25% | 0.13 | 0.56 | 0.42 | 0.101 | 11 | 0.28 | **KILLED** | K1 OOS Sharpe 0.13 does not beat own buy-and-hold 0.56 and equal weight 0.42; K2 DSR 0.101 < 0.95; K4 11 OOS round trips < 30; K5 neighbor(s) V100(target_vol=20%) fail out of sample; K6 OOS Sharpe 0.13 < half of in-sample 0.28 |
| V102 | I03_vol_scaled_trend | GLD/SLV/USO ⚑ | target_vol=15% | 0.31 | 0.42 | 0.42 | 0.192 | 27 | 0.13 | **KILLED** | K1 OOS Sharpe 0.31 does not beat own buy-and-hold 0.42 and equal weight 0.42; K2 DSR 0.192 < 0.95; K4 27 OOS round trips < 30; K5 neighbor(s) V103(target_vol=20%) fail out of sample |
| V103 | I03_vol_scaled_trend | GLD/SLV/USO ⚑ | target_vol=20% | 0.27 | 0.42 | 0.42 | 0.166 | 29 | 0.16 | **KILLED** | K1 OOS Sharpe 0.27 does not beat own buy-and-hold 0.42 and equal weight 0.42; K2 DSR 0.166 < 0.95; K4 29 OOS round trips < 30; K5 neighbor(s) V102(target_vol=15%),V104(target_vol=25%) fail out of sample |
| V104 | I03_vol_scaled_trend | GLD/SLV/USO ⚑ | target_vol=25% | 0.31 | 0.42 | 0.42 | 0.191 | 30 | 0.14 | **KILLED** | K1 OOS Sharpe 0.31 does not beat own buy-and-hold 0.42 and equal weight 0.42; K2 DSR 0.191 < 0.95; K5 neighbor(s) V103(target_vol=20%) fail out of sample |
| V105 | I04_dual_momentum | winner_1x ⚑ | lookback_months=3 | 0.58 | 0.42 | 0.42 | 0.387 | 16 | -0.03 | **KILLED** | K2 DSR 0.387 < 0.95 |
| V106 | I04_dual_momentum | winner_leveraged ⚑ | lookback_months=3 | 0.57 | 0.42 | 0.42 | 0.377 | 16 | -0.06 | **KILLED** | K2 DSR 0.377 < 0.95 |
| V107 | I04_dual_momentum | winner_1x ⚑ | lookback_months=6 | 0.63 | 0.42 | 0.42 | 0.428 | 14 | 0.19 | **KILLED** | K2 DSR 0.428 < 0.95; K5 neighbor(s) V109(lookback_months=12) fail out of sample |
| V108 | I04_dual_momentum | winner_leveraged ⚑ | lookback_months=6 | 0.63 | 0.42 | 0.42 | 0.430 | 14 | 0.14 | **KILLED** | K2 DSR 0.430 < 0.95; K5 neighbor(s) V110(lookback_months=12) fail out of sample |
| V109 | I04_dual_momentum | winner_1x ⚑ | lookback_months=12 | 0.32 | 0.42 | 0.42 | 0.196 | 11 | -0.02 | **KILLED** | K1 OOS Sharpe 0.32 does not beat own buy-and-hold 0.42 and equal weight 0.42; K2 DSR 0.196 < 0.95 |
| V110 | I04_dual_momentum | winner_leveraged ⚑ | lookback_months=12 | 0.30 | 0.42 | 0.42 | 0.180 | 11 | -0.07 | **KILLED** | K1 OOS Sharpe 0.30 does not beat own buy-and-hold 0.42 and equal weight 0.42; K2 DSR 0.180 < 0.95 |
| V111 | I05_real_yield | GLD | slow=120 | 0.26 | 0.56 | 0.42 | 0.159 | 10 | 0.39 | **KILLED** | K1 OOS Sharpe 0.26 does not beat own buy-and-hold 0.56 and equal weight 0.42; K2 DSR 0.159 < 0.95; K4 10 OOS round trips < 30; K5 neighbor(s) V113(slow=250) fail out of sample |
| V112 | I05_real_yield | UGL | slow=120 | 0.16 | 0.56 | 0.42 | 0.112 | 10 | 0.34 | **KILLED** | K1 OOS Sharpe 0.16 does not beat own buy-and-hold 0.56 and equal weight 0.42; K2 DSR 0.112 < 0.95; K4 10 OOS round trips < 30; K5 neighbor(s) V114(slow=250) fail out of sample; K6 OOS Sharpe 0.16 < half of in-sample 0.34 |
| V113 | I05_real_yield | GLD | slow=250 | 0.49 | 0.56 | 0.42 | 0.314 | 2 | 0.16 | **KILLED** | K1 OOS Sharpe 0.49 does not beat own buy-and-hold 0.56; K2 DSR 0.314 < 0.95; K4 2 OOS round trips < 30; K5 neighbor(s) V111(slow=120) fail out of sample |
| V114 | I05_real_yield | UGL | slow=250 | 0.39 | 0.56 | 0.42 | 0.237 | 2 | 0.11 | **KILLED** | K1 OOS Sharpe 0.39 does not beat own buy-and-hold 0.56 and equal weight 0.42; K2 DSR 0.237 < 0.95; K4 2 OOS round trips < 30; K5 neighbor(s) V112(slow=120) fail out of sample |
| V115 | I06_dollar_trend | GLD | sma=100 | 0.18 | 0.56 | 0.42 | 0.121 | 14 | 0.52 | **KILLED** | K1 OOS Sharpe 0.18 does not beat own buy-and-hold 0.56 and equal weight 0.42; K2 DSR 0.121 < 0.95; K4 14 OOS round trips < 30; K5 neighbor(s) V117(sma=200) fail out of sample; K6 OOS Sharpe 0.18 < half of in-sample 0.52 |
| V116 | I06_dollar_trend | UGL | sma=100 | 0.09 | 0.56 | 0.42 | 0.084 | 14 | 0.48 | **KILLED** | K1 OOS Sharpe 0.09 does not beat own buy-and-hold 0.56 and equal weight 0.42; K2 DSR 0.084 < 0.95; K4 14 OOS round trips < 30; K5 neighbor(s) V118(sma=200) fail out of sample; K6 OOS Sharpe 0.09 < half of in-sample 0.48 |
| V117 | I06_dollar_trend | GLD | sma=200 | 0.01 | 0.56 | 0.42 | 0.060 | 7 | 0.48 | **KILLED** | K1 OOS Sharpe 0.01 does not beat own buy-and-hold 0.56 and equal weight 0.42; K2 DSR 0.060 < 0.95; K4 7 OOS round trips < 30; K5 neighbor(s) V115(sma=100) fail out of sample; K6 OOS Sharpe 0.01 < half of in-sample 0.48 |
| V118 | I06_dollar_trend | UGL | sma=200 | -0.05 | 0.56 | 0.42 | 0.045 | 7 | 0.45 | **KILLED** | K1 OOS Sharpe -0.05 does not beat own buy-and-hold 0.56 and equal weight 0.42; K2 DSR 0.045 < 0.95; K4 7 OOS round trips < 30; K5 neighbor(s) V116(sma=100) fail out of sample; K6 OOS Sharpe -0.05 < half of in-sample 0.45 |

## Closest calls (fail only K2)

- V105 I04_dual_momentum: validation Sharpe 0.58, DSR 0.387.
- V106 I04_dual_momentum: validation Sharpe 0.57, DSR 0.377.
