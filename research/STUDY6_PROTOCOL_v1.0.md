# Study 6 protocol v1.0: for freeze approval (NOT frozen, NOT run)

_2026-11-02. Supersedes `research/STUDY6_DESIGN_DRAFT.md` (kept). Governed by **STATS_POLICY v1.1** (frozen 2026-11-02, sha256 `67c710df…`, register row STATS-POLICY-1.1). The data was downloaded after that freeze (`research/DATA_REGISTER.csv`, approval "decision 5"); only dates and availability were inspected, with no returns, statistics or rule evaluation. Historical N = 145 (Study 5 registered, not run), forward N = 2, and the 2024+ holdout stays locked._

**Blocking items before freeze:** decisions S6-1 to S6-4 (§9).

## 1. Decisions applied

| Decision (2026-11-02) | Effect here |
|---|---|
| 4: STATS_POLICY v1.1 | Primary test **t > 3.0** on the trial's test-window series. Romano–Wolf and DSR are reported only. Full cumulative N is reported |
| 5: 6a approved for drafting | Trial 6a below |
| 5: 6c only if power ≥ 0.5 at Sharpe 0.5 under t > 3 | Power **0.54**, but only with a **full-sample test window from 1985-08** that departs from the approved FX period scheme (§4). Under the scheme, power is **0.07**. Your decision: S6-1 |
| 5: 6b observe only | No trial. DBMF and KMLM are observed descriptively (§6) |
| P7 (v1.1) | Both windows are over 10 years. The written amendments are in §2.3 and §3.3 |

## 2. Trial 6a: turn-of-month (TOM) equity (proposed ID V146; return claim)

### 2.1 Rule (fixed; nothing fitted)
- **Trading days** come from the data calendar. Day −1 is the last trading day of a month; +1 is the first trading day of the next month.
- **In market** for the returns of days −2, −1, +1, +2, +3 (enter at the close of day −3, exit at the close of day +3). Otherwise in cash (RF).
- **Unchanged from the design draft:** the window. The classic Lakonishok & Smidt window is −1..+3; this protocol keeps the draft's −2..+3 and does not test both.

### 2.2 Data
- **Primary:** US market, Ken French daily `kf_factors_daily` (Mkt-RF + RF), held since R8.
- **Confirmation:** Developed ex US, Ken French daily `kf_developed_ex_us_3f_daily` (Mkt-RF in USD + RF). The **Developed** series (`kf_developed_3f_daily`) is reported only.
- **Window:** 1990-07-02 to 2023-12-29, about 33.5 years and 402 month-turns. The start is set by the developed-markets data. Applying it to the US series too keeps the window post-publication (Lakonishok & Smidt, 1988).

### 2.3 P7 written amendment (window over 10 years)
- **Window:** 1990-07..2023-12, a single test window. No parameter is fitted, so there is no in-sample period.
- **Why untouched:** this project has never tested calendar rules.
  - Study 3 used the US market monthly 1927–2018, for trend and momentum only.
  - Studies 1–2 used ETFs 2005–2023 for trend and drawdown rules.
- **Not untouched by the literature:** McConnell & Xu (2008) [OV] cover the US to about 2005, so about 15 of the 33.5 US years are published. The developed ex US years 1990–2023 are also partly covered by international TOM studies [OV].
- **Label:** "weak confirmation: published-sample overlap".
- **Regime split, reported:** 1990-07..2006-12 and 2007-01..2023-12.

### 2.4 Primary statistic and pass
- For each month-turn m: e_m = (mean daily excess return on the 5 TOM days) − (mean daily excess return on the other trading days from the previous turn's +4 to this turn's −3). Excess means market return minus RF; the series is gross of costs.
- **Primary:** t-statistic of mean(e_m) over the window on the **US** series, **t > 3.0**. Newey–West (lag 3) t is reported alongside; the plain t decides.

### 2.5 Kill conditions (any one rejects)
1. t ≤ 3.0 on the US series.
2. **Costs:** the strategy net of costs, in market on TOM days and in RF otherwise, has a lower annualized excess return per unit of time in market than always long, at **2× costs**.
   - Cost schedule: the frozen Study 3 stock schedule (`config.yaml` study3_longhist `costs_one_way.stocks`): 0.34% one-way to 1992, 0.11% 1993–2002, 0.07% from 2003.
   - About 24 one-way trades a year.
3. **Placebo:** the same 5-day window placed at a fixed offset of +10 trading days from the turn has a mean(e_m) ≥ TOM's, on the US series.
4. mean(e_m) has the opposite sign in either half of the regime split (US).
5. mean(e_m) on Developed ex US is ≤ 0. Only the sign is checked here, not significance.

