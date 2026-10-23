# Study 3: long-history validation of the near-miss families (1927–2018)

_Run 2026-10-23T00:45:57Z. Pre-registered in commit 79d90a4 (V119–V134). Monthly data, 1x historical costs. Python 3.14.8, pandas 3.1.0, numpy 2.5.4._

## Result first

- **Survivors under the primary pre-registered settings (1x costs): YES (V119, V122).** **But neither holds up:** both fall to 2 of 4 eras or fewer at 2x costs, at 3x costs and with signals lagged one extra month; their grid neighbours (8 and 10 months) pass only 2 eras; and their full-span edge over equal weight is about zero (and negative versus 60/40). I would not treat them as validated. 3 of 16 trials pass the era rule (beat own buy-and-hold and 60/40 on Sharpe in at least 3 of 4 eras): V119, V122, V131; 4 of 16 have a Deflated Sharpe ≥ 0.95 at cumulative N = 134.
- **Best Deflated Sharpe at N = 134: 0.999** (V122, P2 trend 4-asset sma_months=12), hurdle Sharpe 0.39 a year over 1927–2018.
- **Robustness (pre-registered, not trials):** V119 passes 2 of 4 eras at 2x costs, 2 at 3x costs, 1 with signals lagged one extra month; V122 passes 2 of 4 eras at 2x costs, 2 at 3x costs, 2 with signals lagged one extra month; V131 passes 3 of 4 eras at 2x costs, 2 at 3x costs, 1 with signals lagged one extra month.
- **How much better than the benchmarks (information only, full span, 1x costs):** V119 minus L05: -0.0 pp a year, t-stat -0.0; V119 minus L06: -0.7 pp a year, t-stat -0.7; V122 minus L05: +0.1 pp a year, t-stat 0.2; V122 minus L06: -0.6 pp a year, t-stat -0.5; V131 minus L05: +2.3 pp a year, t-stat 1.9; V131 minus L06: +1.6 pp a year, t-stat 1.6.
- **What the Deflated Sharpe does and doesn't say here:** it tests whether a Sharpe ratio above zero could be luck from 134 trials. Over 90 years almost any diversified rule clears that bar (equal weight alone has a full-span Sharpe of 0.49). It does not test whether the rule beats the benchmarks; the era rule does.
- Cumulative trials across the three studies: 92 + 26 + 16 = 134. The holdout stays locked.

## Results by era (Sharpe ratio, excess over T-bills, 1x costs)

✓ = beats both its own buy-and-hold and 60/40 in that era; — = under 10 years of data in the era (counts as not passed).

