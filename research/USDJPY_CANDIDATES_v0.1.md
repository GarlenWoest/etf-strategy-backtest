# USD/JPY candidate rules v0.1 and paper risk limits (draft, 2026-10-28)

**EXPERIMENTAL SHADOW SIGNALS. Not financial advice. Not validated. Not pre-registered trials.**

These are drafts for a forward-only shadow workflow (`research/USDJPY_PIPELINE_DESIGN.md`).
- **Not tested:** no historical data was read to write them, and none of them has been backtested.
- **No change to the trial count:** they don't change the cumulative N of 142. If one ever deserves a historical test, it must be pre-registered first and counted in N.
- **The default output every day is NO TRADE.**
- **Parameters:** every one below is chosen from economic reasoning or round numbers, not fitted. All would be frozen in `config.yaml` before first use.

Notation:
- σ60 = standard deviation of daily log returns over the 60 completed days before the decision day.
- Prices are Yahoo indicative daily closes and snapshot last prices (`JPY=X`, `SPY`), as the market snapshot already records them.
- "Equity" is the $10,000 virtual USD/JPY ledger at ≤ 1x (`config.yaml specialists.ledgers.usdjpy`), also reported per $100.

## Candidate A: RO-REV v0.1, risk-off overshoot reversal

**Economic motivation.** In risk-off episodes the yen jumps as carry positions are unwound and safe-haven demand arrives. With slow-moving, funding-constrained capital, that move can overshoot and partly reverse over the next day.

| Field | Rule |
|---|---|
| Trigger | On the last completed day *t*, both: USD/JPY return ≤ −2.0 × σ60(USD/JPY), **and** SPY return ≤ −2.0 × σ60(SPY). Skipped if day *t* contained a scheduled FOMC or BoJ decision (a news-driven move, not a liquidity overshoot) |
| Entry | Long USD/JPY at the first fresh snapshot price (LIVE) in the next weekday run after the trigger is detected |
| Invalidation | Entry × (1 − 1.0 × \|r_t\|): the move continues by as much again |
| Target | Entry × (1 + 0.5 × \|r_t\|): half the trigger move reverses |
| Expiry | Exit at the weekday run 2 FX trading days after entry if neither level was touched |
| Size | Notional = min(0.5 × equity, 0.5% of equity ÷ invalidation distance), so a full loss at the level is ≤ 0.5% of equity before gaps and costs |
| Supports | **FX010** Ranaldo & Söderlind [L2]: safe-haven effects "appear to be partly reversed after a day", and the reversal of the FX-volatility effect is "almost complete" (1993–2006). JPY/USD's lagged FX-volatility coefficient has t 2.17. **FX002** Brunnermeier et al. [L2]: funding-liquidity unwinds as the mechanism |
| Contradicts | **FX002** [L2]: crash risk clusters, and unwinds can last days (October 7–8, 1998: about 12% in two days). **FX010** [L2]: the JPY/USD lagged S&P coefficient isn't significant (t 1.26), and the sample ends in 2006. Our study: **V139/V140** (carry with a risk-off filter) were killed, but that's a different rule (it stayed out in risk-off; this buys after a shock). Never tested by us |
| Known weaknesses | The daily run enters part-way into day *t*+1, so some of the measured next-day reversal may be missed. Yahoo FX daily-bar boundaries aren't verified against the NYSE close. Joint 2σ days are rare (a few a year), so 30 resolved signals could take many years |

## Candidate B: TSM12 v0.1, 12-month time-series momentum

**Economic motivation.** Prices under-react to slowly diffusing information, including monetary-policy changes, so 12-month trends tend to persist for a while.

