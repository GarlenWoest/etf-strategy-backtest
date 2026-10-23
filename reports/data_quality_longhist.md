# Study 3: long-history data quality

_Produced by `tools/validate_longhist.py`. Downloaded 2026-10-23T00:36:25Z (FRED 2026-10-23T00:38:53Z). Every file was truncated before 2024-01-01 right after parsing and the originals deleted; rows dropped unread: stocks_kf_total_return 32, tbill_kf_rf 32, commodities_aqr_excess_return 17, aqr_tsmom_factor_reference 29, aqr_tsmom_cm_factor_reference 29, gold_worldbank_usd_oz_monthly_avg 12. Nothing was filled or edited._

## Sources and spans

| Series | Source | First | Last | Rows |
|---|---|---|---|---|
| stocks_kf_total_return | Ken French data library | 1926-07-31 | 2023-12-31 | 1170 |
| tbill_kf_rf | Ken French data library | 1926-07-31 | 2023-12-31 | 1170 |
| commodities_aqr_excess_return | AQR datasets | 1877-02-28 | 2023-12-31 | 1763 |
| aqr_tsmom_factor_reference | AQR datasets (reference only) | 1985-01-31 | 2023-12-31 | 468 |
| aqr_tsmom_cm_factor_reference | AQR datasets (reference only) | 1985-01-31 | 2023-12-31 | 468 |
| gold_worldbank_usd_oz_monthly_avg | World Bank Pink Sheet | 1960-01-31 | 2023-12-31 | 768 |
| shiller_bond_gross_return | Shiller (Yale), cross-check only | 1871-01-31 | 2023-08-31 | 1832 |
| shiller_cpi | Shiller (Yale), cross-check only | 1871-01-31 | 2023-09-30 | 1833 |
| shiller_sp_price | Shiller (Yale), cross-check only | 1871-01-31 | 2023-09-30 | 1833 |
| shiller_sp_dividend | Shiller (Yale), cross-check only | 1871-01-31 | 2023-06-30 | 1830 |
| fred_LTGOVTBD | FRED | 1925-01-31 | 2000-06-30 | 906 |
| fred_GS10 | FRED | 1953-04-30 | 2023-12-31 | 849 |
| fred_TB3MS | FRED | 1934-01-31 | 2023-12-31 | 1080 |
| fred_CPIAUCNS | FRED | 1913-01-31 | 2023-12-31 | 1332 |

## Checks

| Series | duplicate months | missing months | NaN | returns <= -100% | big moves (>25%/month) | months inside 3+ month unchanged runs |
|---|---|---|---|---|---|---|
| stocks_kf_total_return | 0 | 0 | 0 | 0 | 4: 1931-09 -29%, 1932-07 +34%, 1932-08 +37%, 1933-04 +39% | 0 |
| tbill_kf_rf | 0 | 0 | 0 | 110 | 110 | 160 |
| commodities_aqr_excess_return | 0 | 0 | 0 | 0 | 0 | 0 |
| aqr_tsmom_factor_reference | 0 | 0 | 0 | 0 | 0 | 0 |
| aqr_tsmom_cm_factor_reference | 0 | 0 | 0 | 0 | 0 | 0 |
| gold_worldbank_usd_oz_monthly_avg | 0 | 0 | 0 | 0 | 1: 1980-01 +48% | 80 |
| shiller_bond_gross_return | 0 | 0 | 0 | 0 | 0 | 0 |
| shiller_cpi | 0 | 0 | 0 | 0 | 0 | 191 |
| shiller_sp_price | 0 | 0 | 0 | 0 | 3: 1929-11 -26%, 1932-08 +50%, 1933-05 +29% | 3 |
| shiller_sp_dividend | 0 | 0 | 0 | 0 | 0 | 154 |
| fred_LTGOVTBD | 0 | 0 | 0 | 0 | 0 | 8 |
| fred_GS10 | 0 | 0 | 0 | 0 | 4: 2008-12 -31%, 2020-03 -42%, 2021-03 +28%, 2022-04 +29% | 0 |
| fred_TB3MS | 0 | 0 | 0 | 0 | 0 | 87 |
| fred_CPIAUCNS | 0 | 0 | 0 | 0 | 0 | 129 |

(The 4th column is non-positive levels for level series and returns ≤ −100% for return series.)

## Cross-checks against a second source (through 2018)

| Check | Correlation | Mean difference (per year) | Months |
|---|---|---|---|
| Bonds 1953-05..2018: my GS10 total return vs Shiller monthly bond return (Shiller shifted 1 month: he dates a return by its start month) | 1.000 | +0.00 pp | 788 |
| Bonds 1926-07..1953-04: my LTGOVTBD total return vs Shiller (interpolated yields; expect lower) | 0.284 | +0.23 pp | 322 |
| Bonds 1953-05..2000-06: LTGOVTBD (20y) vs GS10 (10y) construction, overlap | 0.962 | -0.38 pp | 566 |
| T-bill: Ken French 1-month RF vs FRED TB3MS/12 | 0.990 | -0.11 pp | 1020 |
| Stocks: Ken French market vs Shiller S&P (monthly-average prices) | 0.678 | +0.34 pp | 1109 |
| CPI: FRED CPIAUCNS vs Shiller CPI, monthly change | 1.000 | +0.00 pp | 1271 |
| Gold: World Bank monthly average vs GLD monthly average of closes | 0.997 | +0.40 pp | 168 |
| Gold: World Bank monthly average vs GLD month-end (shows averaging smoothing) | 0.582 | -0.44 pp | 168 |

## Lag-1 autocorrelation of monthly returns (smoothing check)

| Series | Autocorrelation |
|---|---|
| gold WB avg | 0.27 |
| GLD month-end | -0.10 |
| GLD monthly avg | 0.13 |
| stocks KF | 0.10 |
| bonds (built) | 0.31 |
| commodities AQR | 0.13 |

## Problems and decisions

1. **Gold is a monthly average** (World Bank). Averaging smooths returns and adds positive autocorrelation, which flatters trend rules. Pre-registered robustness check: every trial is also run with signals lagged one extra month.
2. **Bond yields are monthly averages** (FRED LTGOVTBD, GS10), so the built bond returns are slightly smoothed too. LTGOVTBD (average maturity above 10 years, modelled as 20) is used until 1953-04, GS10 (10 years) after.
3. **Shiller's long rate before 1953 is linearly interpolated between annual values** (it uses next year's yield), so it is used only as a cross-check, never as a signal or return.
4. **Gold before 1971 was pegged** ($35/oz); gold enters the universe from 1971-10. US residents could not legally hold gold bullion from 1933 to 1974.
5. **Indexes are not what an investor could buy** for most of the sample: no index funds before 1976, no futures on bonds before 1977 or stocks before 1982. Returns are index-level; costs (below) are the only friction.
6. **Ken French market** is CRSP value-weighted, month-end, with dividends: the cleanest series here. Shiller's S&P uses monthly-average prices, hence the imperfect correlation in the cross-check.
7. **Commodities:** AQR's equal-weight futures index (excess return over T-bills; T-bill added back). No second free source exists; not cross-checked.
8. **The study stops at 2018-12-31.** Rows from 2019–2023 exist on disk but are not used; 2024+ rows were never kept.
