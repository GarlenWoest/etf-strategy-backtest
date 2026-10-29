# USD/JPY forward (shadow) test: pre-registration

**Status: DRAFT, awaiting the owner's approval. Not frozen. No shadow run happens before approval.**

On approval, three things happen before the first shadow evaluation:
- this file is committed unchanged;
- its SHA-256 is written to the research memory (kind `preregistration`) and to the forward registry;
- the rule parameters are copied into `config.yaml live_usdjpy` with a test asserting they match this file.

Any later change is a new version with a new forward-trial ID.

**EXPERIMENTAL SHADOW SIGNALS. Not validated. Not financial advice. No orders, no broker, internal simulator only.**

## 1. What this test is, and is not

- **It is** a prospective, forward-only measurement of two frozen rules on USD/JPY, recorded in the immutable registry (`src/live_usdjpy/registry.py`) before outcomes exist, and scored against fixed baselines.
- **It is not** a historical study. It reads no file under `data/`, adds nothing to `research_log.csv`, and leaves the **historical cumulative N = 142** unchanged. The research pause on new historical strategies stays in force.
- **It has its own trial count:** forward N = 2 (F001, F002). A new rule or version gets a new F-ID and raises forward N. Forward results are never pooled with historical trials.
- **Rules were written before seeing any data:** in `research/USDJPY_CANDIDATES_v0.1.md` (10-28), from economic reasoning and round numbers. v0.2 below changes rationale, exclusions and baselines only, not the trading parameters, which no data was used to set.

**Data governance (needs your explicit approval, item D1 in section 9):**
- The rules need trailing windows of current data: a 60-day volatility, and a 12-month return.
- These windows reach back into 2025, which lies inside the calendar period of the locked 2024+ research holdout.
- The forward system fetches them from the monitoring source (Yahoo daily bars, as `market_intel` already does) only to compute that day's signal. It stores them only under `live/`, and never uses them for any historical evaluation, fitting or rule selection.
- The holdout's research datasets are never downloaded or opened.

## 2. Frozen rules (v0.2)

**Common to both rules**

- **Instrument and data.**
  - Instrument: USD/JPY spot, priced from Yahoo `JPY=X`. These are **indicative prices, not executable**, and every result is labelled "indicative-price simulation".
  - Daily bars: completed daily bars only.
  - σ60: the standard deviation of the last 60 completed daily log returns, excluding the decision day.
- **Decision times.** Rules are evaluated at scheduled scans on completed daily bars, never on a partial bar.
- **Entry.** The first scan after the signal at which the eligibility and risk gates pass and the USD/JPY price is LIVE (≤ 180 s old).
  - Fill price = snapshot price × (1 ± c), where c is the one-way cost of the scenario (section 4).
- **Exits are checked at scans, not intraday:**
  - a breached level exits at the next scan's price, never at the level;
  - weekend gaps are taken as they come.

  This is a **daily-close / next-scan exit condition**. It is not a broker stop order and it guarantees nothing.
- **Size.** Notional = min(0.5 × equity, 0.5% of equity ÷ distance to invalidation).
  - Each rule runs a $10,000 virtual sub-ledger at ≤ 1.00x (FX engine v2 accounting), reported also per $100.
- **Risk limits.** As approved 10-29; enforced by the gate (step 4).

### F001: RO-REV v0.2, deleveraging-overshoot reversal

- **Economic rationale (corrected).**
  - Carry positions funded in yen are unwound abruptly when funding liquidity and risk appetite fall. The yen jumps, and the move can overshoot what fundamentals justify (Brunnermeier, Nagel & Pedersen 2008, **FX002 [L2]**).
  - Leveraged unwinds "amplified the initial reaction" in August 2024, and "markets then stabilised quickly" (BIS Bulletin 90, Aquilina et al. 2024; **read at summary-page level only [L1]**). That episode lies inside the locked holdout: it is cited as mechanism only, never as data.
  - The 10-28 draft's main citation (Ranaldo & Söderlind, **FX010 [L2]**) documents mostly **same-time** co-movement. Its lagged JPY/USD S&P coefficient is insignificant (t 1.26). It is kept only as weak, contemporaneous context.
  - **Contradicting:** crashes cluster, and an unwind can run for days (FX002; October 7–8, 1998). The USD's own safe-haven behaviour changed in 2025 (ECB June 2026 box, provisional: not yet read by this project). Expect a low prior.
