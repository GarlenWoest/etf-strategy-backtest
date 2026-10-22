# INFORMATIONAL: not validated, failed DSR

# Phase 7A Monte Carlo: two killed strategies and three benchmarks

> **NOT VALIDATED: FAILED DSR.** All 92 trials were killed in Phase 6. V073 and V074 failed only the Deflated Sharpe test (0.727 and 0.669, both below 0.95). Their 2019–2023 results may be luck from testing 92 variants. This page exists because you asked for it. It is not a recommendation and not a basis for real money.

## In plain English (no monthly additions)

Chance that $100 grows to $1,000 **before** it falls to $20 (within the 30-year simulation), and the median number of years to reach $1,000. Each column is how much of the account is in the strategy (the rest earns T-bills).

| | 20% in: chance | 20% in: median years | 50% in: chance | 50% in: median years | 100% in: chance | 100% in: median years |
|---|---|---|---|---|---|---|
| **V073 P2 6-month 1x** | 0% | >30 | 1% | >30 | 94% | 23.1 |
| **V074 P2 6-month leveraged** | 2% | >30 | 98% | 19.1 | 100% | 10.8 |
| **Equal weight (benchmark)** | 0% | >30 | 28% | >30 | 95% | 19.6 |
| **SPY buy-and-hold (benchmark)** | 0% | >30 | 78% | 25.5 | 98% | 14.7 |
| **UPRO buy-and-hold (benchmark)** | 85% | 23.2 | 98% | 11.4 | 82% | 7.0 |

">30" means fewer than half of the paths reached $1,000 within the 30-year simulation.

**All-in (100%), no monthly additions:**

- **V073 P2 6-month 1x:** out of 100 people running this, about 0 reach $1,000 within 3 years and about 0 within 10 years; about 0 fall to $20 first.
- **V074 P2 6-month leveraged:** out of 100 people running this, about 0 reach $1,000 within 3 years and about 40 within 10 years; about 0 fall to $20 first.
- **Equal weight (benchmark):** out of 100 people running this, about 0 reach $1,000 within 3 years and about 0 within 10 years; about 0 fall to $20 first.
- **SPY buy-and-hold (benchmark):** out of 100 people running this, about 0 reach $1,000 within 3 years and about 11 within 10 years; about 0 fall to $20 first.
- **UPRO buy-and-hold (benchmark):** out of 100 people running this, about 9 reach $1,000 within 3 years and about 68 within 10 years; about 18 fall to $20 first.

**How to read this:** these odds come from replaying 2019–2023 over and over in random 20-day chunks. That was a good period for stocks (SPY +15.8% a year, UPRO +27% a year). The simulation assumes the next decades look like those five years. They may not. The UPRO line shows how leverage turns a good period into large but fragile odds. The equal-weight line is the realistic no-skill baseline.

## Detail

Sample used: daily returns 2019-01-02 to 2023-12-29 at 1x costs, with the T-bill rate of the same days.

| Series | Sample CAGR | Sample volatility | Exposure after $1,000 (Phase 7B cap) |
|---|---|---|---|
| V073 P2 6-month 1x | 10.3% | 8.3% | 100% |
| V074 P2 6-month leveraged | 22.5% | 23.1% | 100% |
| Equal weight (benchmark) | 12.1% | 12.8% | 100% |
| SPY buy-and-hold (benchmark) | 15.8% | 21.0% | 50% |
| UPRO buy-and-hold (benchmark) | 27.0% | 63.5% | 30% |

### $0 added per month

