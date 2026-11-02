# Gold forward observation rules GF1 and GF2: pre-registration v1.0 (FROZEN as a document)

_Drafted and frozen 2026-11-02 under owner decisions R10 (2026-11-02: GF2, plus GF1 as record-only; GF3 dropped) and "freeze GF2 and GF1 as documents now". The freeze hash and date are recorded in `research/PROTOCOL_REGISTER.csv` and the research memory. **Frozen as a document only:** no recording is implemented yet, and **counting has not started**. Counting starts on the first completed NYSE trading day after the recording code is merged and its first evening pass is confirmed clean (§0, freeze procedure, step 3, as amended by this note). No runner change until today's 16:45 / 17:02 checks pass and the audit fixes are done; the implementation will be proposed with tests._

## 0. Common terms (both rules)

- **Status:** INFORMATION ONLY, forward observation rules. **No paper entries, no orders, no tickets, no trade alerts.** Not F-rules, and not counted in forward N (they make no trades). Their observations are recorded and evaluated **only inside the forward registry**, as data-governance rule D1 requires (`research/USDJPY_FORWARD_TEST_PREREG.md:180`).
- **Why forward-only:** gold has no untouched licensed daily history (`research/STUDY5_DESIGN_DRAFT.md:62`). Only data recorded after this freeze is clean.
- **Freeze procedure:**
  1. You approve the final text.
  2. Its SHA-256 is recorded in `config.yaml`, the research memory and the registry (kind `preregistration`).
  3. Counting starts from the **first completed NYSE trading day after the recording code is live and its first evening pass is confirmed clean**. Nothing before that counts, even if the observation layer already holds the bars.
- **Data, as already collected by the observation layer:**
  - GLD and SPY daily bars from the **Alpaca consolidated (SIP) feed**: the official close at 16:00 ET, retrieved after 17:30 ET; feed, bar timestamp and retrieval time stored.
  - DTB3 for cash.
  - The event store for releases.
  - NYSE calendar from `src/clock.py`.
- **Missing or stale data:** a day with a missing, stale or revised close is recorded with its flag and **excluded by rule, never by outcome**. If more than 10% of days are excluded in any quarter, the rule pauses and you are told.
- **No peeking:** before the analysis threshold, the digest and STATUS.md show **counts only** (events recorded, days excluded), never returns or ratios.
- **Revisions:** any change to definitions after freezing is an appended amendment with its own hash. Counting restarts unless the amendment is purely clerical.

## 1. GF2: release-day variance of gold (a risk claim)

- **Question:** is GLD's daily return variance higher on top-tier US release days than on other days? This is a risk claim with no direction. It would justify blackout or position-size rules, not trades.
- **Mechanism:** scheduled macro news is priced on release (Andersen, Bollerslev, Diebold & Vega 2003, as cited in `reports/signal_research_recommendation_2026-10-31.md:32`).
- **Event days**, fixed in advance:
  - an NYSE trading day *t* is an **event day** if the event store, **as of 18:00 ET on day t−1**, lists a scheduled release on day *t* from: BLS CPI, BLS Employment Situation, FOMC statement, BEA Personal Income and Outlays;
  - a release published but not listed by that cut-off still counts, and is flagged "late-listed";
  - a release listed but not published on the day is flagged and excluded.
- **Comparison days:** every other NYSE trading day, **excluding** the trading day after an event day (spillover) and days after market closures of more than 1 day.
- **Measure:** r_t = ln(GLD close_t / GLD close_{t−1}), from consecutive trading days only. VR = mean(r² on event days) ÷ mean(r² on comparison days).
- **Expected frequency:** about 40–45 event days a year (12 CPI + 12 jobs + 8 FOMC + 12 PCE, less overlaps) [estimate].
- **Analysis threshold:** the first analysis when **100 event days** are recorded (about 2.3 years) [estimate]. Then annually.
- **Inference:** log VR with a 95% interval from a weekly block bootstrap (10,000 resamples, seed fixed at freeze).
- **Conclusions:**
  - **"supported"** if the interval's lower bound > 1;
  - **"not supported"** if the upper bound < 1.5 (the pre-stated effect of interest);
  - otherwise **"inconclusive"**.

  Reported each time with n, exclusions and the late-listed count.
- **Power** (estimate): at VR = 1.5 and normal returns, about 80% at 100 event days and 400 comparison days. Heavy tails could double the sample needed.
- **What it cannot show:** direction, tradability, or anything about intraday timing (daily closes only).

## 2. GF1: gold in joint deleveraging shocks (record only)

- **Question, for a much later test:** after a day on which gold and US stocks both fall sharply, does gold partly reverse over the next 5 trading days?
- **Mechanism:** margin-driven selling of liquid assets in funding stress overshoots (Brunnermeier, Nagel & Pedersen 2008, library FX002 at L2 for FX). Its application to gold is **[OV]**.
- **Trigger** on a completed NYSE trading day t: r_GLD,t ≤ −1.5 × σ60(GLD) **and** r_SPY,t ≤ −1.5 × σ60(SPY).
  - σ60 is the standard deviation of the 60 daily log returns ending at t−1, so it is known before t.
  - Both bars come from the same feed (SIP).
- **What is recorded, per trigger:**
  - the date and both z-scores;
  - flags: FOMC/release day, MoF intervention day, data flags;
  - the GLD log returns from close t to closes t+1 and t+5, each recorded once it completes;
  - overlapping triggers (within 5 days of an earlier one), linked to the first.
- **Baseline recorded alongside:** the unconditional mean and standard deviation of 5-day GLD returns over the same observation period, appended monthly.
- **Record-only rule:** no statistic, ratio or chart of trigger outcomes is computed or shown until **30 independent triggers** are recorded (about 6–7 years at about 4–5 a year [estimate]). At that point you decide whether to pre-register a test. The rule produces no verdict on its own.
- **Why so long:** d = 0.3 needs about 69 events (about 15 years); d = 0.5 needs about 25. This is a decade-scale record.

## 3. Implementation plan (for after approval; nothing built now)

- **Registry:**
  - a new record kind `observation` (append-only, in the hash chain);
  - idempotency keys `gf2:<date>` and `gf1:<date>`;
  - written by the evening pass after the GLD/SPY daily bars are confirmed.
- **No new alerts:** one digest line with counts only.
- **Built in a worktree, with tests:**
  - event-day classification uses the t−1 cut-off;
  - no-peek: no outcome statistics before the threshold;
  - exclusion flags;
  - idempotence.
- **Merged between scheduled runs, with the next scan confirmed clean.** This follows the existing build rules.

## 4. Frozen choices

- GF2 event list: BLS CPI, BLS Employment Situation, FOMC statement, BEA Personal Income and Outlays (as drafted; no additions).
- Thresholds: GF2 first analysis at 100 event days; GF1 first look at 30 independent triggers.
- Any change after this freeze is an appended amendment with its own hash.