- **Trigger.** On the last completed day *t*, USD/JPY log return ≤ −2.0 × σ60(USD/JPY) **and** SPY log return ≤ −2.0 × σ60(SPY).
- **Excluded triggers (recorded as NO TRADE with the reason):**
  - day *t* had a scheduled FOMC or BoJ policy decision (news-driven moves, not liquidity);
  - day *t* is a Japanese or US bank holiday (conservative temporary guard: thin liquidity, as on 3 Jan 2019).
  - If an MoF release published later shows yen intervention on day *t* or inside the holding window, the signal is **flagged and reported separately, never deleted**.
- **Direction and levels.** Long USD/JPY.
  - Invalidation: entry × (1 − 1.0 × \|r_t\|).
  - Target: entry × (1 + 0.5 × \|r_t\|).
  - Expiry: 2 FX trading days after entry.

### F002: TSM12 v0.2, 12-month time-series momentum (a LOW-PRIOR CONTROL, not a candidate edge)

- **Rationale and its limits.**
  - Time-series momentum is documented for **diversified multi-market portfolios** (Moskowitz, Ooi & Pedersen 2012, S01 [L0]; Hurst, Ooi & Pedersen 2017, S02 [L0], whose average single-market gross Sharpe is about 0.4).
  - Single-asset evidence is weak, and a historical-sample-mean strategy matches it (Huang et al. 2020, S04 [L0]).
  - Part of the published alpha is volatility scaling (Kim, Tse & Wald 2016, C110 [L0]).
  - FX technical-rule profits decayed by the early 1990s (Neely, Weller & Ulrich, FX007 [L1]).
  - It is kept as a **control**: a transparent, well-known rule against which the plumbing and baselines can be checked.
- **Trigger.** At the close of the last FX trading day of each month (market clock):
  - 12-month log return > +2% → long;
  - < −2% → short;
  - otherwise no position.
- **Levels.**
  - Catastrophe stop: entry ∓ 3 × σ60 × √21.
  - Target: none.
  - Expiry: the next month-end evaluation. An unchanged sign is recorded as a **new** signal, not a silent roll.

## 3. Baselines (fixed now; each over the same windows and at the same size)

| Baseline | Definition |
|---|---|
| Cash | No position: return 0 (financing 0) |
| No-change | Forecasts zero price change; used for the error metrics (its error = the realised move) |
| Always long | Long USD/JPY over each signal's window, with costs and financing |
| Historical sample mean | Position sign = sign of the mean monthly USD/JPY log return over 1991-01 to 2023-12 (Fed H.10, already in `data/`), **frozen at approval**. Computing this one constant reads research data, so it needs approval (item D2). It is the Huang et al. null, made look-ahead-free |
| Simple trend | Sign of (price − its 20-day average of completed closes) at entry, held over the same window |
| Placebo (F001 only) | The same entry, levels and expiry on 10 randomly chosen eligible non-trigger days per signal (fixed seed 20261029), to separate the rule from "any day" |

## 4. Costs and financing (two scenarios, both always reported)

| | Base | Stress |
|---|---|---|
| One-way trading cost c | 0.015% of notional (unverified assumption) | 0.030% (2x) |
| Financing per night (5 p.m. ET roll; triple on Wednesday) | Long USD/JPY: + (r_USD − r_JPY) − 1.00%/yr. Short: − (r_USD − r_JPY) − 1.00%/yr. The 1.00%/yr admin fee is OANDA US's stated fee for this pair; tom-next is proxied by the rate differential | Admin fee 1.50%/yr |
| Rate inputs | US: 3-month T-bill (FRED DTB3). Japan: overnight call rate (BoJ Time-Series API or FRED mirror) | Same |

- **Labelling:** financing is labelled **"estimated, unverified"** until venue swap data exists.
- **Missing rates:** a missing rate input uses the last known value, flagged STALE. Results are then reported with and without financing.

## 5. Metrics

**Per rule and scenario:**
- net return per signal;
- sub-ledger equity curve, annualised Sharpe, maximum drawdown;
- hit rate, average win and loss (trade-level, never return-period win rates);
- exposure, turnover, costs paid, financing paid;
- directional accuracy and error against no-change.

**Not measured:** calibration is **UNKNOWN**, because neither rule produces probabilities.