| ID | Rule | 1927–1949 | 1950–1979 | 1980–1999 | 2000–2018 | Eras passed (1x / 2x / 3x costs / lag 1) | Full-span Sharpe | DSR (N=134) |
|---|---|---|---|---|---|---|---|---|
| V119 | P2 trend 4-asset sma_months=6 | 0.55 ✓ | 0.93 ✓ | 0.30 | 1.07 ✓ | 3 / 2 / 2 / 1 | 0.68 | 0.997 |
| V120 | P2 trend 4-asset sma_months=8 | 0.55 ✓ | 0.90 | 0.39 | 1.08 ✓ | 2 / 2 / 2 / 2 | 0.69 | 0.998 |
| V121 | P2 trend 4-asset sma_months=10 | 0.57 ✓ | 0.91 | 0.39 | 1.01 ✓ | 2 / 2 / 2 / 2 | 0.69 | 0.998 |
| V122 | P2 trend 4-asset sma_months=12 | 0.57 ✓ | 0.96 ✓ | 0.42 | 0.98 ✓ | 3 / 2 / 2 / 2 | 0.71 | 0.999 |
| V123 | S3 TSMOM stocks lookback_months=3 | 0.24 | 0.47 | 0.46 | 0.52 ✓ | 1 / 1 / 1 / 1 | 0.38 | 0.459 |
| V124 | S3 TSMOM bonds lookback_months=3 | 0.66 | -0.07 | 0.64 | 0.54 | 0 / 0 / 0 / 0 | 0.43 | 0.641 |
| V125 | S3 TSMOM gold lookback_months=3 | — | — | -0.14 | 0.46 | 0 / 0 / 0 / 0 | 0.32 | 0.303 |
| V126 | S3 TSMOM commodities lookback_months=3 | 0.28 | 0.62 | -0.13 | 0.45 | 0 / 0 / 0 / 1 | 0.35 | 0.349 |
| V127 | S3 TSMOM stocks lookback_months=6 | 0.21 | 0.68 ✓ | 0.51 | 0.71 ✓ | 2 / 2 / 2 / 3 | 0.48 | 0.792 |
| V128 | S3 TSMOM bonds lookback_months=6 | 0.67 | -0.26 | 0.60 | 0.35 | 0 / 0 / 0 / 0 | 0.32 | 0.265 |
| V129 | S3 TSMOM gold lookback_months=6 | — | — | -0.14 | 0.63 ✓ | 1 / 1 / 1 / 0 | 0.33 | 0.323 |
| V130 | S3 TSMOM commodities lookback_months=6 | 0.46 ✓ | 0.47 | 0.01 | 0.67 ✓ | 2 / 2 / 1 / 0 | 0.42 | 0.614 |
| V131 | S3 TSMOM stocks lookback_months=12 | 0.47 ✓ | 0.55 ✓ | 0.65 | 0.50 ✓ | 3 / 3 / 2 / 1 | 0.53 | 0.902 |
| V132 | S3 TSMOM bonds lookback_months=12 | 0.66 | -0.23 | 0.49 | 0.46 | 0 / 0 / 0 / 0 | 0.32 | 0.259 |
| V133 | S3 TSMOM gold lookback_months=12 | — | — | -0.02 | 0.54 | 0 / 0 / 0 / 1 | 0.41 | 0.573 |
| V134 | S3 TSMOM commodities lookback_months=12 | 0.29 | 0.60 | 0.01 | 0.33 | 0 / 0 / 0 / 0 | 0.36 | 0.374 |

**Benchmarks (same costs on rebalancing):**

| ID | Benchmark | 1927–1949 | 1950–1979 | 1980–1999 | 2000–2018 | Full-span Sharpe | CAGR |
|---|---|---|---|---|---|---|---|
| L01 | B&H stocks | 0.29 | 0.52 | 0.69 | 0.31 | 0.41 | 9.6% |
| L02 | B&H bonds | 0.67 | -0.25 | 0.43 | 0.56 | 0.32 | 5.1% |
| L03 | B&H commodities | 0.23 | 0.66 | -0.08 | 0.21 | 0.30 | 7.0% |
| L04 | B&H gold | — | — | -0.40 | 0.54 | 0.19 | 6.6% |
| L05 | Equal weight (available assets) | 0.37 | 0.91 | 0.17 | 0.63 | 0.49 | 7.7% |
| L06 | 60/40 stocks/bonds | 0.36 | 0.44 | 0.74 | 0.47 | 0.46 | 8.2% |

## Worst 10-year stretch (annualized total return over the worst 120 months, full span)

