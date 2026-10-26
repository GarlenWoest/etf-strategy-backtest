# USD/JPY study 1: results and kill table (V135–V142)

_Run 2026-10-26T15:38:46Z. Pre-registered in commit 2aae894 (`research/USDJPY_PREREGISTRATION.md`); run exactly as frozen. Python 3.14.8, pandas 3.1.0, numpy 2.5.4._

## Result first

- **Survivors: NO.** 0 of 8 trials pass all of K1–K7; nothing goes further.
- **Best Deflated Sharpe at N = 142: 0.368** (V142, UJ-H4 relative curve slope lookback=126d), against 0.95 required. Hurdle: an annualized Sharpe of about 0.58 is what the best of 142 unskilled trials would reach over these 9 years.
- **Benchmarks, validation 2015–2023:** flat (UB01) Sharpe 0.00 by construction; always long USD/JPY 1x (UB02) Sharpe **0.24** (overlay +0.8% a year).
- **Single-pair caveat:** the strongest carry and momentum evidence is cross-sectional across many currencies; single-pair results were expected to be weaker (Burnside, Eichenbaum & Rebelo 2008).

## Each trial against both benchmarks (validation 2015–2023, 1x costs)

| ID | Hypothesis | Params | Val Sharpe | vs flat (0) | vs always-long (0.24) | DSR (N=142) | 95% CI | IS Sharpe | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| V135 | UJ-H1 carry level | maturity=1Y | 0.38 | beats | beats | 0.274 | -0.28 to 1.04 | 0.11 | **KILLED** |
| V136 | UJ-H1 carry level | maturity=2Y | 0.22 | beats | **loses** | 0.142 | -0.41 to 0.90 | 0.09 | **KILLED** |
| V137 | UJ-H2 differential momentum | lookback=63d | -0.06 | **loses** | **loses** | 0.027 | -0.73 to 0.60 | 0.27 | **KILLED** |
| V138 | UJ-H2 differential momentum | lookback=126d | -0.11 | **loses** | **loses** | 0.020 | -0.77 to 0.55 | -0.09 | **KILLED** |
| V139 | UJ-H3 carry with risk-off filter | filter=VIX>p80(252d) | 0.09 | beats | **loses** | 0.070 | -0.56 to 0.75 | 0.06 | **KILLED** |
| V140 | UJ-H3 carry with risk-off filter | filter=USDJPY_vol21>p80(252d) | 0.24 | beats | beats | 0.153 | -0.40 to 0.92 | 0.02 | **KILLED** |
| V141 | UJ-H4 relative curve slope | lookback=63d | -0.09 | **loses** | **loses** | 0.023 | -0.74 to 0.57 | 0.14 | **KILLED** |
| V142 | UJ-H4 relative curve slope | lookback=126d | 0.47 | beats | beats | 0.368 | -0.17 to 1.12 | -0.26 | **KILLED** |

## Kill reasons (mechanical; criteria from `config.yaml usdjpy_study1.kill_criteria`)

| ID | Reasons |
|---|---|
| V135 | K2 DSR 0.274 < 0.95; K5 neighbour V136 fails K1 |
| V136 | K1 val Sharpe 0.22 does not beat always-long 0.24; K2 DSR 0.142 < 0.95 |
| V137 | K1 val Sharpe -0.06 does not beat flat 0.00 and always-long 0.24; K2 DSR 0.027 < 0.95; K3 profitable at 1x (+5.5%) but not at 2x (-2.5%); K5 neighbour V138 fails K1; K6 val Sharpe -0.06 < half of in-sample 0.27 |
| V138 | K1 val Sharpe -0.11 does not beat flat 0.00 and always-long 0.24; K2 DSR 0.020 < 0.95; K3 profitable at 1x (+2.0%) but not at 2x (-5.2%); K5 neighbour V137 fails K1; K6 val Sharpe -0.11 < half of in-sample -0.09 |
| V139 | K1 val Sharpe 0.09 does not beat always-long 0.24; K2 DSR 0.070 < 0.95 |
| V140 | K2 DSR 0.153 < 0.95; K5 neighbour V139 fails K1 |
| V141 | K1 val Sharpe -0.09 does not beat flat 0.00 and always-long 0.24; K2 DSR 0.023 < 0.95; K3 profitable at 1x (+3.3%) but not at 2x (-4.7%); K6 val Sharpe -0.09 < half of in-sample 0.14 |
| V142 | K2 DSR 0.368 < 0.95; K5 neighbour V141 fails K1 |

