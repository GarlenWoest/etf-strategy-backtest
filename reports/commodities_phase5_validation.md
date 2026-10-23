# Commodity study, Phase 5: validation (2019–2023)

_Run 2026-10-23T00:06:01Z. Continuous runs from 2007-07-02; in-sample to 2018-12-31, validation 2019-01-01 to 2023-12-31. Risk layer off, $100 start. Python 3.14.8, pandas 3.1.0, numpy 2.5.4._

⚑ = uses oil. **Oil flag:** USO structure change Apr-2020 (front-month -> multi-month futures; 1:8 reverse split 2020-04-29). Oil results before and after April 2020 come from a differently built fund.

## Result first

- **6 of 26** trials beat both their own buy-and-hold and equal weight (GLD/SLV/USO, Sharpe 0.42) out of sample: V095, V096, V105, V106, V107, V108.
- 70/30 SPY/GLD benchmark: validation Sharpe 0.82, CAGR 14.4%, max drawdown -25.2%.
- Deflated Sharpe at cumulative N = 118 (hurdle: annualized Sharpe the best of 118 unskilled trials would reach, 0.71). Best 5:

| ID | Strategy | Params | Val Sharpe | 95% CI | DSR (N=118) | DSR (N=26, info) |
|---|---|---|---|---|---|---|
| V108 | I04_dual_momentum winner_leveraged ⚑ | lookback_months=6 | 0.63 | -0.23 to 1.51 | 0.430 | 0.714 |
| V107 | I04_dual_momentum winner_1x ⚑ | lookback_months=6 | 0.63 | -0.25 to 1.53 | 0.428 | 0.712 |
| V105 | I04_dual_momentum winner_1x ⚑ | lookback_months=3 | 0.58 | -0.29 to 1.47 | 0.387 | 0.675 |
| V095 | I01_tsmom_basket GLD/SLV/USO ⚑ | lookback_months=6 | 0.57 | -0.31 to 1.46 | 0.377 | 0.666 |
| V106 | I04_dual_momentum winner_leveraged ⚑ | lookback_months=3 | 0.57 | -0.29 to 1.47 | 0.377 | 0.665 |

Effective number of independent new trials (correlation-based, information only): 2.3.

## Benchmarks

| ID | Series | IS Sharpe | Val Sharpe | Val CAGR | Val max DD |
|---|---|---|---|---|---|
| CB01 | buy_and_hold GLD | 0.35 | 0.56 | 9.6% | -22.0% |
| CB02 | buy_and_hold SLV | 0.18 | 0.36 | 8.6% | -39.3% |
| CB03 | buy_and_hold USO ⚑ | -0.27 | 0.13 | -2.7% | -84.6% |
| CB04 | buy_and_hold UGL | 0.30 | 0.44 | 11.4% | -46.2% |
| CB05 | buy_and_hold AGQ | 0.10 | 0.30 | 0.8% | -74.2% |
| CB06 | buy_and_hold UCO ⚑ | -0.32 | 0.18 | -20.2% | -98.2% |
| CB07 | buy_and_hold SPY | 0.39 | 0.72 | 15.8% | -33.7% |
| CB08 | equal_weight GLD/SLV/USO ⚑ | 0.04 | 0.42 | 9.0% | -40.7% |
| CB09 | mix_70_30 SPY/GLD | 0.49 | 0.82 | 14.4% | -25.2% |

## All 26 trials

