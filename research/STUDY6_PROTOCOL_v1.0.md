# Study 6 protocol v1.0 (FROZEN at registration; NOT run)

_2026-11-02. Supersedes `research/STUDY6_DESIGN_DRAFT.md` (kept). Governed by **STATS_POLICY v1.1** (frozen 2026-11-02, sha256 `67c710df…`, register row STATS-POLICY-1.1). The data was downloaded after that freeze (`research/DATA_REGISTER.csv`, approval "decision 5"); only dates and availability were inspected, with no returns, statistics or rule evaluation. Historical N = 145 → **146** (Study 5 registered, not run), forward N = 2, and the 2024+ holdout stays locked. **Study 6 is one trial, V146. It runs only when the owner says so.**_

## 1. Decisions applied

| Decision (2026-11-02) | Effect here |
|---|---|
| 4: STATS_POLICY v1.1 | Primary test **t > 3.0** on the trial's test-window series. Romano–Wolf and DSR are reported only. Full cumulative N is reported |
| 5: 6a approved | Trial 6a (V146) below |
| S6-1: drop 6c | 6c is **dropped**, with the reason recorded in §3 |
| S6-2: window −1..+3 | 6a uses the original published window (Lakonishok & Smidt, 1988) |
| S6 secondaries | Two **SECONDARY** analyses are pre-registered in §2.7. They cannot change the verdict |
| Costs | The frozen Study 3 stock cost schedule (§2.5) |
| 5: 6b observe only | No trial. DBMF and KMLM are observed descriptively (§4) |
| P7 (v1.1) | The window is over 10 years. The written amendment is in §2.3 |

## 2. Trial V146: turn-of-month (TOM) equity (return claim)

### 2.1 Rule (fixed; nothing fitted)
- **Trading days** come from the data calendar. Day −1 is the last trading day of a month; +1 is the first trading day of the next month.
- **In market** for the returns of days **−1, +1, +2, +3**: enter at the close of day −2, exit at the close of day +3. Otherwise in cash (RF).

### 2.2 Data
- **Primary:** US market, Ken French daily `kf_factors_daily` (Mkt-RF + RF), held since R8.
- **Secondary:** Developed ex US, Ken French daily `kf_developed_ex_us_3f_daily` (Mkt-RF in USD + RF).
- **Window:** 1990-07-02 to 2023-12-29, about 33.5 years and 402 month-turns. A turn belongs to the window if its day −1 and day +3 are both inside the window.
  - The start is set by the developed-markets data. Applying it to the US series too keeps the window after Lakonishok & Smidt (1988).
- The **Developed** series (`kf_developed_3f_daily`) is not used.

### 2.3 P7 written amendment (window over 10 years)
- **Window:** 1990-07..2023-12, a single test window. No parameter is fitted, so there is no in-sample period.
- **Why untouched:** this project has never tested calendar rules.
  - Study 3 used the US market monthly 1927–2018, for trend and momentum only.
  - Studies 1–2 used ETFs 2005–2023 for trend and drawdown rules.
- **Not untouched by the literature:** McConnell & Xu (2008) [OV] cover the US to about 2005, so about 15 of the 33.5 US years are published. The developed ex US years are partly covered by international TOM studies [OV].
- **Label:** "weak confirmation: published-sample overlap". The post-publication sub-period is the secondary analysis (i) in §2.7.
- **Regime split, reported:** 1990-07..2006-12 and 2007-01..2023-12.

### 2.4 Primary statistic and pass
- For each month-turn m: e_m = (mean daily excess return on the 4 TOM days) − (mean daily excess return on the other trading days from the previous turn's +4 to this turn's −2). Excess means market return minus RF; the series is gross of costs.
- **Primary:** t-statistic of mean(e_m) over the window on the **US** series, **t > 3.0**. Newey–West (lag 3) t is reported alongside; the plain t decides.

### 2.5 Kill conditions (any one rejects)
1. t ≤ 3.0 on the US series.
2. **Costs:** the strategy net of costs, in market on TOM days and in RF otherwise, has a lower annualized excess return per unit of time in market than always long, at **2× costs**.
   - Cost schedule: the frozen Study 3 stock schedule (`config.yaml` study3_longhist `costs_one_way.stocks`): 0.34% one-way to 1992, 0.11% 1993–2002, 0.07% from 2003.
   - About 24 one-way trades a year.
3. **Placebo:** the same 4-day window placed at a fixed offset of +10 trading days from the turn has a mean(e_m) ≥ TOM's, on the US series.
4. mean(e_m) has the opposite sign in either half of the regime split (US).