### 2.6 Reported, not deciding
- DSR at N = 147 (or 146 without 6c), using the within-family variance. "Calendar" is a new family, so the variance comes from this trial alone; this is stated.
- Romano–Wolf over the study's trials.
- Net-of-cost Sharpe vs always long; turnover.
- Results at 1× and 3× costs.
- The Developed series; the Newey–West t.

### 2.7 Power [estimate]
- Per-turn standardized effect d (mean(e_m) / sd(e_m)) at 402 turns.
- t > 3 needs d > 0.150. Power is **0.50 at d = 0.15** (the design draft's 0.53 was a rounding error), 0.84 at d = 0.2, and 0.16 at d = 0.1.
- Pre-publication TOM magnitudes imply d ≈ 0.2 [estimate]. Post-publication decay is likely.

### 2.8 $100–$1,000
- Feasible with fractional shares of a broad US ETF at zero-commission brokers [OV: broker-specific].
- Spread costs dominate. The kill condition at 2× costs is the binding test.

## 3. Trial 6c: G10 FX carry + momentum + value (proposed ID V147; return claim; CONDITIONAL on S6-1)

### 3.1 Rule (fixed; nothing fitted)
- **Universe:** AUD, CAD, CHF, GBP, JPY, NOK, NZD and SEK from the first signal; **EUR from 1999-01** (9 currencies).
  - The current Board H.10 package has **no DEM series** (checked 2026-11-02), so there is no EUR leg before 1999.
- **Signal date:** the last H.10 observation of each month (New York noon). Positions earn the next month.
- **Carry:** 3-month rate minus the US 3-month rate.
  - Rates come from OECD IR3TIB. Where IR3TIB is not yet available, use IRSTCI (fixed fallback): JPN before 2002-04, CHE before 1999-07, GBR before 1986-01.
  - The mixed rate types are a stated limitation.
  - EUR uses EA20 IR3TIB.
- **Momentum:** the 12-month log spot change of the currency vs USD.
- **Value:** the negative of the 60-month change in the log real exchange rate (spot × CPI_foreign / CPI_US).
  - CPI is lagged 2 months (monthly CPI) or by the latest quarter ending ≥ 3 months before the signal (AUS, NZL quarterly).
- **Portfolio:**
  - Rank each signal across the available currencies and average the three ranks.
  - Long the top 3 and short the bottom 3, equal weight (1/6 gross each, gross 1×). Ties go to alphabetical order.
  - Rebalance monthly.
- **Return per leg:** daily H.10 spot return plus the rate differential accrued daily (actual/360), using the same rate series as the carry signal (covered interest parity approximation).

### 3.2 Data
- **Spot:** Board H.10 (`board_h10_*`; 7 new series plus the GBP and JPY rows already held).
- **Rates:** `oecd_g10_M_IR3TIB` and `oecd_g10_M_IRSTCI`.
- **CPI:** `oecd_g10_M_CPI` and `oecd_g10_Q_CPI`.
- **Gap:** OECD CPI for **JPN ends 2021-06** in both frequencies (S6-3).

### 3.3 Window and P7 written amendment
- **Window:** first return month **1985-08** through 2023-12, 461 months or 38.4 years. The start is set by the first Japanese rate (IRSTCI 1985-07); it also follows the NZD float (1985-03).
- **Conflict with the approved FX period scheme:** the scheme is in-sample 1990–2014, validation 2015–2023, holdout 2024+.
  - This trial uses the whole of 1985-08..2023-12 as **one test window**. Nothing is fitted, so no in-sample is needed. This **departs from the scheme**, and the R4a precedent rejected a pre-1990 window for H5-B.
  - On the scheme's validation window alone (9 years), power is **0.07**.
- **Why not untouched:**
  - **Published-sample overlap:** canonical carry and momentum samples run 1983–2009/2010 (FX005, FX008 [L]); value samples are similar [OV]. About 24 of 38.4 years are published.
  - **Prior project use:** USD/JPY carry and momentum were tested single-pair 1990–2023 (Study 4). GBP/USD 1990–2023 is in Study 5 (volatility targeting, registered, not run).
- **Label:** "weak confirmation: mostly published sample; JPY single-pair carry seen by Study 4".
- **Regime split, reported:**
  - 1985-08..2008-07 and 2008-08..2023-12 (carry crash);
  - post-publication 2011-01..2023-12 separately (power 0.12 there at Sharpe 0.5).

### 3.4 Primary statistic and pass
- t-statistic of the mean monthly net-of-cost return of the long-short portfolio, **t > 3.0**.
- The portfolio is dollar-neutral, so its return is already an excess return.

### 3.5 Kill conditions (any one rejects)
1. t ≤ 3.0.
2. Mean return ≤ 0 at **2× costs**.
   - Base one-way cost: **0.015%** (the frozen FX cost) for EUR, JPY, GBP, CHF, CAD and AUD; **0.03%** [estimate] for NZD, NOK and SEK (S6-4).
3. Regression alpha on the **dollar factor** (equal-weight long all available currencies vs USD, with carry) ≤ 0.
4. Opposite sign in either half of the carry-crash split.

**Changes from the design draft:**
- The draft's "t vs the dollar factor" is replaced by t on the dollar-neutral portfolio, plus the dollar-factor alpha as a kill condition.
- The draft's "one signal alone explains it" is reported, not deciding: each signal's own long-short is shown.

### 3.6 Power
- Monthly i.i.d. normal approximation; power = Φ(SR·√Y − 3).

| Window | Years | Power at Sharpe 0.5 | Sharpe needed for power 0.5 |
|---|---|---|---|
| FX scheme validation 2015–2023 | 9.0 | 0.07 | 1.00 |
| Design draft 1990-07..2023-12 | 33.5 | 0.46 | 0.52 |
| **This protocol 1985-08..2023-12** | **38.4** | **0.54** | **0.48** |
| Unbalanced ≥ 7 currencies from 1979-01 (not proposed: AUD/NZD pegged, capital controls) | 45.0 | 0.64 | 0.45 |
| 1974–2023 (not attainable: no Japanese rate before 1985) | 50.0 | 0.70 | 0.42 |

- The 1971 H.10 start is not binding. **Rates are:** JPN 1985-07, NOR 1979, GBR 1978.

### 3.7 $100–$1,000
- Implementable at OANDA US with 1-unit sizing across 6 pairs [OV].
- Broker financing differs from the OECD-rate model.

## 4. Approved FX period scheme: how this protocol treats it
- **6a:** equity, not covered by the FX scheme.
- **6c:** needs an explicit exception (S6-1). If you decline it, 6c is dropped (power 0.07 on the scheme).

## 5. Trials and N

| Proposed ID | Trial | Claim | Window | N after |
|---|---|---|---|---|
| V146 | 6a TOM equity | Return | 1990-07..2023-12 | 146 |
| V147 | 6c G10 FX cross-section (if S6-1 = keep) | Return | 1985-08..2023-12 | 147 |

The forward registry is unaffected (forward N = 2).

## 6. 6b: observation only (no trial, no N)
- Monthly total returns of **DBMF** and **KMLM** are recorded from their inception onward, descriptively, as an observation log.
- **Source and terms:** to be decided. Yahoo automated collection is excluded; Alpaca daily bars for ETFs are already allow-listed read-only.
- **2024+ rule:** observing these ETFs in 2024+ is an external-product observation, not a rule evaluation. D1 still forbids computing performance on 2024+ data outside the forward registry, so **the log starts at registration and is appended prospectively**, like the GF observation records. Nothing before registration is looked at.

## 7. Run plan (after freeze only)
1. Freeze (sha256, `PROTOCOL_REGISTER.csv` row, research-memory `preregistration` record).
2. Write `tools/run_study6.py` with unit tests on synthetic data before any real-data run. The tests cover the TOM calendar, rank ties, CPI lags and the rate fallback.
3. Run once; report in the format of §2.4–2.6 and §3.4–3.5, failures included.
4. Append the results to the research memory.

## 8. Limitations (stated in every result)
- Ken French market series are indices, not tradable funds.
- H.10 noon rates are not tradable closes.
- The CIP approximation ignores forward-basis deviations (large after 2008 [OV]).
- Mixed short-rate types.
- Large published-sample overlap for both trials.

## 9. Decisions needed before freeze

- **S6-1:** keep 6c with the single 1985-08..2023-12 test window (an exception to the FX period scheme, power 0.54), or drop 6c.
  - **My recommendation: drop.** The power clears 0.5 only by departing from the scheme you upheld in R4a. About 24 of the 38 years are the published sample, and the post-publication part alone has power 0.12. A pass would largely re-confirm the literature, not test it.
- **S6-2:** 6a window −2..+3 (as drafted) or −1..+3 (Lakonishok & Smidt). Pick one; the other is never run.
- **S6-3 (only if 6c is kept):** JPN CPI after 2021-06. Options:
  - (a) carry the last value forward (stale for 30 months);
  - (b) rank JPN on carry and momentum only from 2021-07;
  - (c) approve a download of Japan's CPI from the Statistics Bureau of Japan (e-Stat; terms to be checked first).
- **S6-4 (only if 6c is kept):** the 0.03% one-way cost estimate for NZD, NOK and SEK.