| ID | Strategy | Trades in | Params | IS Sharpe | Val Sharpe | Own B&H | Val CAGR | Val max DD | Round trips | Val Sharpe 2x / 3x costs | Time in market | DSR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V093 | I01_tsmom_basket | GLD/SLV/USO ⚑ | lookback_months=3 | -0.17 | 0.33 | 0.42 | 5.8% | -20.0% | 27 | 0.32 / 0.30 | 88% | 0.202 |
| V094 | I01_tsmom_basket | UGL/AGQ/UCO ⚑ | lookback_months=3 | -0.20 | 0.27 | 0.42 | 5.6% | -42.0% | 27 | 0.26 / 0.25 | 88% | 0.164 |
| V095 | I01_tsmom_basket | GLD/SLV/USO ⚑ | lookback_months=6 | 0.35 | 0.57 | 0.42 | 9.4% | -22.2% | 20 | 0.55 / 0.54 | 95% | 0.377 |
| V096 | I01_tsmom_basket | UGL/AGQ/UCO ⚑ | lookback_months=6 | 0.31 | 0.48 | 0.42 | 12.2% | -44.6% | 20 | 0.47 / 0.46 | 95% | 0.309 |
| V097 | I01_tsmom_basket | GLD/SLV/USO ⚑ | lookback_months=12 | -0.01 | 0.32 | 0.42 | 5.7% | -25.0% | 13 | 0.31 / 0.31 | 87% | 0.195 |
| V098 | I01_tsmom_basket | UGL/AGQ/UCO ⚑ | lookback_months=12 | -0.05 | 0.26 | 0.42 | 5.4% | -48.5% | 13 | 0.26 / 0.25 | 87% | 0.162 |
| V099 | I03_vol_scaled_trend | GLD | target_vol=15% | 0.25 | 0.17 | 0.56 | 2.9% | -13.0% | 9 | 0.14 / 0.11 | 55% | 0.118 |
| V100 | I03_vol_scaled_trend | GLD | target_vol=20% | 0.29 | 0.15 | 0.56 | 2.8% | -14.7% | 10 | 0.12 / 0.09 | 57% | 0.107 |
| V101 | I03_vol_scaled_trend | GLD | target_vol=25% | 0.28 | 0.13 | 0.56 | 2.7% | -15.4% | 11 | 0.10 / 0.08 | 58% | 0.101 |
| V102 | I03_vol_scaled_trend | GLD/SLV/USO ⚑ | target_vol=15% | 0.13 | 0.31 | 0.42 | 3.5% | -5.5% | 27 | 0.29 / 0.26 | 82% | 0.192 |
| V103 | I03_vol_scaled_trend | GLD/SLV/USO ⚑ | target_vol=20% | 0.16 | 0.27 | 0.42 | 3.6% | -8.5% | 29 | 0.24 / 0.22 | 85% | 0.166 |
| V104 | I03_vol_scaled_trend | GLD/SLV/USO ⚑ | target_vol=25% | 0.14 | 0.31 | 0.42 | 4.1% | -9.0% | 30 | 0.29 / 0.26 | 85% | 0.191 |
| V105 | I04_dual_momentum | winner_1x ⚑ | lookback_months=3 | -0.03 | 0.58 | 0.42 | 15.9% | -30.5% | 16 | 0.57 / 0.55 | 88% | 0.387 |
| V106 | I04_dual_momentum | winner_leveraged ⚑ | lookback_months=3 | -0.06 | 0.57 | 0.42 | 19.2% | -55.8% | 16 | 0.56 / 0.55 | 88% | 0.377 |
| V107 | I04_dual_momentum | winner_1x ⚑ | lookback_months=6 | 0.19 | 0.63 | 0.42 | 18.1% | -41.4% | 14 | 0.62 / 0.60 | 95% | 0.428 |
| V108 | I04_dual_momentum | winner_leveraged ⚑ | lookback_months=6 | 0.14 | 0.63 | 0.42 | 23.7% | -66.9% | 14 | 0.62 / 0.61 | 95% | 0.430 |
| V109 | I04_dual_momentum | winner_1x ⚑ | lookback_months=12 | -0.02 | 0.32 | 0.42 | 7.3% | -46.8% | 11 | 0.31 / 0.30 | 87% | 0.196 |
| V110 | I04_dual_momentum | winner_leveraged ⚑ | lookback_months=12 | -0.07 | 0.30 | 0.42 | 1.2% | -75.0% | 11 | 0.29 / 0.28 | 87% | 0.180 |
| V111 | I05_real_yield | GLD | slow=120 | 0.39 | 0.26 | 0.56 | 4.3% | -27.3% | 10 | 0.24 / 0.21 | 55% | 0.159 |
| V112 | I05_real_yield | UGL | slow=120 | 0.34 | 0.16 | 0.56 | 3.0% | -50.2% | 10 | 0.15 / 0.13 | 55% | 0.112 |
| V113 | I05_real_yield | GLD | slow=250 | 0.16 | 0.49 | 0.56 | 7.0% | -19.9% | 2 | 0.49 / 0.48 | 51% | 0.314 |
| V114 | I05_real_yield | UGL | slow=250 | 0.11 | 0.39 | 0.56 | 8.6% | -39.5% | 2 | 0.38 / 0.38 | 51% | 0.237 |
| V115 | I06_dollar_trend | GLD | sma=100 | 0.52 | 0.18 | 0.56 | 3.2% | -18.8% | 14 | 0.14 / 0.11 | 48% | 0.121 |
| V116 | I06_dollar_trend | UGL | sma=100 | 0.48 | 0.09 | 0.56 | 1.6% | -37.3% | 14 | 0.06 / 0.04 | 48% | 0.084 |
| V117 | I06_dollar_trend | GLD | sma=200 | 0.48 | 0.01 | 0.56 | 1.6% | -18.8% | 7 | -0.01 / -0.03 | 39% | 0.060 |
| V118 | I06_dollar_trend | UGL | sma=200 | 0.45 | -0.05 | 0.56 | -0.8% | -37.3% | 7 | -0.06 / -0.07 | 39% | 0.045 |