### 2.6 Reported, not deciding
- DSR at N = 146, using the within-family variance. "Calendar" is a new family, so the variance comes from this trial alone; this is stated.
- Romano–Wolf over the study's single trial (equal to the plain test; stated).
- Net-of-cost Sharpe vs always long; turnover.
- Results at 1× and 3× costs.
- The Newey–West t.

### 2.7 SECONDARY analyses (pre-registered; cannot change the verdict)
Both use the primary statistic (§2.4) and report t against the 3.0 threshold, the Newey–West t, and the net-of-cost comparison at 1× and 2× costs. Their results are labelled "SECONDARY (pre-registered; cannot change the V146 verdict)" in the report and the research memory. They do not add to N.

- **(i) Post-publication sub-period, US:** turns with day −1 from 2009-01 to 2023-12, about 180 turns (15 years). It starts after McConnell & Xu (2008).
- **(ii) Developed ex US only:** the full window, 1990-07..2023-12, about 402 turns.

### 2.8 Power [estimate]
- Per-turn standardized effect d = mean(e_m) / sd(e_m). Power = Φ(d·√n − 3), normal approximation.
- Pre-publication TOM magnitudes imply d ≈ 0.2 [estimate]. Post-publication decay is likely.

| Analysis | Turns n | d needed for t > 3 | Power at d = 0.10 | at d = 0.15 | at d = 0.20 |
|---|---|---|---|---|---|
| **Primary: US 1990-07..2023-12** | 402 | 0.150 | 0.16 | 0.50 | 0.84 |
| Secondary (i): US 2009-01..2023-12 | 180 | 0.224 | 0.05 | 0.16 | 0.38 |
| Secondary (ii): Developed ex US 1990-07..2023-12 | 402 | 0.150 | 0.16 | 0.50 | 0.84 |

Secondary (i) is underpowered: a failure there is weak evidence of decay, not a refutation.

### 2.9 $100–$1,000
- Feasible with fractional shares of a broad US ETF at zero-commission brokers [OV: broker-specific].
- Spread costs dominate. The kill condition at 2× costs is the binding test.

## 3. Trial 6c: G10 FX carry + momentum + value: DROPPED (S6-1, 2026-11-02)
- **Not registered; no trial ID; not in N.**
- **Reason:**
  - Power reached 0.54 at Sharpe 0.5 under t > 3 only with a single 1985-08..2023-12 test window. That would have been an exception to the approved FX period scheme (power 0.07 on its 2015–2023 validation window).
  - About 24 of the 38.4 years are the published sample (canonical datasets 1983–2009/2010 [L: FX005, FX008]).
  - The post-publication part alone (2011–2023) has power 0.12.
  - A pass would mostly reconfirm the published samples rather than test them.
- **Record of the coverage check:** first return month 1985-08, set by the Japanese short rate (OECD IRSTCI from 1985-07). There is no DEM series in the current H.10 package. OECD CPI for JPN ends 2021-06.
- The downloaded data stays registered; no 6c rule is ever evaluated on it under this protocol.

## 4. 6b: observation only (no trial, no N)
- Monthly total returns of **DBMF** and **KMLM** are recorded from their inception onward, descriptively, as an observation log.
- **Source and terms:** to be decided. Yahoo automated collection is excluded; Alpaca daily bars for ETFs are already allow-listed read-only.
- **2024+ rule:** observing these ETFs in 2024+ is an external-product observation, not a rule evaluation. D1 still forbids computing performance on 2024+ data outside the forward registry, so **the log starts at registration and is appended prospectively**, like the GF observation records. Nothing before registration is looked at.

## 5. Trials and N

| ID | Trial | Claim | Window | N after |
|---|---|---|---|---|
| V146 | 6a TOM equity | Return | 1990-07..2023-12 | **146** |

The forward registry is unaffected (forward N = 2).

## 6. Run plan (only when the owner says so)
1. Write `tools/run_study6.py` with unit tests on synthetic data before any real-data run. The tests cover the TOM calendar, turn membership in the window, the placebo offset and the cost schedule.
2. Run once; report in the format of §2.4–2.8, failures included.
3. Append the results to the research memory.

## 7. Limitations (stated in every result)
- Ken French market series are indices, not tradable funds.
- Large published-sample overlap (§2.3).

## 8. Decisions recorded (owner, 2026-11-02)
- **S6-1:** drop 6c (§3).
- **S6-2:** window −1..+3.
- **Secondaries:** (i) post-publication 2009–2023, (ii) Developed ex US only; SECONDARY, cannot change the verdict; power reported (§2.8).
- **Costs:** the frozen stock schedule.
- **S6-3, S6-4:** lapsed with 6c.
