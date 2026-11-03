# Prior-exposure register

_Created 2026-11-02 (second outside review). It lists every period, market and idea already **seen**, whether by this project's studies, by work outside this repository, or by the published samples behind its hypotheses. **Every future protocol must check this register and declare each overlap** (market × period × idea family) in a section "Prior exposure", with the label it implies ("untouched", "weak confirmation: …"). Append new rows; never delete (mark superseded with a date). Tags: **[L]** checked in this repository; **[OV]** from a citation not verified here; **[U]** unknown, owner to supply._

## A. This project's studies (returns computed)

| Study | Markets / data | Periods with returns computed | Idea families | Source |
|---|---|---|---|---|
| 1 ETFs (V001–V092) | GLD, SPY, QQQ, TLT and 2x/3x versions (`config.yaml` instruments) | In-sample 2006-01-03..2018-12-31; validation 2019-01-01..2023-12-31 (sensitivity 2006–2023) | Trend MA, TSMOM, RSI(2), rotation, leveraged rotation, vol-gated leverage, multi-asset trend, RSI(2)+trend | `research_log.csv` phases 4–6 [L] |
| 2 Commodities (V093–V118) | Gold, silver, oil funds + 2x | In-sample 2007-07-02..2018-12-31; validation 2019–2023 | TSMOM basket, vol-scaled trend, dual momentum, real yield, dollar trend | `research_log.csv` phases 9-4..9-6 [L] |
| 3 Long history (V119–V134) | Monthly: US stocks (Ken French), US bonds (FRED LTGOVTBD/GS10), commodities (AQR), gold (World Bank from 1971-10), cash | 1927-08-31..2018-12-31 (some 1972-11..2018-12) | Multi-asset trend, TSMOM | `config.yaml` study3_longhist [L] |
| 4 USD/JPY (V135–V142) | USD/JPY spot (FRED DEXJPUS), US/JP rates | In-sample 1991-01-02..2014-12-31 (warm-up from 1990-01-02); validation 2015-01-01..2023-12-31 | Carry level, rate-differential momentum, risk-off filter, curve slope | `config.yaml` usdjpy_study1 [L] |
| 5 (V143–V145) | GBP/USD, USD/JPY (Board H.10); US market MTD (Ken French daily) | In-sample from 1990-04-02..2014; validation 2015-01-02..2023-12-29 | Volatility targeting (risk); month-end equity-hedge flow | `reports/study5_kill_table.md` [L] |
| 5 post-hoc | Same | Validation 2015–2023 | Constant-exposure benchmark | `reports/study5_posthoc_supplementary.md` [L] |
| 6 (V146) | US market, Developed ex US (Ken French daily) | 1990-07-02..2023-12-29 | Turn of month | `reports/study6_kill_table.md` [L] |
| Diagnostics | Studies 1–4 stored metrics; V142 sizing and engine diagnostics | 2015–2023 (V142) | — | research log "DIAGNOSTIC" rows [L] |

## B. This project: frequency-only counts and data inspection (no returns examined)

| What | Market / period | Source |
|---|---|---|
| F001 trigger frequency (23 days) | USD/JPY + SPY 2004–2023 | Forward pre-registration [L] |
| R7 G1 frequency (72 validation, 189 in-sample events) | US market MTD, GBP/USD dates 1990–2023 | Study 5 protocol [L] |
| GF1 frequency (41 joint days, 38 independent) | GLD + SPY 2005-02-16..2023-12-29 (Yahoo adjusted) | Research memory record 104 [L] |
| Study 6 coverage check (dates and availability only) | G10 FX (H.10 1971–2023), OECD G10 rates and CPI | `research/STUDY6_PROTOCOL_v1.0.md` §3 [L] |
| Source comparisons (values, not returns) | DTB3 vs H.15 1954–2023; Treasury bills 2015–2023; OECD vs FRED IRSTCI 1985–2023 | `research/DATA_REGISTER.csv` [L] |
| Data-quality checks | HistData USD/JPY 2018–2019 timestamps; Yahoo vs ECB/Fed 2026-10-20..28 | `reports/data_quality*.md` [L] |

## C. This project: live and forward (2024+ allowed only here, D1)

| What | Period | Note |
|---|---|---|
| Forward registry: F001/F002 evaluations, GBP/USD and gold observation | From 2026-10-29 | The only place 2024+ rule evaluation may happen (D1) [L] |
| Monitoring trailing windows (Yahoo, then Alpaca/OANDA) | Windows reaching into 2024–2026 | Owner D1 2026-10-29: monitoring only, never rule evaluation [L] |
| ETF paper books and watchlist (V122/V074 live signals; Book B) | From 2026-10-26 | Failed rules observed live, not tested [L] |

## D. Outside this repository

| Source | Market × period × idea | Status |
|---|---|---|
| **MontyFinance** (separate project; read-only audit 2026-11-01) | **GBP/USD "C4/52" post-hoc result**: period, rule definition and result **not recorded in this repository [U]**. Owner to supply | Until supplied, treat **GBP/USD (all periods) as exposed** for any idea family MontyFinance tested; declare "weak confirmation: MontyFinance post-hoc" |
| MontyFinance financing audit | USD/JPY financing-rate definitions (no returns) | Findings used; no code (`reports/forward_reliability_2026-10-30.md`) [L] |
| 10-29 research report (local only) | Realistic single-market Sharpe ranges; AI forecasting evidence | Literature summary, no data [L] |
| External reviews (2026-11-02, two) | Literature claims (trend, carry, value, TOM, vol targeting, gold real yields) | `reports/research_review/EXTERNAL_REVIEW_2026-11-02.md` [OV] |

## E. Published samples behind this project's hypotheses

| Paper | Sample (as cited) | Families |
|---|---|---|
| Lakonishok & Smidt (1988) | DJIA to 1986 [OV] | Turn of month |
| McConnell & Xu (2008) | US to about 2005 [OV] | Turn of month |
| Menkhoff, Sarno, Schmeling & Schrimpf (2012), carry | 48 currencies incl. GBP, 1983–2009 [L: `research/library/knowledge.csv:6`] | FX carry |
| Menkhoff et al. (2012), FX momentum | 1976–2010 [L: FX008 per Study 6 draft] | FX momentum |
| Asness, Moskowitz & Pedersen (2013) | Multi-asset value and momentum, through about 2011 [OV] | Value, momentum |
| Moskowitz, Ooi & Pedersen (2012); Hurst, Ooi & Pedersen (2017) | 58 markets; century-long trend [OV] | Time-series momentum |
| Brunnermeier, Nagel & Pedersen (2008) | Carry crashes [OV] | Carry / deleveraging (F001, GF1 mechanism) |
| Melvin & Prins (2015) | Month-end hedging flows; sample not stated in the abstract [V abstract only] | Month-end flow (V145) |
| Krohn, Mueller & Whelan (2024) | Fix reversals [OV] | Fix effects |
| Andersen, Bollerslev, Diebold & Vega (2003) | Macro announcement effects [OV] | GF2 release-day variance |

## How to use it

1. **Before registration:** each protocol lists every row above that overlaps its market × period × idea family.
2. **Labels:**
   - **Overlap with section A or D:** "weak confirmation", or a different window.
   - **Overlap with section E:** "published-sample overlap" (L10).
3. **Confirmatory studies** (STATS_POLICY v1.2 draft) should use windows with no section A or D overlap in the same family.