| Series | Size | P($1,000 before $20) | P($20 first) | Neither in 30y | Years to $1,000 (10th / median / 90th) | Value after 1y (10th / median / 90th) | After 2y | After 3y | P(kill switch after $1,000) |
|---|---|---|---|---|---|---|---|---|---|
| V073 P2 6-month 1x | 20% | 0% | 0% | 100% | >30 / >30 / >30 | $101 / $104 / $106 | $104 / $107 / $110 | $107 / $111 / $115 | 0% |
| V073 P2 6-month 1x | 50% | 1% | 0% | 99% | >30 / >30 / >30 | $101 / $106 / $111 | $105 / $113 / $121 | $110 / $120 / $130 | 0% |
| V073 P2 6-month 1x | 100% | 94% | 0% | 6% | 18.8 / 23.1 / 28.6 | $100 / $111 / $122 | $105 / $122 / $140 | $113 / $134 / $159 | 4% |
| V074 P2 6-month leveraged | 20% | 2% | 0% | 98% | >30 / >30 / >30 | $100 / $106 / $112 | $104 / $113 / $122 | $108 / $120 / $132 | 1% |
| V074 P2 6-month leveraged | 50% | 98% | 0% | 2% | 14.7 / 19.1 / 25.3 | $97 / $113 / $129 | $103 / $127 / $154 | $111 / $143 / $181 | 95% |
| V074 P2 6-month leveraged | 100% | 100% | 0% | <1% | 7.3 / 10.8 / 16.4 | $91 / $124 / $161 | $99 / $151 / $222 | $112 / $186 / $299 | 100% |
| Equal weight (benchmark) | 20% | 0% | 0% | 100% | >30 / >30 / >30 | $100 / $104 / $108 | $103 / $108 / $114 | $106 / $112 / $119 | 0% |
| Equal weight (benchmark) | 50% | 28% | 0% | 72% | 26.8 / >30 / >30 | $98 / $107 / $116 | $102 / $115 / $129 | $106 / $123 / $142 | 6% |
| Equal weight (benchmark) | 100% | 95% | 0% | 5% | 14.1 / 19.6 / 27.4 | $94 / $112 / $132 | $98 / $126 / $160 | $104 / $141 / $188 | 63% |
| SPY buy-and-hold (benchmark) | 20% | 0% | 0% | 100% | >30 / >30 / >30 | $100 / $105 / $110 | $102 / $110 / $118 | $106 / $116 / $126 | 0% |
| SPY buy-and-hold (benchmark) | 50% | 78% | 0% | 22% | 19.7 / 25.5 / >30 | $96 / $110 / $123 | $100 / $120 / $141 | $104 / $131 / $161 | 19% |
| SPY buy-and-hold (benchmark) | 100% | 98% | <1% | 2% | 9.9 / 14.7 / 22.7 | $90 / $117 / $146 | $93 / $135 / $189 | $99 / $158 / $237 | 50% |
| UPRO buy-and-hold (benchmark) | 20% | 85% | 0% | 15% | 17.2 / 23.2 / >30 | $94 / $111 / $126 | $97 / $122 / $148 | $102 / $134 / $171 | 68% |
| UPRO buy-and-hold (benchmark) | 50% | 98% | 1% | 1% | 6.8 / 11.4 / 20.4 | $79 / $122 / $169 | $81 / $147 / $240 | $87 / $176 / $323 | 96% |
| UPRO buy-and-hold (benchmark) | 100% | 82% | 18% | <1% | 3.1 / 7.0 / 19.6 | $53 / $134 / $260 | $47 / $171 / $474 | $47 / $220 / $826 | 95% |

### $50 added per month