## Walk-forward (train 5 years, test the next year, 2012–2023)

| Group | WF Sharpe | Own B&H | Equal weight | 70/30 | WF CAGR | WF max DD | Parameter chosen each year |
|---|---|---|---|---|---|---|---|
| I01_tsmom_basket GLD/SLV/USO->GLD/SLV/USO ⚑ | 0.04 | -0.05 | -0.05 | 0.78 | 0.9% | -39.4% | 2012:V095 2013:V095 2014:V095 2015:V095 2016:V097 2017:V095 2018:V095 2019:V095 2020:V095 2021:V095 2022:V095 2023:V095 |
| I01_tsmom_basket GLD/SLV/USO->UGL/AGQ/UCO ⚑ | -0.02 | -0.05 | -0.05 | 0.78 | -1.7% | -64.7% | 2012:V096 2013:V096 2014:V096 2015:V096 2016:V098 2017:V096 2018:V096 2019:V096 2020:V096 2021:V096 2022:V096 2023:V096 |
| I03_vol_scaled_trend GLD->GLD | -0.12 | 0.13 | -0.05 | 0.78 | 0.1% | -17.6% | 2012:V100 2013:V101 2014:V100 2015:V101 2016:V099 2017:V101 2018:V101 2019:V101 2020:V100 2021:V099 2022:V099 2023:V099 |
| I03_vol_scaled_trend GLD/SLV/USO->GLD/SLV/USO ⚑ | -0.11 | -0.05 | -0.05 | 0.78 | 0.3% | -17.4% | 2012:V103 2013:V103 2014:V103 2015:V103 2016:V103 2017:V104 2018:V104 2019:V104 2020:V103 2021:V103 2022:V103 2023:V102 |
| I04_dual_momentum GLD/SLV/USO->winner_1x ⚑ | 0.07 | -0.05 | -0.05 | 0.78 | -0.2% | -69.4% | 2012:V105 2013:V107 2014:V109 2015:V107 2016:V109 2017:V109 2018:V107 2019:V107 2020:V107 2021:V107 2022:V107 2023:V107 |
| I04_dual_momentum GLD/SLV/USO->winner_leveraged ⚑ | -0.04 | -0.05 | -0.05 | 0.78 | -10.9% | -93.5% | 2012:V106 2013:V106 2014:V110 2015:V108 2016:V110 2017:V110 2018:V108 2019:V108 2020:V108 2021:V106 2022:V108 2023:V108 |
| I05_real_yield DFII10->GLD | 0.08 | 0.13 | -0.05 | 0.78 | 1.4% | -27.3% | 2012:V111 2013:V111 2014:V111 2015:V111 2016:V111 2017:V111 2018:V111 2019:V111 2020:V111 2021:V111 2022:V113 2023:V113 |
| I05_real_yield DFII10->UGL | 0.02 | 0.13 | -0.05 | 0.78 | -0.7% | -50.2% | 2012:V112 2013:V112 2014:V112 2015:V112 2016:V112 2017:V112 2018:V112 2019:V112 2020:V112 2021:V112 2022:V114 2023:V114 |
| I06_dollar_trend DTWEXBGS->GLD | -0.19 | 0.13 | -0.05 | 0.78 | -1.0% | -26.2% | 2012:V115 2013:V115 2014:V115 2015:V115 2016:V115 2017:V115 2018:V115 2019:V117 2020:V117 2021:V117 2022:V117 2023:V115 |
| I06_dollar_trend DTWEXBGS->UGL | -0.24 | 0.13 | -0.05 | 0.78 | -4.5% | -55.8% | 2012:V116 2013:V116 2014:V116 2015:V116 2016:V116 2017:V116 2018:V116 2019:V118 2020:V118 2021:V118 2022:V118 2023:V116 |