## Detail

| ID | IS overlay/yr | Val overlay/yr | Val Sharpe 2x / 3x costs | Val Sharpe lag 2 | Val ledger return 1x / 2x | Val max DD | Position changes | Median hold (days) | In market (val) | Long share (val) |
|---|---|---|---|---|---|---|---|---|---|---|
| V135 | +0.7% | +2.4% | 0.31 / 0.25 | 0.38 | +38.0% / +33.1% | -11.1% | 94 | 465 | 57% | 57% |
| V136 | +0.5% | +1.5% | 0.15 / 0.08 | 0.22 | +27.2% / +22.1% | -14.5% | 120 | 18 | 64% | 64% |
| V137 | +2.8% | -0.5% | -0.16 / -0.27 | -0.01 | +5.5% / -2.5% | -21.7% | 963 | 20 | 100% | 65% |
| V138 | -0.9% | -0.9% | -0.20 / -0.30 | -0.13 | +2.0% / -5.2% | -27.2% | 765 | 20 | 100% | 67% |
| V139 | +0.4% | +0.6% | 0.02 / -0.05 | 0.07 | +17.5% / +12.8% | -14.6% | 478 | 14 | 53% | 53% |
| V140 | +0.1% | +1.3% | 0.16 / 0.09 | 0.22 | +26.1% / +21.6% | -13.5% | 396 | 34 | 49% | 49% |
| V141 | +1.4% | -0.8% | -0.19 / -0.29 | -0.28 | +3.3% / -4.7% | -28.7% | 1180 | 14 | 100% | 61% |
| V142 | -2.7% | +3.9% | 0.37 / 0.28 | 0.41 | +57.3% / +46.4% | -19.6% | 907 | 14 | 100% | 66% |
| UB02 | -0.2% | +0.8% | 0.16 / 0.08 | 0.24 | +21.9% / +19.4% | -9.0% | 61 | 8282 | 100% | 100% |

## Stress windows ($10,000 at the start of each window; lowest value)

| ID | 1998 | 2008-09 | 2011 | 2022 |
|---|---|---|---|---|
| V135 | -10.0% (low $8967) | -5.6% (low $9185) | +0.0% (low $10000) | +16.7% (low $9975) |
| V136 | -10.0% (low $8967) | -5.6% (low $9185) | +0.0% (low $10000) | +16.8% (low $9922) |
| V137 | +23.4% (low $9685) | +14.5% (low $10000) | -2.5% (low $9600) | +15.9% (low $9892) |
| V138 | +22.4% (low $9956) | -2.9% (low $9345) | -2.5% (low $9600) | +15.9% (low $9892) |
| V139 | -0.3% (low $9972) | -2.5% (low $9594) | +0.0% (low $10000) | +2.9% (low $9787) |
| V140 | -12.4% (low $8756) | -2.6% (low $9578) | +0.0% (low $10000) | +3.9% (low $9922) |
| V141 | +17.9% (low $9691) | +30.4% (low $10000) | +1.1% (low $9877) | +16.3% (low $9889) |
| V142 | +22.7% (low $10000) | -2.9% (low $9344) | +0.7% (low $9619) | +15.9% (low $9892) |
| UB02 | -10.0% (low $8967) | -4.3% (low $9109) | -0.5% (low $9819) | +7.5% (low $9958) |

