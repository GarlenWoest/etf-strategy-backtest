# Phase 9c: commodity data quality (through 2023-12-29; holdout locked)

Produced by `tools/download_commodities.py`. Raw files are in `data/raw/commodities/`, which is not committed. Rows, dates and SHA-256 hashes are in `download_meta.json`, and every validation issue with its dates is in `results/commodities_validation.json`.

- **Sources:** Yahoo Finance via yfinance (prices) and FRED's `fredgraph.csv` endpoint (macro series). No new packages were installed.
- **Holdout:** every request ended before 2024-01-01 (exclusive). No source returned a row on or after that date, so **0 holdout rows were dropped**, and the last row in every file is 2023-12-29 (CPI: 2023-12-01, monthly).
- **Checks:** the same checks as Phase 2 (`src/data.validate_prices`), run against the SPY trading calendar: duplicates, NaN or non-positive prices, OHLC consistency, missing or extra days, moves above 10% (flagged and kept), and runs of 3 or more unchanged closes.
- **Nothing was filled, interpolated or edited.**

## Start dates
| Ticker | What it is | First day | Rows | Usable from (my judgment) |
|---|---|---|---|---|
| GLD | Gold (grantor trust) | 2004-11-18 | 4,811 | 2004-11-18 |
| IAU | Gold (grantor trust) | 2005-01-28 | 4,763 | 2005-01-28 |
| GLDM | Gold (grantor trust) | 2018-06-26 | 1,388 | 2018-06-26 (too short for in-sample; tracks GLD) |
| SLV | Silver (grantor trust) | 2006-04-28 | 4,449 | 2006-04-28 |
| USO | WTI futures pool | 2006-04-10 | 4,462 | 2006-04-10 (structure changed April 2020, see below) |
| CPER | Copper futures pool | 2011-11-15 | 3,050 | **2017** (see problem 1) |
| UGL | 2x gold | 2008-12-03 | 3,794 | 2008-12-03 |
| AGQ | 2x silver | 2008-12-04 | 3,793 | 2008-12-04 |
| UCO | 2x WTI | 2008-11-25 | 3,799 | 2008-11-25 |
| DGP | 2x gold ETN | 2008-02-28 | 3,988 | 2008-02-28 |
| SPY | Benchmark | 2000-01-03 | 6,037 | 2000-01-03 |
| GC=F, SI=F, CL=F, HG=F | Front-month continuous futures (signals only) | 2000-08-23 to 2000-08-30 | about 5,860 each | Signals only (see problem 3) |
| ^GVZ | Gold ETF implied volatility | 2008-06-03 | 3,922 | Signal |
| ^OVX | Oil ETF implied volatility | 2007-05-10 | 4,190 | Signal |
| ^IRX | T-bill rate (cash) | 2000-01-03 | 6,031 | As in Phase 2 |
| DFII10 | 10-year TIPS real yield | 2003-01-02 | 5,477 (223 blanks) | Signal |
| T10YIE | 10-year breakeven inflation | 2003-01-02 | 5,477 (223 blanks) | Signal |
| DTWEXBGS | Broad dollar index | 2006-01-02 | 4,695 (183 blanks) | Signal |
| DTWEXM | Major-currency dollar index | 2000-01-03 | ends 2019-12-31 (discontinued) | Pre-2006 dollar signal only |
| CPIAUCSL | CPI, monthly | 2000-01-01 | 288 | Signal; lag by the release date (about 2 weeks after month end) |

FRED blanks are market holidays (FRED marks them "."). They are left blank, and any signal must use the last value known on that date.

## Consistency with the Phase 2 data
GLD, UGL and SPY were downloaded again. Their daily returns match the Phase 2 files exactly (maximum difference 0 for GLD and UGL, and 1.5e-6 for SPY over 2004–2023, from adjustment rounding).

## Problems found
1. **CPER is unreliable before 2017.**
   - Median volume was 200–800 shares a day in 2012–2015.
   - It had 329 zero-volume days in 2011–2018, and 132 dates sit inside runs of 3 or more unchanged closes, almost all in 2012–2016.
   - Its daily correlation with copper futures (HG=F) was 0.41 in 2011–2016 and 0.91 in 2017–2023.

   **Result:** CPER has no usable in-sample period before 2017 under the current splits (in-sample to 2018). Options are:
   - (a) a synthetic CPER history from HG=F (front-month, so it ignores roll costs, which makes it optimistic);
   - (b) use copper only as a signal;
   - (c) drop copper.

   **This is your decision; nothing has been done yet.**
2. **USO changed structure in April 2020.**
   - It moved from front-month WTI futures to a spread across several months, and did a 1-for-8 reverse split on 2020-04-29. The adjusted data handle the split: there is no gap on that date.
   - 2020-03 to 2020-04 contains 10 moves above 10%. They are real (the oil crash), but USO's pre-2020 and post-2020 behavior differ.
3. **Front-month futures from Yahoo are signal-quality only.**
   - **Bad high/low values:** GC=F has 441 days, HG=F 300, SI=F 243 and CL=F 7 where the high or low doesn't contain the open and close. Yahoo's settle-based close is mixed with session high/low values.
   - **Missing days:** 15–19 days each, mostly early-2000s half-day holidays.
   - **Extra days:** 3–7 holiday sessions each, e.g. 2023-11-23.
   - **Negative prices:** CL=F closed negative on 2020-04-20 and 2020-04-21 (real), which breaks log returns and percentage signals.
   - **Contract rolls:** the series are spliced across rolls with no back-adjustment, so roll days show artificial jumps.
   - **Timing:** GLD and GC=F daily returns correlate only 0.88, because the futures settle (1:30 pm ET) and the ETF close (4 pm ET) happen at different times.

   **Rule I'd propose:** signals from ETF closes where possible; futures closes only for pre-ETF history or as a cross-check, and never as traded prices.
4. **The leveraged funds have reverse splits and extreme days.**
   - **Splits:** UCO had 5 split events and AGQ had 2. The adjusted closes show no jump on split days, with one exception: UCO on 2020-04-21 (−56.8%, the day after WTI went negative).
   - **That UCO day:** USO fell 25.1% the same day, so 2x leverage plus UCO's different futures mix makes it plausible. It can't be cross-checked without a second source (Stooq is still blocked).
   - **Big-move counts (above 10%):** UCO 125 and AGQ 81. All are kept and flagged.
5. **Minor stale closes:**
   - IAU: 6 short runs.
   - SLV: 4 runs.
   - UGL: 1 run, on 2018-05-22, the same window as the unresolved Phase 2 suspect.
   - GLDM and AGQ: 1 run each.
   - These are small, and each was kept as is.
6. **^IRX** shows the same artifacts as in Phase 2: near-zero rates and stale runs in 2009–2015 and 2020–2021. It is used as in Phase 2.

## What was not downloaded, and why
- **Futures term structure (second and later contracts):** not available free with reliable history. Carry, roll-yield and basis-momentum ideas are flagged in the idea pool.
- **CFTC Commitments of Traders:** free from cftc.gov (weekly), but not downloaded, because none of the ranked ideas uses it yet. It can be added if you pick a positioning idea.
- **XAU/USD spot and physical gold prices:** not needed; GLD/IAU are the proxy.