## Stress periods ($100 at the start of each period; lowest value reached)

| ID | 2008 | covid_2020 | 2022 | calm_2017 | calm_2013 | calm_2014 |
|---|---|---|---|---|---|---|
| CB01 | +4% (low $84) | -3% (low $91) | -0% (low $89) | +12% (low $100) | -28% (low $72) | -2% (low $95) |
| CB02 | -24% (low $60) | -28% (low $66) | +3% (low $77) | +4% (low $96) | -36% (low $61) | -20% (low $78) |
| CB03 | -56% (low $38) | -55% (low $43) | +27% (low $100) | +2% (low $74) | +7% (low $94) | -43% (low $57) |
| CB04 | -6% (low $63) | -6% (low $83) | -6% (low $76) | +21% (low $100) | -51% (low $48) | -6% (low $89) |
| CB05 | -60% (low $26) | -50% (low $41) | -6% (low $53) | +2% (low $88) | -64% (low $35) | -41% (low $57) |
| CB06 | -85% (low $11) | -85% (low $15) | +36% (low $99) | +0% (low $54) | +12% (low $87) | -68% (low $32) |
| CB07 | -37% (low $52) | -33% (low $67) | -18% (low $76) | +21% (low $100) | +35% (low $100) | +14% (low $95) |
| CB08 | -26% (low $66) | -29% (low $67) | +11% (low $94) | +7% (low $92) | -20% (low $78) | -22% (low $78) |
| CB09 | -25% (low $63) | -25% (low $75) | -13% (low $80) | +19% (low $100) | +13% (low $100) | +9% (low $98) |
| V093 | -7% (low $93) | -4% (low $94) | +13% (low $100) | -5% (low $90) | -12% (low $88) | -15% (low $84) |
| V094 | -18% (low $82) | -8% (low $88) | +19% (low $100) | -10% (low $81) | -23% (low $77) | -29% (low $71) |
| V095 | +1% (low $99) | -4% (low $94) | +8% (low $100) | -1% (low $93) | -4% (low $92) | -5% (low $95) |
| V096 | -5% (low $92) | -8% (low $89) | +9% (low $99) | -3% (low $87) | -8% (low $84) | -11% (low $89) |
| V097 | -15% (low $81) | -11% (low $86) | +8% (low $99) | -2% (low $94) | +3% (low $99) | -6% (low $94) |
| V098 | -34% (low $60) | -20% (low $74) | +10% (low $99) | -6% (low $87) | +5% (low $98) | -11% (low $89) |
| V099 | +2% (low $100) | -4% (low $95) | +3% (low $100) | -4% (low $95) | -1% (low $99) | -3% (low $97) |
| V100 | +2% (low $100) | -7% (low $91) | +3% (low $99) | -4% (low $95) | -1% (low $99) | -4% (low $96) |
| V101 | +3% (low $100) | -7% (low $91) | +3% (low $99) | -4% (low $95) | -1% (low $99) | -4% (low $95) |
| V102 | +3% (low $100) | -2% (low $98) | +5% (low $100) | -2% (low $96) | -2% (low $98) | -3% (low $97) |
| V103 | +4% (low $100) | -3% (low $96) | +4% (low $100) | -2% (low $96) | -2% (low $98) | -4% (low $96) |
| V104 | +7% (low $100) | -3% (low $96) | +6% (low $100) | -3% (low $95) | -3% (low $97) | -4% (low $96) |
| V105 | -13% (low $87) | -3% (low $91) | +30% (low $99) | -5% (low $79) | -14% (low $86) | -15% (low $84) |
| V106 | -34% (low $65) | -6% (low $83) | +47% (low $97) | -11% (low $61) | -27% (low $73) | -29% (low $70) |
| V107 | -18% (low $77) | -11% (low $84) | +41% (low $100) | +1% (low $87) | -3% (low $86) | -4% (low $92) |
| V108 | -43% (low $52) | -21% (low $70) | +69% (low $99) | -1% (low $75) | -8% (low $72) | -8% (low $85) |
| V109 | -21% (low $67) | -3% (low $91) | +27% (low $100) | -12% (low $80) | +9% (low $100) | -12% (low $88) |
| V110 | -49% (low $37) | -6% (low $83) | +36% (low $99) | -24% (low $64) | +17% (low $100) | -22% (low $78) |
| V111 | +3% (low $100) | -3% (low $91) | +2% (low $100) | -5% (low $95) | -2% (low $98) | -1% (low $99) |
| V112 | +2% (low $99) | -6% (low $83) | +2% (low $100) | -10% (low $89) | -6% (low $94) | -3% (low $97) |
| V113 | -6% (low $94) | -3% (low $91) | +2% (low $98) | -1% (low $96) | -14% (low $82) | -10% (low $84) |
| V114 | -17% (low $83) | -6% (low $83) | +2% (low $97) | -4% (low $91) | -28% (low $66) | -19% (low $70) |
| V115 | +4% (low $100) | +0% (low $100) | +7% (low $97) | -3% (low $94) | -7% (low $92) | -0% (low $95) |
| V116 | +3% (low $99) | +0% (low $100) | +12% (low $94) | -9% (low $87) | -14% (low $83) | -1% (low $91) |
| V117 | -3% (low $97) | +0% (low $100) | +2% (low $100) | +5% (low $98) | -12% (low $88) | -8% (low $92) |
| V118 | -11% (low $89) | +0% (low $100) | +2% (low $100) | +7% (low $95) | -23% (low $77) | -15% (low $85) |

