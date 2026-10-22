# Phase 4: in-sample results (tuning data only)

_Run 2026-10-22T19:50:30Z. Window 2006-01-03 to 2018-12-31 (12.99 years); signals warm up from 2004-11-18. 1x costs, $100 start, risk layer off. Python 3.14.8, pandas 3.1.0, numpy 2.5.4. No random numbers used._

**These are in-sample numbers: the data any tuning would be done on.** They are not evidence of an edge. Nothing is selected or killed here. Phase 5 adds validation (2019–2023), walk-forward, the full metric set, the Deflated Sharpe Ratio, and the 2x/3x cost runs. Sharpe is the annualized excess return over T-bills.

`n_trades` = number of days with at least one fill (entries, exits, switches and rebalances). The Phase 6 30-trade rule will count completed round trips; that count is added in Phase 5.

## Benchmarks

| ID | Instrument | CAGR | Vol | Sharpe | Max DD |
|---|---|---|---|---|---|
| B01 | GLD | 6.59% | 18.9% | 0.38 | -45.6% |
| B02 | SPY | 7.52% | 19.2% | 0.42 | -55.2% |
| B03 | QQQ | 11.60% | 20.7% | 0.58 | -53.4% |
| B04 | TLT | 5.70% | 14.0% | 0.39 | -26.6% |
| B05 | UGL | 6.24% | 37.8% | 0.32 | -75.9% |
| B06 | UPRO | 7.02% | 57.4% | 0.39 | -95.5% |
| B07 | TQQQ | 17.70% | 61.6% | 0.56 | -94.6% |
| B08 | TMF | 6.52% | 42.2% | 0.34 | -67.2% |
| B09 | GLD|SPY|QQQ|TLT | 8.88% | 10.1% | 0.79 | -26.3% |

## All 92 trials