## Walk-forward (choose the grid value with the best prior-5-year Sharpe; test the next year)

| Hypothesis | Trials | WF Sharpe 1996–2023 | WF Sharpe 2015–2023 | Always-long 2015–2023 | Choices |
|---|---|---|---|---|---|
| UJ-H1 carry level | V135,V136 | 0.21 | 0.38 | 0.24 | 1996:V135 1997:V135 1998:V135 1999:V136 2000:V136 2001:V136 2002:V135 2003:V135 2004:V136 2005:V136 2006:V136 2007:V135 2008:V136 2009:V136 2010:V135 2011:V136 2012:V136 2013:V136 2014:V135 2015:V135 2016:V135 2017:V135 2018:V135 2019:V135 2020:V135 2021:V135 2022:V136 2023:V136 |
| UJ-H2 differential momentum | V137,V138 | -0.03 | -0.28 | 0.24 | 1996:V137 1997:V137 1998:V137 1999:V137 2000:V137 2001:V137 2002:V137 2003:V137 2004:V137 2005:V137 2006:V137 2007:V138 2008:V138 2009:V138 2010:V137 2011:V137 2012:V137 2013:V137 2014:V137 2015:V138 2016:V138 2017:V138 2018:V138 2019:V137 2020:V137 2021:V137 2022:V137 2023:V137 |
| UJ-H3 carry with risk-off filter | V139,V140 | 0.09 | 0.11 | 0.24 | 1996:V140 1997:V140 1998:V140 1999:V140 2000:V140 2001:V140 2002:V140 2003:V139 2004:V140 2005:V139 2006:V139 2007:V140 2008:V139 2009:V139 2010:V139 2011:V139 2012:V139 2013:V139 2014:V139 2015:V139 2016:V139 2017:V140 2018:V140 2019:V140 2020:V140 2021:V140 2022:V140 2023:V139 |
| UJ-H4 relative curve slope | V141,V142 | 0.15 | 0.47 | 0.24 | 1996:V141 1997:V141 1998:V141 1999:V141 2000:V141 2001:V141 2002:V141 2003:V141 2004:V141 2005:V141 2006:V141 2007:V141 2008:V142 2009:V141 2010:V141 2011:V141 2012:V141 2013:V141 2014:V141 2015:V142 2016:V142 2017:V142 2018:V142 2019:V142 2020:V142 2021:V142 2022:V142 2023:V142 |

Effective number of independent trials among the 8 (correlation-based, information only): 2.8.

## Method notes

- Sharpe = annualized daily overlay return (equity return minus cash return at DTB3), i.e. excess over T-bills.
- Costs: 0.015% of notional each way plus a 0.75%/yr rollover markup; 2x/3x multiply both.
- K3 uses the $10,000 ledger's total validation return (as in Studies 1–3); K7 rescales each stress window to $10,000.
- Prices: FRED DEXJPUS noon NY; US yields lagged 2 FX days, JGB and VIX 1 day; decisions weekly; execution next FX day (lag 1); lag 2 reported as robustness.
- The 2024+ holdout was not opened; data end 2023-12-29.

## Known issue found after the frozen run (not corrected, per the pre-registration)

The frozen sizing rule re-sizes a position only when the target changes or the notional exceeds 1x equity. When equity dips, the cap shrinks the notional, and it never grows back: always-long (UB02) exposure fell from 1.0x to about 0.39x by 2015 and 0.32x by 2023, and slow trials such as V135 (median hold 465 days) are affected similarly. Sharpe-based criteria (K1, K2, K6) are largely scale-invariant and every Deflated Sharpe is far below 0.95, so the verdict is very unlikely to change, but this has not been verified. Dollar figures (ledger returns, stress lows) are understated for long holds. Recorded as an error in the research memory; a later study should pre-register symmetric re-sizing.

V140 passes K1 by 0.0008 Sharpe (0.2379 vs 0.2371); applied as frozen, and it is killed by K2 and K5.