Calm years are the 3 lowest SPY-volatility years: 2017, 2013, 2014.

## Suspect-price sensitivity

UGL's unresolved 2018-05-18..22 closes were interpolated and every trial was rerun. Largest change in validation Sharpe: 1.9e-14; in in-sample Sharpe: 2.5e-06 (V096 and V098 held UGL that week).

## Synthetic leveraged history (AGQ, UCO before December 2008)

| Fund | Real from | Extra drag (calibrated to 2018) | Daily corr. (overlap) | Tracking error | Synthetic minus real, 2019–2023 (per year) |
|---|---|---|---|---|---|
| AGQ | 2008-12-04 | 4.31% | 0.997 | 4.8% | +2.0 pp |
| UCO | 2008-11-25 | 0.94% | 0.988 | 11.8% | +6.7 pp |

The validation window uses real AGQ/UCO prices only; the synthetic part affects in-sample and walk-forward training years before 2009.

## Method notes

- Sharpe = annualized excess return over T-bills. DSR uses the cross-trial variance of daily validation Sharpe ratios over all 118 trials (92 ETF + 26 commodity) and N = 118.
- FRED signals use only values released by each date: DFII10 from the 2nd trading day after its date (H.15, 4:15 pm), DTWEXBGS from the Wednesday after its week (H.10, weekly). Current FRED vintage; revisions not modelled.
- Bootstrap: 10,000 i.i.d. resamples of daily excess returns, seed 20261022 + 92 + trial index.