| ID | Strategy | Signal | Trades in | Params | CAGR | Vol | Sharpe | Max DD | Fill days | In market |
|---|---|---|---|---|---|---|---|---|---|---|
| V001 | S2_trend_ma | GLD | GLD | N=50 | 0.45% | 13.9% | 0.02 | -43.8% | 247 | 54% |
| V002 | S2_trend_ma | GLD | UGL | N=50 | -3.10% | 27.9% | -0.01 | -70.3% | 247 | 54% |
| V003 | S2_trend_ma | SPY | SPY | N=50 | 2.45% | 10.5% | 0.18 | -30.1% | 240 | 68% |
| V004 | S2_trend_ma | SPY | UPRO | N=50 | 2.45% | 31.5% | 0.20 | -69.2% | 240 | 68% |
| V005 | S2_trend_ma | QQQ | QQQ | N=50 | 6.13% | 12.6% | 0.45 | -18.3% | 218 | 68% |
| V006 | S2_trend_ma | QQQ | TQQQ | N=50 | 12.42% | 37.7% | 0.47 | -52.9% | 218 | 68% |
| V007 | S2_trend_ma | TLT | TLT | N=50 | 0.87% | 10.8% | 0.03 | -28.9% | 285 | 58% |
| V008 | S2_trend_ma | TLT | TMF | N=50 | -1.74% | 32.5% | 0.08 | -66.3% | 285 | 58% |
| V009 | S2_trend_ma | GLD | GLD | N=100 | 1.17% | 14.3% | 0.08 | -42.7% | 177 | 59% |
| V010 | S2_trend_ma | GLD | UGL | N=100 | -2.13% | 28.5% | 0.03 | -70.7% | 177 | 59% |
| V011 | S2_trend_ma | SPY | SPY | N=100 | 6.74% | 10.6% | 0.57 | -19.0% | 140 | 74% |
| V012 | S2_trend_ma | SPY | UPRO | N=100 | 15.06% | 31.9% | 0.57 | -48.2% | 140 | 74% |
| V013 | S2_trend_ma | QQQ | QQQ | N=100 | 7.21% | 13.3% | 0.51 | -24.5% | 158 | 74% |
| V014 | S2_trend_ma | QQQ | TQQQ | N=100 | 14.43% | 39.7% | 0.51 | -60.4% | 158 | 74% |
| V015 | S2_trend_ma | TLT | TLT | N=100 | 2.62% | 11.2% | 0.19 | -28.4% | 167 | 60% |
| V016 | S2_trend_ma | TLT | TMF | N=100 | 2.25% | 33.5% | 0.20 | -65.6% | 167 | 60% |
| V017 | S2_trend_ma | GLD | GLD | N=200 | 4.98% | 14.8% | 0.33 | -35.0% | 99 | 62% |
| V018 | S2_trend_ma | GLD | UGL | N=200 | 5.05% | 29.6% | 0.28 | -62.0% | 99 | 62% |
| V019 | S2_trend_ma | SPY | SPY | N=200 | 5.81% | 11.2% | 0.46 | -24.6% | 80 | 79% |
| V020 | S2_trend_ma | SPY | UPRO | N=200 | 10.72% | 33.6% | 0.44 | -58.3% | 80 | 79% |
| V021 | S2_trend_ma | QQQ | QQQ | N=200 | 7.79% | 14.5% | 0.52 | -26.6% | 94 | 80% |
| V022 | S2_trend_ma | QQQ | TQQQ | N=200 | 15.15% | 42.9% | 0.52 | -60.0% | 94 | 80% |
| V023 | S2_trend_ma | TLT | TLT | N=200 | 3.19% | 11.6% | 0.24 | -25.3% | 123 | 61% |
| V024 | S2_trend_ma | TLT | TMF | N=200 | 3.22% | 34.7% | 0.23 | -60.9% | 123 | 61% |
| V025 | S3_tsmom | GLD | GLD | lookback_months=3 | 4.01% | 14.0% | 0.27 | -33.0% | 189 | 58% |
| V026 | S3_tsmom | GLD | UGL | lookback_months=3 | 3.70% | 27.9% | 0.23 | -57.2% | 189 | 58% |
| V027 | S3_tsmom | SPY | SPY | lookback_months=3 | 4.59% | 10.7% | 0.37 | -20.1% | 144 | 72% |
| V028 | S3_tsmom | SPY | UPRO | lookback_months=3 | 8.14% | 32.1% | 0.37 | -53.0% | 144 | 72% |
| V029 | S3_tsmom | QQQ | QQQ | lookback_months=3 | 5.92% | 13.7% | 0.41 | -31.5% | 140 | 73% |
| V030 | S3_tsmom | QQQ | TQQQ | lookback_months=3 | 10.05% | 40.8% | 0.41 | -71.5% | 140 | 73% |
| V031 | S3_tsmom | TLT | TLT | lookback_months=3 | 4.95% | 11.3% | 0.39 | -22.5% | 199 | 62% |
| V032 | S3_tsmom | TLT | TMF | lookback_months=3 | 9.74% | 33.8% | 0.41 | -52.6% | 199 | 62% |
| V033 | S3_tsmom | GLD | GLD | lookback_months=6 | 5.89% | 14.3% | 0.40 | -32.7% | 95 | 62% |
| V034 | S3_tsmom | GLD | UGL | lookback_months=6 | 7.35% | 28.6% | 0.35 | -57.6% | 95 | 62% |
| V035 | S3_tsmom | SPY | SPY | lookback_months=6 | 7.70% | 11.3% | 0.62 | -19.9% | 90 | 77% |
| V036 | S3_tsmom | SPY | UPRO | lookback_months=6 | 17.08% | 33.7% | 0.61 | -50.0% | 90 | 77% |
| V037 | S3_tsmom | QQQ | QQQ | lookback_months=6 | 10.60% | 14.2% | 0.71 | -25.1% | 96 | 79% |
| V038 | S3_tsmom | QQQ | TQQQ | lookback_months=6 | 24.16% | 42.3% | 0.70 | -58.8% | 96 | 79% |
| V039 | S3_tsmom | TLT | TLT | lookback_months=6 | 4.04% | 11.6% | 0.31 | -26.9% | 93 | 62% |
| V040 | S3_tsmom | TLT | TMF | lookback_months=6 | 4.72% | 34.7% | 0.28 | -69.2% | 93 | 62% |
| V041 | S3_tsmom | GLD | GLD | lookback_months=12 | 4.09% | 15.8% | 0.26 | -39.5% | 82 | 64% |
| V042 | S3_tsmom | GLD | UGL | lookback_months=12 | 3.04% | 31.6% | 0.22 | -67.3% | 82 | 64% |
| V043 | S3_tsmom | SPY | SPY | lookback_months=12 | 7.59% | 13.1% | 0.54 | -19.8% | 50 | 83% |
| V044 | S3_tsmom | SPY | UPRO | lookback_months=12 | 14.61% | 39.2% | 0.52 | -53.9% | 50 | 83% |
| V045 | S3_tsmom | QQQ | QQQ | lookback_months=12 | 9.34% | 16.1% | 0.57 | -31.9% | 56 | 87% |
| V046 | S3_tsmom | QQQ | TQQQ | lookback_months=12 | 17.11% | 48.0% | 0.55 | -72.6% | 56 | 87% |
| V047 | S3_tsmom | TLT | TLT | lookback_months=12 | 2.61% | 12.8% | 0.18 | -28.7% | 68 | 72% |
| V048 | S3_tsmom | TLT | TMF | lookback_months=12 | -1.15% | 38.6% | 0.13 | -69.7% | 68 | 72% |
| V049 | S4_rsi2 | SPY | SPY | entry_rsi<5;exit_close>sma5 | 2.37% | 9.3% | 0.18 | -17.2% | 160 | 9% |
| V050 | S4_rsi2 | SPY | UPRO | entry_rsi<5;exit_close>sma5 | 3.57% | 27.8% | 0.22 | -44.8% | 160 | 9% |
| V051 | S4_rsi2 | QQQ | QQQ | entry_rsi<5;exit_close>sma5 | 7.27% | 10.0% | 0.65 | -12.1% | 176 | 10% |
| V052 | S4_rsi2 | QQQ | TQQQ | entry_rsi<5;exit_close>sma5 | 19.15% | 29.6% | 0.70 | -33.0% | 176 | 10% |
| V053 | S4_rsi2 | SPY | SPY | entry_rsi<10;exit_close>sma5 | 4.39% | 11.0% | 0.35 | -23.7% | 280 | 16% |
| V054 | S4_rsi2 | SPY | UPRO | entry_rsi<10;exit_close>sma5 | 9.48% | 32.9% | 0.40 | -57.5% | 280 | 16% |
| V055 | S4_rsi2 | QQQ | QQQ | entry_rsi<10;exit_close>sma5 | 7.75% | 11.6% | 0.61 | -19.5% | 298 | 17% |
| V056 | S4_rsi2 | QQQ | TQQQ | entry_rsi<10;exit_close>sma5 | 20.16% | 34.4% | 0.67 | -49.4% | 298 | 17% |
| V057 | S4_rsi2 | SPY | SPY | entry_rsi<15;exit_close>sma5 | 6.20% | 12.7% | 0.45 | -23.7% | 426 | 23% |
| V058 | S4_rsi2 | SPY | UPRO | entry_rsi<15;exit_close>sma5 | 15.29% | 38.0% | 0.53 | -57.5% | 426 | 23% |
| V059 | S4_rsi2 | QQQ | QQQ | entry_rsi<15;exit_close>sma5 | 7.89% | 12.9% | 0.57 | -19.5% | 412 | 23% |
| V060 | S4_rsi2 | QQQ | TQQQ | entry_rsi<15;exit_close>sma5 | 20.81% | 38.4% | 0.65 | -50.3% | 412 | 23% |
| V061 | S5_rotation | GLD|SPY|QQQ|TLT | winner_1x | lookback_months=3;monthly;cash_if_all_negative | 11.00% | 17.6% | 0.62 | -31.0% | 65 | 97% |
| V062 | S5_rotation | GLD|SPY|QQQ|TLT | winner_1x | lookback_months=6;monthly;cash_if_all_negative | 8.41% | 18.4% | 0.47 | -27.2% | 43 | 99% |
| V063 | S5_rotation | GLD|SPY|QQQ|TLT | winner_1x | lookback_months=12;monthly;cash_if_all_negative | 8.05% | 19.2% | 0.44 | -37.3% | 38 | 100% |
| V064 | S6_leveraged_rotation | GLD|SPY|QQQ|TLT | winner_leveraged | lookback_months=3;monthly;cash_if_all_negative | 23.75% | 46.9% | 0.67 | -68.7% | 65 | 97% |
| V065 | S6_leveraged_rotation | GLD|SPY|QQQ|TLT | winner_leveraged | lookback_months=6;monthly;cash_if_all_negative | 9.52% | 50.0% | 0.41 | -65.2% | 43 | 99% |
| V066 | S6_leveraged_rotation | GLD|SPY|QQQ|TLT | winner_leveraged | lookback_months=12;monthly;cash_if_all_negative | 11.06% | 49.5% | 0.44 | -73.7% | 38 | 100% |
| V067 | P1_vol_gated_leverage | SPY | UPRO|SPY|cash | sma=200;vol_window=20;vol_threshold=15% | 9.60% | 26.7% | 0.44 | -41.5% | 156 | 79% |
| V068 | P1_vol_gated_leverage | QQQ | TQQQ|QQQ|cash | sma=200;vol_window=20;vol_threshold=15% | 11.54% | 29.5% | 0.48 | -51.5% | 203 | 80% |
| V069 | P1_vol_gated_leverage | SPY | UPRO|SPY|cash | sma=200;vol_window=20;vol_threshold=20% | 13.12% | 30.9% | 0.52 | -46.9% | 108 | 79% |
| V070 | P1_vol_gated_leverage | QQQ | TQQQ|QQQ|cash | sma=200;vol_window=20;vol_threshold=20% | 15.72% | 36.4% | 0.56 | -54.1% | 151 | 80% |
| V071 | P1_vol_gated_leverage | SPY | UPRO|SPY|cash | sma=200;vol_window=20;vol_threshold=25% | 14.22% | 32.8% | 0.54 | -57.3% | 87 | 79% |
| V072 | P1_vol_gated_leverage | QQQ | TQQQ|QQQ|cash | sma=200;vol_window=20;vol_threshold=25% | 17.85% | 40.5% | 0.58 | -59.5% | 110 | 80% |
| V073 | P2_multi_asset_trend | GLD|SPY|QQQ|TLT | GLD|SPY|QQQ|TLT | sma_months=6;25%_each;monthly | 7.70% | 7.5% | 0.89 | -13.3% | 134 | 97% |
| V074 | P2_multi_asset_trend | GLD|SPY|QQQ|TLT | UGL|UPRO|TQQQ|TMF | sma_months=6;25%_each;monthly | 17.47% | 20.3% | 0.84 | -35.1% | 154 | 97% |
| V075 | P2_multi_asset_trend | GLD|SPY|QQQ|TLT | GLD|SPY|QQQ|TLT | sma_months=8;25%_each;monthly | 7.16% | 7.7% | 0.80 | -12.3% | 125 | 98% |
| V076 | P2_multi_asset_trend | GLD|SPY|QQQ|TLT | UGL|UPRO|TQQQ|TMF | sma_months=8;25%_each;monthly | 15.07% | 20.8% | 0.73 | -30.3% | 151 | 98% |
| V077 | P2_multi_asset_trend | GLD|SPY|QQQ|TLT | GLD|SPY|QQQ|TLT | sma_months=10;25%_each;monthly | 6.61% | 7.8% | 0.72 | -10.4% | 122 | 98% |
| V078 | P2_multi_asset_trend | GLD|SPY|QQQ|TLT | UGL|UPRO|TQQQ|TMF | sma_months=10;25%_each;monthly | 13.67% | 21.1% | 0.66 | -29.4% | 150 | 98% |
| V079 | P2_multi_asset_trend | GLD|SPY|QQQ|TLT | GLD|SPY|QQQ|TLT | sma_months=12;25%_each;monthly | 6.36% | 7.8% | 0.69 | -11.8% | 121 | 99% |
| V080 | P2_multi_asset_trend | GLD|SPY|QQQ|TLT | UGL|UPRO|TQQQ|TMF | sma_months=12;25%_each;monthly | 12.50% | 21.1% | 0.61 | -33.0% | 149 | 99% |
| V081 | P3_rsi2_trend_filter | SPY | SPY | entry_rsi<5;close>sma200;exit_close>sma5 | 1.88% | 5.3% | 0.18 | -15.8% | 102 | 5% |
| V082 | P3_rsi2_trend_filter | SPY | UPRO | entry_rsi<5;close>sma200;exit_close>sma5 | 3.28% | 15.7% | 0.22 | -42.5% | 102 | 5% |
| V083 | P3_rsi2_trend_filter | QQQ | QQQ | entry_rsi<5;close>sma200;exit_close>sma5 | 2.27% | 6.9% | 0.20 | -12.4% | 120 | 7% |
| V084 | P3_rsi2_trend_filter | QQQ | TQQQ | entry_rsi<5;close>sma200;exit_close>sma5 | 4.24% | 20.3% | 0.25 | -34.7% | 120 | 7% |
| V085 | P3_rsi2_trend_filter | SPY | SPY | entry_rsi<10;close>sma200;exit_close>sma5 | 2.69% | 6.5% | 0.27 | -15.0% | 194 | 11% |
| V086 | P3_rsi2_trend_filter | SPY | UPRO | entry_rsi<10;close>sma200;exit_close>sma5 | 6.02% | 19.5% | 0.34 | -41.1% | 194 | 11% |
| V087 | P3_rsi2_trend_filter | QQQ | QQQ | entry_rsi<10;close>sma200;exit_close>sma5 | 3.43% | 8.0% | 0.33 | -14.1% | 220 | 13% |
| V088 | P3_rsi2_trend_filter | QQQ | TQQQ | entry_rsi<10;close>sma200;exit_close>sma5 | 7.77% | 23.6% | 0.39 | -37.6% | 220 | 13% |
| V089 | P3_rsi2_trend_filter | SPY | SPY | entry_rsi<15;close>sma200;exit_close>sma5 | 3.40% | 7.2% | 0.35 | -14.7% | 308 | 16% |
| V090 | P3_rsi2_trend_filter | SPY | UPRO | entry_rsi<15;close>sma200;exit_close>sma5 | 8.83% | 21.6% | 0.45 | -40.3% | 308 | 16% |
| V091 | P3_rsi2_trend_filter | QQQ | QQQ | entry_rsi<15;close>sma200;exit_close>sma5 | 3.97% | 8.9% | 0.36 | -16.2% | 306 | 17% |
| V092 | P3_rsi2_trend_filter | QQQ | TQQQ | entry_rsi<15;close>sma200;exit_close>sma5 | 9.78% | 26.4% | 0.45 | -42.5% | 306 | 17% |