| ID | Series | Worst 10 years (per year) | Ending | Full-span CAGR | Max drawdown |
|---|---|---|---|---|---|
| V119 | P2 trend 4-asset sma_months=6 | +2.3% | 1939-08 | 7.9% | -20% |
| V120 | P2 trend 4-asset sma_months=8 | +2.3% | 1940-05 | 7.9% | -21% |
| V121 | P2 trend 4-asset sma_months=10 | +1.9% | 1941-02 | 8.0% | -20% |
| V122 | P2 trend 4-asset sma_months=12 | +1.9% | 1941-02 | 8.1% | -22% |
| V123 | S3 TSMOM stocks lookback_months=3 | -4.2% | 1940-05 | 7.7% | -60% |
| V124 | S3 TSMOM bonds lookback_months=3 | +1.0% | 1949-06 | 5.2% | -10% |
| V125 | S3 TSMOM gold lookback_months=3 | -1.5% | 1997-12 | 8.7% | -30% |
| V126 | S3 TSMOM commodities lookback_months=3 | -0.8% | 2018-02 | 7.1% | -34% |
| V127 | S3 TSMOM stocks lookback_months=6 | -3.4% | 1942-05 | 8.9% | -57% |
| V128 | S3 TSMOM bonds lookback_months=6 | +0.6% | 1959-12 | 4.8% | -12% |
| V129 | S3 TSMOM gold lookback_months=6 | -1.0% | 1999-12 | 8.7% | -24% |
| V130 | S3 TSMOM commodities lookback_months=6 | -0.6% | 1961-01 | 8.0% | -34% |
| V131 | S3 TSMOM stocks lookback_months=12 | +1.6% | 1947-02 | 9.8% | -45% |
| V132 | S3 TSMOM bonds lookback_months=12 | +0.9% | 1957-05 | 4.8% | -11% |
| V133 | S3 TSMOM gold lookback_months=12 | +0.7% | 2000-08 | 10.3% | -24% |
| V134 | S3 TSMOM commodities lookback_months=12 | -3.2% | 2018-06 | 7.4% | -37% |
| L01 | B&H stocks | -5.4% | 1939-08 | 9.6% | -84% |
| L02 | B&H bonds | +0.2% | 1959-09 | 5.1% | -15% |
| L03 | B&H commodities | -9.0% | 1939-07 | 7.0% | -79% |
| L04 | B&H gold | -5.6% | 1990-07 | 6.6% | -62% |
| L05 | Equal weight (available assets) | -1.6% | 1939-08 | 7.7% | -61% |
| L06 | 60/40 stocks/bonds | +0.2% | 1939-08 | 8.2% | -63% |

## Context: AQR's diversified trend factor

AQR's TSMOM factor (long/short, volatility-scaled, about 58 futures markets; reference only, not a trial): Sharpe 1.62 in 1985–1999 and 0.83 in 2000–2018. The rules tested here are long-only, unscaled and use 3–4 markets, as in Study 1.

## Method and assumptions

- **Data:** stocks = Ken French US market total return; bonds = total return built from FRED long-term Treasury yields (LTGOVTBD to 1953-04, GS10 after; matches Shiller's bond returns at correlation 1.000 after 1953); commodities = AQR equal-weight futures index plus T-bills; gold = World Bank monthly average from 1971-10; cash = Ken French T-bill. Details: [`data_quality_longhist.md`](data_quality_longhist.md).
- **Rules:** P2 = 1/k in each available asset above its N-month average of month-end total-return values (N = 6/8/10/12); S3 = 100% in the asset when its trailing 3/6/12-month total return is positive. Monthly decisions (Study 1's S3 was checked daily; only monthly data exist here). No leverage.
- **Execution:** weights set at a month-end close earn the next month; rebalanced every month-end; costs on turnover.
- **Costs (one-way):** Hurst, Ooi & Pedersen (2017, Appendix B; AQR 2012 estimates scaled ×6 before 1993 and ×2 for 1993–2002, following Jones 2002): stocks 0.34% / 0.11% / 0.07%, bonds 0.06% / 0.02% / 0.07%, commodities and gold 0.58% / 0.19% / 0.10% (to 1992 / 1993–2002 / 2003+; 2003+ floored at this project's ETF cost). Jones (2002) puts one-way stock costs near 1% in the 1960s–70s for actual share trading, so the ×3 column is the realistic case for a pre-1975 stock investor.
- **Pass rule (pre-registered):** an era passes if the trial's Sharpe beats its own buy-and-hold (S3: the asset; P2: equal weight of available assets) and 60/40; at least 3 of 4 eras needed; eras with under 10 years of the asset's data count as not passed, so S3 on gold (from 1971-10) cannot pass. DSR uses N = 134 and the cross-trial variance of the 16 Study 3 Sharpe ratios.
- **Robustness (not trials):** 2x and 3x costs, and signals lagged one extra month, because gold and bond data are monthly averages (smoothed; lag-1 autocorrelation 0.27 and 0.31).

## Limitations

- Index-level returns: no index funds before 1976, no bond futures before 1977, no stock-index futures before 1982.
- Gold and bond yields are monthly averages; gold was pegged before 1971 and illegal for US residents to hold 1933–1974.
- The 2000–2018 era overlaps Study 1's in-sample period (2006–2018), where the near-misses were first seen.
- One data vendor per asset (no free second source for commodities).