| Series | Size | P($1,000 before $20) | P($20 first) | Neither in 30y | Years to $1,000 (10th / median / 90th) | Value after 1y (10th / median / 90th) | After 2y | After 3y | P(kill switch after $1,000) |
|---|---|---|---|---|---|---|---|---|---|
| V073 P2 6-month 1x | 20% | 100% | 0% | 0% | 1.5 / 1.5 / 1.5 | $705 / $714 / $722 | $1302 / $1389 / $1474 | $1962 / $2157 / $2374 | 8% |
| V073 P2 6-month 1x | 50% | 100% | 0% | 0% | 1.4 / 1.5 / 1.5 | $702 / $723 / $744 | $1313 / $1410 / $1511 | $1980 / $2182 / $2408 | 8% |
| V073 P2 6-month 1x | 100% | 100% | 0% | 0% | 1.3 / 1.4 / 1.5 | $696 / $739 / $782 | $1325 / $1445 / $1571 | $2002 / $2222 / $2467 | 8% |
| V074 P2 6-month leveraged | 20% | 100% | 0% | 0% | 1.4 / 1.4 / 1.5 | $699 / $724 / $747 | $1187 / $1480 / $1773 | $1759 / $2373 / $3250 | 100% |
| V074 P2 6-month leveraged | 50% | 100% | 0% | 0% | 1.2 / 1.4 / 1.5 | $685 / $748 / $811 | $1223 / $1533 / $1891 | $1800 / $2429 / $3387 | 100% |
| V074 P2 6-month leveraged | 100% | 100% | 0% | 0% | 1.1 / 1.3 / 1.5 | $659 / $788 / $929 | $1249 / $1611 / $2073 | $1850 / $2509 / $3593 | 100% |
| Equal weight (benchmark) | 20% | 100% | 0% | 0% | 1.4 / 1.5 / 1.5 | $700 / $715 / $729 | $1258 / $1404 / $1560 | $1863 / $2202 / $2597 | 91% |
| Equal weight (benchmark) | 50% | 100% | 0% | 0% | 1.3 / 1.4 / 1.5 | $690 / $727 / $764 | $1266 / $1431 / $1612 | $1881 / $2235 / $2647 | 91% |
| Equal weight (benchmark) | 100% | 100% | 0% | 0% | 1.2 / 1.4 / 1.6 | $672 / $747 / $824 | $1270 / $1474 / $1701 | $1901 / $2280 / $2730 | 91% |
| SPY buy-and-hold (benchmark) | 20% | 100% | 0% | 0% | 1.4 / 1.5 / 1.5 | $698 / $720 / $738 | $1283 / $1398 / $1504 | $1906 / $2159 / $2413 | 59% |
| SPY buy-and-hold (benchmark) | 50% | 100% | 0% | 0% | 1.3 / 1.4 / 1.6 | $683 / $738 / $786 | $1285 / $1434 / $1578 | $1923 / $2200 / $2478 | 59% |
| SPY buy-and-hold (benchmark) | 100% | 100% | 0% | 0% | 1.2 / 1.3 / 1.6 | $655 / $768 / $873 | $1277 / $1492 / $1693 | $1933 / $2262 / $2587 | 59% |
| UPRO buy-and-hold (benchmark) | 20% | 100% | 0% | 0% | 1.3 / 1.4 / 1.6 | $676 / $741 / $799 | $1209 / $1471 / $1722 | $1769 / $2280 / $2866 | 100% |
| UPRO buy-and-hold (benchmark) | 50% | 100% | 0% | 0% | 1.1 / 1.3 / 1.6 | $619 / $786 / $957 | $1213 / $1556 / $1921 | $1813 / $2349 / $3067 | 100% |
| UPRO buy-and-hold (benchmark) | 100% | 100% | 0% | 0% | 0.8 / 1.1 / 1.7 | $517 / $855 / $1187 | $1211 / $1662 / $2157 | $1839 / $2434 / $3319 | 100% |

### $100 added per month

