# Commodity study, Phase 4: in-sample results (tuning data only)

_Run 2026-10-23T00:05:50Z. Window 2007-07-02 to 2018-12-31; signals warm up from 2006-04-28. 1x costs, $100 start, risk layer off. Python 3.14.8, pandas 3.1.0, numpy 2.5.4._

**In-sample numbers are not evidence of an edge.** Nothing is selected or killed here. ⚑ = uses oil: USO structure change Apr-2020 (front-month -> multi-month futures; 1:8 reverse split 2020-04-29) (the change falls in the validation window, not here).

AGQ and UCO are synthetic before their launch (Dec 2008), calibrated on in-sample overlap only; see `data/clean/commodities/build_meta.json`.

| ID | Strategy | Trades in | Params | CAGR | Vol | Sharpe | Max DD | Fill days | In market |
|---|---|---|---|---|---|---|---|---|---|
| CB01 | buy_and_hold | GLD |  | 5.56% | 18.5% | 0.35 | -45.6% | 1 | 100% |
| CB02 | buy_and_hold | SLV |  | 1.30% | 31.5% | 0.18 | -72.4% | 1 | 100% |
| CB03 | buy_and_hold | USO ⚑ |  | -13.81% | 34.6% | -0.27 | -93.2% | 1 | 100% |
| CB04 | buy_and_hold | UGL |  | 4.85% | 37.0% | 0.30 | -75.9% | 1 | 100% |
| CB05 | buy_and_hold | AGQ |  | -12.72% | 63.0% | 0.10 | -97.0% | 1 | 100% |
| CB06 | buy_and_hold | UCO ⚑ |  | -35.31% | 67.4% | -0.32 | -99.8% | 1 | 100% |
| CB07 | buy_and_hold | SPY |  | 6.59% | 20.0% | 0.39 | -55.2% | 1 | 100% |
| CB08 | equal_weight | GLD/SLV/USO ⚑ | monthly | -0.92% | 22.2% | 0.04 | -64.2% | 110 | 100% |
| CB09 | mix_70_30 | SPY/GLD | 70/30;monthly | 7.00% | 15.0% | 0.49 | -38.4% | 89 | 100% |
| V093 | I01_tsmom_basket | GLD/SLV/USO ⚑ | lookback_months=3;thirds;monthly;vs_tbill | -2.86% | 14.2% | -0.17 | -61.1% | 102 | 79% |
| V094 | I01_tsmom_basket | UGL/AGQ/UCO ⚑ | lookback_months=3;thirds;monthly;vs_tbill | -8.72% | 28.2% | -0.20 | -86.3% | 107 | 79% |
| V095 | I01_tsmom_basket | GLD/SLV/USO ⚑ | lookback_months=6;thirds;monthly;vs_tbill | 4.67% | 14.3% | 0.35 | -37.0% | 107 | 78% |
| V096 | I01_tsmom_basket | UGL/AGQ/UCO ⚑ | lookback_months=6;thirds;monthly;vs_tbill | 5.56% | 28.3% | 0.31 | -64.9% | 116 | 78% |
| V097 | I01_tsmom_basket | GLD/SLV/USO ⚑ | lookback_months=12;thirds;monthly;vs_tbill | -0.66% | 14.8% | -0.01 | -46.9% | 96 | 76% |
| V098 | I01_tsmom_basket | UGL/AGQ/UCO ⚑ | lookback_months=12;thirds;monthly;vs_tbill | -5.13% | 29.3% | -0.05 | -76.6% | 107 | 76% |
| V099 | I03_vol_scaled_trend | GLD | target_vol=15%;ewmac16_64;weekly;band10% | 2.10% | 6.8% | 0.25 | -19.9% | 180 | 50% |
| V100 | I03_vol_scaled_trend | GLD | target_vol=20%;ewmac16_64;weekly;band10% | 2.62% | 8.0% | 0.29 | -22.5% | 182 | 52% |
| V101 | I03_vol_scaled_trend | GLD | target_vol=25%;ewmac16_64;weekly;band10% | 2.73% | 8.8% | 0.28 | -24.6% | 183 | 52% |
| V102 | I03_vol_scaled_trend | GLD/SLV/USO ⚑ | target_vol=15%;ewmac16_64;weekly;band10% | 1.09% | 4.7% | 0.13 | -17.0% | 281 | 68% |
| V103 | I03_vol_scaled_trend | GLD/SLV/USO ⚑ | target_vol=20%;ewmac16_64;weekly;band10% | 1.41% | 6.0% | 0.16 | -20.4% | 315 | 71% |
| V104 | I03_vol_scaled_trend | GLD/SLV/USO ⚑ | target_vol=25%;ewmac16_64;weekly;band10% | 1.38% | 7.1% | 0.14 | -25.2% | 323 | 72% |
| V105 | I04_dual_momentum | winner_1x ⚑ | lookback_months=3;monthly;vs_tbill | -3.20% | 24.7% | -0.03 | -81.2% | 52 | 79% |
| V106 | I04_dual_momentum | winner_leveraged ⚑ | lookback_months=3;monthly;vs_tbill | -13.60% | 48.9% | -0.06 | -97.6% | 52 | 79% |
| V107 | I04_dual_momentum | winner_1x ⚑ | lookback_months=6;monthly;vs_tbill | 2.32% | 24.3% | 0.19 | -62.1% | 43 | 78% |
| V108 | I04_dual_momentum | winner_leveraged ⚑ | lookback_months=6;monthly;vs_tbill | -4.29% | 48.3% | 0.14 | -90.0% | 43 | 78% |
| V109 | I04_dual_momentum | winner_1x ⚑ | lookback_months=12;monthly;vs_tbill | -3.14% | 25.2% | -0.02 | -71.3% | 48 | 76% |
| V110 | I04_dual_momentum | winner_leveraged ⚑ | lookback_months=12;monthly;vs_tbill | -14.59% | 50.0% | -0.07 | -95.4% | 48 | 76% |
| V111 | I05_real_yield | GLD | fast=20;slow=120;h15_lag | 4.97% | 13.1% | 0.39 | -25.1% | 30 | 53% |
| V112 | I05_real_yield | UGL | fast=20;slow=120;h15_lag | 6.33% | 26.2% | 0.34 | -53.2% | 30 | 53% |
| V113 | I05_real_yield | GLD | fast=20;slow=250;h15_lag | 1.84% | 14.1% | 0.16 | -44.4% | 20 | 59% |
| V114 | I05_real_yield | UGL | fast=20;slow=250;h15_lag | -0.24% | 28.1% | 0.11 | -74.3% | 20 | 59% |
| V115 | I06_dollar_trend | GLD | sma=100;h10_lag | 6.03% | 11.3% | 0.52 | -25.2% | 50 | 49% |
| V116 | I06_dollar_trend | UGL | sma=100;h10_lag | 9.32% | 22.5% | 0.48 | -47.4% | 50 | 49% |
| V117 | I06_dollar_trend | GLD | sma=200;h10_lag | 5.54% | 11.2% | 0.48 | -28.8% | 42 | 45% |
| V118 | I06_dollar_trend | UGL | sma=200;h10_lag | 8.52% | 22.4% | 0.45 | -51.2% | 42 | 45% |