| Field | Rule |
|---|---|
| Trigger | At the close of the last FX trading day of each month (market clock): 12-month log return of USD/JPY > +2% → long; < −2% → short; otherwise no position (a dead band against flipping on noise) |
| Entry | First fresh snapshot price (LIVE) in the next weekday run |
| Invalidation | Signal level: a sign flip at the next month-end. Price level: a catastrophe stop at entry ∓ 3 × σ60 × √21 (three monthly standard deviations) |
| Target | None: time-based exit only |
| Expiry | Next month-end evaluation. If the sign is unchanged, a new signal is recorded (no silent roll) |
| Size | Notional = min(0.5 × equity, 0.5% of equity ÷ stop distance). At 5% annual volatility that is about 0.11x |
| Supports | **S01** Moskowitz, Ooi & Pedersen (2012) [L0] and **S02** Hurst, Ooi & Pedersen (2017) [L0]: time-series momentum across many futures markets, currencies included. **FX003** [L2]: delayed reaction to monetary policy (the authors' interpretation, panel level) |
| Contradicts | **FX007** Neely, Weller & Ulrich [L1]: FX moving-average and filter-rule profits "had disappeared by the early 1990s". **FX008** [L1]: currency momentum is a cross-sectional, many-currency effect. **S04** "Time series momentum: Is it there?" [L0]. Our Study 3: of 12 single-asset momentum trials, only stocks at 12 months passed the era rule, and none was validated. **The supporting evidence is multi-market, and the single-pair evidence is weak** |
| Known weaknesses | About 12 signals a year, so 30 resolved signals take about 2.5 years. The supporting sources are L0 (not yet verified) |

## Ideas considered and rejected for v0.1

| Idea | Why not |
|---|---|
| Carry level; carry with a risk-off filter; rate-differential momentum; relative curve slope | Already tested and killed (V135–V142). Failed trials stay failed; relabelling them as shadow signals isn't allowed |
| Inflation-differential predictor | FX003 [L2]: no significant effect for JPY in any sample, and positive in 2007–2020 |
| Fading MoF interventions | Too few episodes observable in real time (config `usdjpy_study1` rejection); interventions are published with a lag |
| London 4 p.m. fix drift (FX025 [L1]) | Needs minute-level, timestamp-verified quotes; HistData intraday use is blocked, and the daily scheduler can't act at 16:00 London |
| Trading announcement surprises (FX022 [L2]) | Needs licensed consensus forecasts, which we don't have |

## Paper risk limits (proposed, for the shadow paper ledger)

| Limit | Proposed value | One-line justification |
|---|---|---|
| Max loss per trade | 0.5% of equity at the invalidation level (enforced through sizing) | Twenty losses in a row would cost about 10%, survivable for a learning experiment; gap losses beyond it are recorded, not hidden |
| Max gross exposure | 1.00x, hard (engine v2: a close above 1.00x is trimmed back to 0.95x) | The project's existing hard limit; no exception |
| Per-rule exposure | 0.5x | Both rules at full size still can't breach 1x |
| Net exposure | ≤ 1.00x of the combined book; each rule also scored on its own sub-ledger | One pair, so opposite rules net out; separate sub-ledgers keep each rule's record clean |
| Concurrent positions | 1 per rule, 2 in total | More positions in the same pair would be correlated duplicates, not diversification |
| Daily loss | −1.0% of equity at the run's mark → no new entries until the next run | At these sizes that's several daily standard deviations, so it fires only on gaps or errors |
| Max drawdown | −3% from peak: halt new entries and review; −5%: close everything and stop pending your decision | Six full per-trade losses in a row trigger a review before damage compounds |
| Stale data | No entry unless the USD/JPY price is LIVE (≤ 180 s) or DELAYED (≤ 20 min), daily bars are CURRENT and the specialist status is DATA OK; a stale mark is flagged | Uses the existing freshness rules; an entry price we can't timestamp isn't an entry |
| Event blackout | No entry within 60 min before to 30 min after US 08:30 ET releases (jobs report, CPI, GDP/PCE) or the FOMC statement and press conference. No entry on a BoJ statement date (time unpublished). No entry for 5 trading days after a published MoF intervention covering the period | FX022: prices jump within minutes of releases, and a once-a-day run can't see those minutes; BoJ times are unknown in advance |
| Weekend | No new entries in Friday runs; triple rollover on Wednesday accounted for | A daily run can't manage a weekend gap; financing must be counted correctly |
| Integrity kill switch | A registry chain break, an engine-parity mismatch above $0.01 per $10,000, or a heartbeat gap above 3 trading days → no new entries until reviewed | A record we can't trust shouldn't produce new positions |
| Cost sanity | Once an executable quote source exists: block entries if the measured spread exceeds 2× the assumed 0.015% one-way cost | The cost assumption is unverified and must not quietly drift |

**Not decided here:**
- whether these limits apply to the discretionary trade-ideas plan (it uses a $100 account and up to 25% size, which is a different scale);
- the exact US release list for the blackout.

Both are for your review tomorrow.