| Series | Size | P($1,000 before $20) | P($20 first) | Neither in 30y | Years to $1,000 (10th / median / 90th) | Value after 1y (10th / median / 90th) | After 2y | After 3y | P(kill switch after $1,000) |
|---|---|---|---|---|---|---|---|---|---|
| V073 P2 6-month 1x | 20% | 100% | 0% | 0% | 0.8 / 0.8 / 0.8 | $1286 / $1343 / $1397 | $2522 / $2741 / $2963 | $3866 / $4277 / $4737 | 8% |
| V073 P2 6-month 1x | 50% | 100% | 0% | 0% | 0.8 / 0.8 / 0.8 | $1290 / $1352 / $1412 | $2531 / $2751 / $2977 | $3874 / $4288 / $4750 | 8% |
| V073 P2 6-month 1x | 100% | 100% | 0% | 0% | 0.8 / 0.8 / 0.8 | $1291 / $1368 / $1444 | $2542 / $2769 / $3004 | $3889 / $4311 / $4776 | 8% |
| V074 P2 6-month leveraged | 20% | 100% | 0% | 0% | 0.8 / 0.8 / 0.8 | $1214 / $1385 / $1550 | $2297 / $2960 / $3775 | $3501 / $4626 / $6653 | 100% |
| V074 P2 6-month leveraged | 50% | 100% | 0% | 0% | 0.7 / 0.8 / 0.8 | $1219 / $1410 / $1601 | $2316 / $2989 / $3824 | $3519 / $4658 / $6727 | 100% |
| V074 P2 6-month leveraged | 100% | 100% | 0% | 0% | 0.6 / 0.7 / 0.8 | $1213 / $1449 / $1699 | $2343 / $3034 / $3918 | $3545 / $4698 / $6852 | 100% |
| Equal weight (benchmark) | 20% | 100% | 0% | 0% | 0.8 / 0.8 / 0.8 | $1252 / $1350 / $1442 | $2422 / $2786 / $3185 | $3665 / $4379 / $5213 | 91% |
| Equal weight (benchmark) | 50% | 100% | 0% | 0% | 0.8 / 0.8 / 0.8 | $1255 / $1361 / $1466 | $2431 / $2797 / $3200 | $3673 / $4395 / $5236 | 91% |
| Equal weight (benchmark) | 100% | 100% | 0% | 0% | 0.7 / 0.8 / 0.8 | $1249 / $1383 / $1519 | $2439 / $2822 / $3245 | $3692 / $4417 / $5275 | 91% |
| SPY buy-and-hold (benchmark) | 20% | 100% | 0% | 0% | 0.8 / 0.8 / 0.8 | $1273 / $1349 / $1412 | $2461 / $2731 / $2983 | $3726 / $4250 / $4770 | 59% |
| SPY buy-and-hold (benchmark) | 50% | 100% | 0% | 0% | 0.8 / 0.8 / 0.8 | $1268 / $1367 / $1451 | $2468 / $2748 / $3017 | $3737 / $4269 / $4802 | 59% |
| SPY buy-and-hold (benchmark) | 100% | 100% | 0% | 0% | 0.7 / 0.8 / 0.8 | $1248 / $1399 / $1522 | $2473 / $2776 / $3078 | $3751 / $4304 / $4856 | 59% |
| UPRO buy-and-hold (benchmark) | 20% | 100% | 0% | 0% | 0.7 / 0.8 / 0.8 | $1228 / $1380 / $1519 | $2286 / $2837 / $3376 | $3457 / $4373 / $5611 | 100% |
| UPRO buy-and-hold (benchmark) | 50% | 100% | 0% | 0% | 0.6 / 0.7 / 0.8 | $1194 / $1433 / $1638 | $2305 / $2880 / $3485 | $3480 / $4405 / $5719 | 100% |
| UPRO buy-and-hold (benchmark) | 100% | 100% | 0% | 0% | 0.5 / 0.7 / 0.9 | $1142 / $1508 / $1794 | $2307 / $2940 / $3648 | $3504 / $4447 / $5868 | 100% |

## Method and limits

- 10,000 paths per cell, a 20-day circular block bootstrap of validation-period daily (return, T-bill) pairs, and a 30-year horizon.
- Seed 20261022 + series index; the same random draws are used for every size and contribution level of a series, so comparisons within a series are like for like.
- **Below $1,000:** a constant fraction (20/50/100%%) is in the strategy and the rest earns T-bills. Exposure is rebalanced daily. That rebalancing is not charged costs and ignores the $1 minimum order, which flatters the 20%% and 50%% cells slightly. No stops, caps or kill switch apply (your rule).
- **From the first close at or above $1,000:** Phase 7B applies permanently. Exposure is capped (SPY 50%%, UPRO 30%%; the multi-asset series already hold 25%% slices), and a −20%% drop from the post-$1,000 peak moves the account to cash for good. The 2%% per-trade rule is not modelled; it is designed in Phase 7B.
- Contributions arrive every 21 trading days and count toward $1,000. Paths keep running after touching $20 (an aggressive account has no kill switch), so 1/2/3-year values include recoveries funded by contributions.
- Taxes are not included here.
- Python 3.14.8, pandas 3.1.0, numpy 2.5.4. Run 2026-10-22T20:03:55Z.
