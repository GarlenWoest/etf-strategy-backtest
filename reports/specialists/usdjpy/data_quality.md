# USD/JPY specialist: data quality

_Produced by `tools/validate_usdjpy.py`. Downloaded 2026-10-23T16:08:49Z. All files truncated before 2024-01-01 right after parsing; originals deleted; rows dropped unread: mof_jgb_yields 668, mof_intervention 7. Nothing filled or edited. No strategy statistic is computed here._

## Series (from 1990, the study start)

| series | first (1990+) | last | values | duplicate dates | weekdays absent from file | blank values (holidays) | non-positive | large moves | values inside 5+ day unchanged runs |
|---|---|---|---|---|---|---|---|---|---|
| DEXJPUS (yen per USD) | 1990-01-02 | 2023-12-29 | 8533 | 0 | 0 | 337 | 0 | 21 (> 3%): 1998-10-07 +5.47, 2008-10-24 +5.08, 1998-06-17 +4.42, 2009-03-19 +4.31 | 0 |
| DGS1 | 1990-01-02 | 2023-12-29 | 8506 | 0 | 0 | 364 | n/a | 12 (> 0.30 pp): 2023-03-13 +0.6, 2008-09-19 +0.52, 2001-09-13 +0.5, 2008-01-22 +0.4 | 117 |
| DGS2 | 1990-01-02 | 2023-12-29 | 8506 | 0 | 0 | 364 | n/a | 14 (> 0.30 pp): 2023-03-13 +0.57, 2001-09-13 +0.54, 2008-09-15 +0.45, 2008-09-29 +0.41 | 46 |
| DGS10 | 1990-01-02 | 2023-12-29 | 8506 | 0 | 0 | 364 | n/a | 4 (> 0.30 pp): 2009-03-18 +0.51, 1994-04-04 +0.39, 1996-03-08 +0.34, 2022-11-10 +0.3 | 2 |
| DTB3 | 1990-01-02 | 2023-12-29 | 8506 | 0 | 0 | 364 | n/a | 27 (> 0.30 pp): 2008-09-17 +0.81, 2008-09-19 +0.74, 2008-03-24 +0.61, 2007-08-20 +0.57 | 179 |
| VIXCLS | 1990-01-02 | 2023-12-29 | 8575 | 0 | 0 | 294 | n/a | 7 (> 15.00 pp): 2020-03-16 +24.9, 2020-03-12 +21.6, 2018-02-05 +20, 2020-03-13 +17.6 | 0 |
| JGB 1Y | 1990-01-04 | 2023-12-29 | 8349 | 0 | 518 | 0 | n/a | 0 (> 0.30 pp) | 384 |
| JGB 2Y | 1990-01-04 | 2023-12-29 | 8349 | 0 | 518 | 0 | n/a | 1 (> 0.30 pp): 1995-08-16 +0.365 | 280 |
| JGB 10Y | 1990-01-04 | 2023-12-29 | 8349 | 0 | 518 | 0 | n/a | 0 (> 0.30 pp) | 0 |

"Weekdays absent" are mostly US holidays (FRED omits or blanks them). The JGB file follows Tokyo business days, so its absent weekdays include Japanese holidays.

## Cross-checks

| Check | Result |
|---|---|
| DEXJPUS (noon NY) vs Yahoo JPY=X close, 2003-01-02..2023-12-29 | levels agree (median diff -0.00%, 99th pct |diff| 1.60%), but daily-return correlation is only 0.39 (Yahoo shifted -1/0/+1 day: 0.37 / 0.39 / 0.04; 2011-2023 alone: 0.20). Yahoo FX daily bars are not on a consistent timestamp and are not used; DEXJPUS is the single price source (5235 days) |
| MoF JGB 10Y monthly mean vs FRED IRLTLT01JPM156N (OECD), 1990-01-01..2023-12-01 | corr 0.9995; mean abs diff 0.039 pp; max abs diff 0.485 pp; 408 months |

## MoF intervention record (USD/JPY operations only; counts of operation days)

| Year | yen_buying | yen_selling |
|---|---|---|
| 1991 | 3 | 0 |
| 1992 | 23 | 0 |
| 1993 | 0 | 49 |
| 1994 | 0 | 55 |
| 1995 | 0 | 43 |
| 1996 | 0 | 5 |
| 1997 | 3 | 0 |
| 1998 | 3 | 0 |
| 1999 | 0 | 12 |
| 2000 | 0 | 4 |
| 2001 | 0 | 7 |
| 2002 | 0 | 7 |
| 2003 | 0 | 82 |
| 2004 | 0 | 47 |
| 2010 | 0 | 1 |
| 2011 | 0 | 7 |
| 2022 | 3 | 0 |

Other-currency operations in the file, excluded from USD/JPY (25 days): the Euro (bought) the Japanese yen (sold) 1999–2003 (18); the German mark (bought) the Japanese yen (sold) 1993 (1); the US dollar (sold) the German mark (bought) 1991 (1); the US dollar (sold) the Indonesian rupiah (bought) 1997 (5).

## Point-in-time caveats

- **H.10 noon rate:** a market price observable at noon NY on its date; the Fed publishes H.10 weekly, so the official series lags but the price itself was observable.
- **H.15 yields (DGS*):** usable from the 2nd trading day after their date (rule used in Study 2).
- **JGB yields:** MoF posts them after the Tokyo close; usable from the next US trading day.
- **Intervention:** the 1991-04 to 2001-03 daily record was disclosed only in July 2001 (Ito 2003); today MoF publishes monthly totals about 2 days after each monthly period and daily detail about 5 weeks after each quarter (MoF pages, 2026). When monthly totals were first published is UNVERIFIED. Any signal must use publication dates, never intervention dates.
- **VIX:** an end-of-day index; usable the next trading day.
