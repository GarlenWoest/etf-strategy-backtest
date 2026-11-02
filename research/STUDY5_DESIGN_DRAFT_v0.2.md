# Study 5: design draft v0.2 (NOT pre-registered; for the owner's review)

_Draft 2026-11-02. It supersedes v0.1 (`research/STUDY5_DESIGN_DRAFT.md`, kept unchanged, commit c920b1c) and applies the owner decisions of 2026-11-02:_
- _R2: the statistics policy draft;_
- _R3: GBP/USD on the approved scheme;_
- _R4: option P;_
- _R8: DEXUSUK and Ken French daily downloaded._

_It fixes the 7 errors found in the research review (`reports/research_review/RESEARCH_REVIEW_2026-11-02.md` §5.1). **Document only:** no returns were computed and no trial ID was assigned. Historical N stays 142, forward N stays 2, the holdout stays locked, and the research pause continues until you approve a frozen version._

## 0. Corrections to v0.1

| # | v0.1 said | v0.2 says |
|---|---|---|
| C1 | DEXUSUK "Already validated" (v0.1 `:48`) | **Downloaded 2026-11-02, not yet validated** (`research/DATA_REGISTER.csv`). Validation as for DEXJPUS (duplicates, gaps, stale runs, H.10 calendar) is the first step after approval |
| C2 | Ken French daily "OK, already used" (v0.1 `:52`, `:60`) | Only monthly was held. **Daily factors downloaded 2026-11-02** (1926-07-01..2023-12-29; 689 rows from 2024 onward discarded unread) |
| C3 | GBP/USD "1971–2023 untouched" (v0.1 `:61`) | GBP/USD uses the **approved scheme only:** in-sample 1990–2014, validation 2015–2023, 2024+ locked (R3). The data are untouched by this project, but GBP is inside published carry/momentum samples (`research/library/knowledge.csv:6,9`) |
| C4 | H5-A on USD/JPY 1986–1989 | **Dropped.** The carry family is burned for USD/JPY (`research/memory/research.jsonl` lines 24–29), and 4 years is too short |
| C5 | H5-C on USD/JPY 1971–1989 | **Dropped from the historical study.** The mechanism needs free capital flows (Japan liberalised around December 1980 [OV]). A gold analogue is drafted as a forward record-only rule (GF1) |
| C6 | H5-B gold on monthly averages | **Dropped** (smoothing, correlation 0.58, biases tail measures) |
| C7 | K-rules "adapted from K1–K7" | Fixed definitions in §5: K3 on excess return; K6 only if in-sample Sharpe > 0; K4 on true direction changes; symmetric re-sizing; robustness checks are kill rules |

## 1. Scope: option P (3 trials, N 142 → 145)

| Trial | Hypothesis | Market | Windows | Status |
|---|---|---|---|---|
| T1 | H5-B volatility-target risk overlay | GBP/USD | IS 1990–2014, val 2015–2023 | Ready, subject to validating DEXUSUK |
| T2 | H5-B volatility-target risk overlay | USD/JPY | **Needs a choice:** (a) 1974–1989 confirmation window under amendment A1 (`research/FX_PERIOD_AMENDMENT_A1_DRAFT.md`), or (b) IS 1990–2014 / val 2015–2023, already used by Study 4 for *other* hypotheses (carry, differential momentum, risk-off filter, curve slope), never for volatility targeting | Decision R4a |
| T3 | G1 month-end equity-hedge flow | GBP/USD | IS 1990–2014, val 2015–2023 | **Candidate only:** see §3 (decay) and §6 (power). It may be replaced or dropped |