## By family (median / min / max over each family's variants)

| Family | CAGR median | CAGR range | Sharpe median | Sharpe range | Max DD median | Worst Max DD |
|---|---|---|---|---|---|---|
| P1_vol_gated_leverage | 13.67% | 9.60% to 17.85% | 0.53 | 0.44 to 0.58 | -52.8% | -59.5% |
| P2_multi_asset_trend | 10.10% | 6.36% to 17.47% | 0.73 | 0.61 to 0.89 | -21.4% | -35.1% |
| P3_rsi2_trend_filter | 3.70% | 1.88% to 9.78% | 0.34 | 0.18 to 0.45 | -25.4% | -42.5% |
| S2_trend_ma | 4.10% | -3.10% to 15.15% | 0.26 | -0.01 to 0.57 | -46.0% | -70.7% |
| S3_tsmom | 6.64% | -1.15% to 24.16% | 0.39 | 0.13 to 0.71 | -44.7% | -72.6% |
| S4_rsi2 | 7.82% | 2.37% to 20.81% | 0.55 | 0.18 to 0.70 | -28.3% | -57.5% |
| S5_rotation | 8.41% | 8.05% to 11.00% | 0.47 | 0.44 to 0.62 | -31.0% | -37.3% |
| S6_leveraged_rotation | 11.06% | 9.52% to 23.75% | 0.44 | 0.41 to 0.67 | -68.7% | -73.7% |