**Breakdowns (descriptive only, never used to change a rule):** by session at entry, by volatility regime (σ60 tercile at entry), and with or without a scheduled event inside the window.

**Every report carries a power banner:** "n = …; fewer than 30 resolved signals: nothing here is statistically meaningful", plus the power table below.

## 6. Power (written estimates, 2026-10-29; analytic, no data used)

**Assumptions:**
- normal approximation;
- one-sided test, α = 5%, 80% power;
- per-signal effect d = mean net return ÷ its standard deviation.

| | F001 RO-REV | F002 TSM12 |
|---|---|---|
| Signal frequency | About 0.3–4 per year. A joint −2σ day has probability 0.14–0.55% under a bivariate normal with correlation 0.2–0.6 (0.35–1.4 a year), times 1–3 for fat tails. **An empirical count from pre-2024 data was not run** (item D3) | 12 decisions a year (some flat) |
| Signals needed for 80% power | d = 0.3: 69; d = 0.2: 155; d = 0.1: 618 | At an annual Sharpe of 0.4: 464 months (≈ 39 years); at 0.6: 206 months (≈ 17 years) |
| Power at realistic horizons | d = 0.3: 24% at n = 10, 50% at n = 30 | At Sharpe 0.4: 17% at 3 years, 23% at 5 years, 35% at 10 years |

**Conclusion:**
- **Neither rule can be validated by this forward test within a decade.** Its realistic value is:
  - proving that the pipeline, costs, gates, registry and scoring work;
  - detecting clear harm early (futility);
  - building an uneditable record.
- **No result from it may be presented as evidence of an edge** unless the success criteria in section 7 are met.

## 7. Success, failure and stopping rules

**Minimum sample:**
- **No performance claim** for a rule before **30 resolved signals**.
- **Formal evaluation:** F001 at 69 resolved signals; F002 at 120 resolved months; or at 2036-10-31, whichever comes first.
- **Review checkpoints:** descriptive reports at each 12-month anniversary.

**Success.** All must hold at formal evaluation, under base costs, with Holm correction across forward N:
1. Mean net return per signal > 0, one-sided p < 0.05.
2. Paired difference against **each** baseline (cash, always long, historical sample mean, simple trend; plus placebo for F001) > 0, p < 0.05.
3. Mean net return still > 0 under stress costs.
4. Not driven by one episode: mean > 0 after removing the best 10% of signals.
5. No unresolved registry, reconciliation or integrity failure during the test.

**Meeting all five makes a rule eligible to be *considered* as a VALIDATED RESEARCH CANDIDATE.** That status still needs your separate decision, and nothing advances automatically.

**Failure (the rule stops and is recorded FAILED; failed rules stay failed):**
- **Futility,** at any 12-month review with ≥ 30 resolved signals: the one-sided 95% upper bound of mean net return (base costs) < 0.
- **Not met** at formal evaluation.

**Experiment stop (pending your decision; not counted as a performance verdict):**
- a sub-ledger drawdown of −5%;
- the kill switch;
- an integrity failure that can't be reconciled.

**Forbidden:**
- changing parameters, baselines or criteria after the first shadow run;
- excluding signals after the fact (they can only be flagged);
- restarting a rule's count;
- tuning on forward results.

## 8. What would invalidate the rationale (beyond the statistics)

- **F001:** no tendency for USD/JPY to recover after joint risk-off days, in placebo-controlled forward data; or most triggers turn out to coincide with interventions or policy decisions.
- **F002:** performance indistinguishable from the historical-sample-mean or always-long baselines, as Huang et al. found for single assets.

## 9. Decisions this pre-registration needs from you

| ID | Decision | My recommendation |
|---|---|---|
| D1 | Approve the data governance in section 1 (current trailing windows reaching into 2025, monitoring side only) | Approve; it's required for any live signal |
| D2 | Allow computing the one historical-sample-mean constant from 1991–2023 H.10 data already in `data/` | Approve; it's a single descriptive constant, not a strategy test |
| D3 | Allow an empirical count of RO-REV trigger days in 1991–2023 (frequency only; no returns examined) to replace the analytic range in section 6 | Optional; if declined, the analytic range stands |
| D4 | Approve both rules, or keep only F002 as the plumbing control and drop F001, which may produce almost no signals | Keep both: F001 costs nothing when silent, and NO TRADE records are also data |
| D5 | Approve the minimum samples, success, failure and stop rules above | Approve |