**On T2, option (b):** it needs no amendment, but the data have been seen in aggregate (Study 4's benchmarks and stress windows), so it is weaker confirmation. Option (a) is cleaner data under a new rule. **My recommendation is (b)**, because it keeps the approved scheme intact. The cost is disclosing that the data were seen in aggregate.

## 2. Hypotheses and rules (fixed numbers, not fitted)

**T1/T2, H5-B (unchanged from v0.1 `:24-29`):**
- **Mechanism:** volatility clusters, so scaling exposure down when recent volatility is high should cut the left tail (Harvey et al. 2018; library S25).
- **Rule:**
  - base position fixed once, in the sign of the pair's in-sample mean (as D2);
  - exposure x = min(1, 10% ÷ σ60), where σ60 is the annualised volatility of the last 60 daily log returns;
  - rebalanced at month-end, executed the next FX day.
- **Success** is a risk claim: worst drawdown **and** 1% CVaR at least 25% lower than the unscaled base, with Sharpe not significantly lower (paired block bootstrap, 5%).

**T3, G1 (from the research review §3.2):**
- **Rule:**
  - on the second-to-last US business day of each month, R = US market month-to-date total return through the previous close, from Ken French daily (Mkt-RF + RF);
  - if R ≥ +2%, buy GBP/USD at that day's H.10 noon rate; if R ≤ −2%, sell;
  - exit at the next day's noon rate, after the 11:00 NY London fix.
- **Placebo:** the same rule on the 10th US business day of each month.

**Financing and carry (open; decision R8b):**
- The UK and Japan short rates are not held.
- **Proposed:** spot-only returns plus the USD T-bill on cash, with carry excluded and disclosed. For T1/T2 the claim is about risk; for T3 the holding is one day, so carry is at most one day's interest.
- The alternative is to approve a download of the OECD immediate rates (IRSTCI01GBM156N; IRSTCI01JPM156N, which starts around 1985 [OV]).

## 3. G1: post-publication decay of the month-end FX effect

_Added at your request before G1 enters the protocol. Every citation is **[OV]**: none of these papers is in the project library or has been read here. Titles, venues and findings are from memory and must be checked (R12) before freezing._

### 3.1 Original evidence

- **Melvin & Prins (2015), "Equity hedging and exchange rates at the London 4 p.m. fix"** [OV: journal and volume]. They report that month-end exchange-rate moves around the WM/Reuters 4 p.m. fix are related to month-to-date relative equity performance, consistent with foreign investors rebalancing currency hedges on equity holdings. This is the mechanism G1 encodes.
- **Evans (2018), "Forex trading and the WMR Fix"**, *Journal of Banking & Finance* [OV]. He documents a distinctive price behaviour and elevated volatility around the fix, including month-end. Relevant as the market-microstructure context.
- **Krohn, Mueller & Whelan (2024), "Foreign Exchange Fixings and Returns Around the Clock"**, *Journal of Finance* [OV]. They report systematic USD movements around the major fixes (appreciation before, reversal after). Relevant both as support for fix-related flows and as evidence that a predictable pattern was still visible in recent data [OV: sample period and month-end detail].

### 3.2 Reasons to expect decay

- **Publication and arbitrage.** McLean & Pontiff (2016, *Journal of Finance*), "Does Academic Research Destroy Stock Return Predictability?" [OV] found anomaly returns markedly lower out of sample and lower again after publication: roughly a third lower out of sample and over half lower post-publication [OV: exact figures]. There is no equivalent FX study in the library, so assume the same direction for FX.
- **Fix reform.** After the FX benchmark-manipulation investigations (2013–2015; fines from late 2014 [OV]), the Financial Stability Board's 2014 report on FX benchmarks led to widening the WM/Reuters fix window from 1 to 5 minutes, effective around February 2015 [OV]. Dealer handling of fix orders also changed. Both could spread or weaken a fix-concentrated flow.
- **Practitioner awareness.** Month-end rebalancing flows are a widely published sell-side topic [OV]. Anticipatory trading would move the effect earlier (before the second-to-last day) or erase it.
- **Mechanism growth (pulling the other way).** Hedged foreign holdings of US equities grew over 1990–2023 [OV], so the flow's *size* may have grown even if its predictability fell.

### 3.3 What this means for G1 under the approved windows

| Item | In-sample 1990–2014 | Validation 2015–2023 |
|---|---|---|
| Publication status | Mostly pre-publication (Melvin & Prins appeared 2015 [OV]) | **Entirely post-publication** |
| Fix regime | 1-minute window (pre-reform) | **5-minute window (post-reform)** [OV] |
| Expected effect (prior) | d₀ (unknown) | About 0.5 × d₀ or less (McLean–Pontiff direction) |
| Events (estimate; R7 count pending) | About 160 (25 years × about 6.5) | About 58 (9 years × about 6.5) |
| d needed for 80% power | About 0.20 | **About 0.33** |

**Implications:**
- The validation window is the post-publication, post-reform period. Decay therefore works directly against G1's only decisive test.
- Even with no decay, 58 events need a per-event Sharpe of about 0.33. Round-trip costs at the frozen assumption (0.03%) take about 0.05 of a daily standard deviation [estimate], and a d of about 0.33 is a large effect for any FX timing rule.

**Pre-registration conditions, if G1 stays:**
- (a) State the in-sample vs validation decay expectation in advance, and report the pre/post-2015 ratio, without making it a pass condition.
- (b) Run the R7 frequency count first. **Drop G1 if the validation window has fewer than 50 events** (L1).
- (c) Register "inconclusive" as the expected outcome if power is below 0.5 at d = 0.2.

**Recommendation:** keep G1 only if R12's reading confirms a documented month-end GBP/USD (or USD-wide) effect *after* 2015. Otherwise drop T3 and run Study 5 with 2 trials (N = 144).

## 4. Data (all pre-2024; register: `research/DATA_REGISTER.csv`)

| Series | Held | Use | Status |
|---|---|---|---|
| DEXUSUK (H.10 noon, USD per GBP) | `data/raw/r8_fred_dexusuk/` (1971-01-04..2023-12-29) | T1, T3 | Not validated; licence line unverified [OV] |
| DEXJPUS | `data/raw/usdjpy/` (1971-01-04..2023-12-29) | T2 | Validated for 1990+ only |
| Ken French daily 3 factors | `data/raw/r8_kenfrench_daily/` (1926-07-01..2023-12-29) | T3 | Copyright Fama & French; no explicit licence text [OV for redistribution]; local use only |
| DTB3 | `data/raw/usdjpy/` (1954-01-04..) | Cash rate | Validated |
| UK and Japan short rates | Not held | Carry (optional) | R8b |

## 5. Kill criteria (fixed definitions)

- **K1 (T3):** beats flat and the placebo in validation. For T1/T2, the risk criterion in §2 replaces K1.
- **K2 (statistics policy, draft):** DSR ≥ 0.95 at full cumulative N with the pooled variance (`research/STATS_POLICY_DRAFT.md`). The family-wise test is secondary.
- **K3:** mean **excess** return (or, for T1/T2, the risk criterion) still holds at 2x and 3x costs.
- **K4:** at least 30 true direction changes or events in validation, or the trial is reported "underpowered" and cannot pass.
- **K5:** pre-set neighbours (T1/T2 target 12%; T3 thresholds ±1.5% and ±3%) must not reverse the sign of the effect.
- **K6:** validation at least half of in-sample, **only if the in-sample statistic > 0**; "n/a" for T2 under amendment A1.
- **K7:** no fall to 20% of capital in any stress window.
- **Robustness as kill rules:** a 1-day extra lag (T1/T2: rebalance one day later) must not reverse the effect.

## 6. Power (estimates; nothing computed on data)

- **T1/T2:** a risk claim, judged on effect size with bootstrap intervals; precision is limited by about 6–10 stress episodes per window (v0.1 `:83`).
- **T3:** see §3.3. Power is below about 0.3 at d = 0.2 in validation [estimate].

## 7. Open decisions

- **R4a:** T2 window, (a) amendment A1 or (b) the approved scheme. Recommendation: (b).
- **R8b:** spot-only vs downloading UK/Japan short rates. Recommendation: spot-only, disclosed.
- **R7:** a frequency-only count of G1 events (pre-2024, no returns).
- **R12:** read the §3 papers before freezing.
- **Statistics policy Q1:** raw vs length-standardized pooled variance.
- **Final scope:** 3 trials (N = 145) or 2 (N = 144), if G1 is dropped.
