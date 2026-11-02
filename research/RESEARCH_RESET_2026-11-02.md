# Research reset, 2026-11-02 (documents only; no trials run in this step)

## 1. Statistics policy v1.1

See `research/STATS_POLICY_v1.1_DRAFT.md` (draft; hurdle table for 9, 20 and 34 years).

## 2. Study 5 supplementary analysis (POST-HOC, labelled; cannot change verdicts)

- **Question:** does volatility targeting (T1/T2) reduce risk *beyond what a lower average exposure does on its own*?
- **Method** (computed **after** the frozen Study 5 run, from its own outputs):
  - For T1 and T2, take the scaled strategy's **average absolute weight** over the validation window, w̄.
  - Build a **constant-exposure benchmark**: the base sign × w̄, held every day, rebalanced monthly with the same costs, cash and spot-only treatment.
  - Report realized volatility, maximum drawdown and worst calendar month for scaled vs constant-w̄ and constant-w̄ vs unscaled, with the same bootstrap intervals as R-1.
- **Labelling:** every figure is marked "POST-HOC SUPPLEMENTARY (not pre-registered; cannot change the V143/V144 verdicts)" in the report and research memory.
- **Timing:** after the Study 5 run, which runs only if today's 16:45 and 17:02 checks pass.

## 3. Measured-cost study (no trials added)

- **Purpose:** compare the frozen cost assumptions (FX 0.015% one-way; ETF costs from Study 1) with costs measured going forward.
- **What is recorded:**
  - **USD/JPY and GBP/USD:** OANDA bid/ask at the **17:00 ET decision times**. The 17:02 scan already stores quotes in `market_state`, so this needs only a tag on the decision-time scan and a weekly aggregation.
  - **ETF universe** (SPY, QQQ, TLT, GLD, SLV, USO and the 2x/3x funds): **SIP NBBO spreads near the open (09:30–09:35) and the close (15:55–16:00)**, fetched once each evening from Alpaca's historical quotes endpoint for the day. This needs a **new allow-listed read-only GET** (`/v2/stocks/quotes`, multi-symbol), plus a test that order endpoints stay blocked.
- **Report after 4 weeks** (target 2026-12-04, about 20 trading days): median and 90th-percentile half-spread per instrument and session, in % of price, against the frozen one-way cost. Descriptive only; the frozen costs are never replaced by measured ones without an amendment.
- **Where it goes:** a runner change, so not in the 11-06 batch (already large). **Proposed:** with the v0.5 weekend (after 11-14), or a separate small batch the week of 11-09. Your decision.

## 4. Study 6

See `research/STUDY6_DESIGN_DRAFT.md`.

## 5. Contradictions fixed

**GF1 frequency (frequency only, no returns examined).**
- **Count:** joint GLD ≤ −1.5σ60 **and** SPY ≤ −1.5σ60 days, σ from the 60 returns before each day. Held data (Yahoo adjusted closes from Study 1), 2005-02-16 to 2023-12-29, 18.9 years:
  - 41 joint days;
  - **38 independent** (more than 5 trading days apart) = **2.0 a year**. That's above the 1.2 a year independence implies (correlation 0.05), but far **below the 4–5 a year estimated** in `research/GOLD_FORWARD_PREREG_GF1_GF2_v1.0.md` §2.
- **Consequence:**
  - GF1's frozen first look at **30 independent triggers is about 15 years away**, not 6–7.
  - d = 0.3 (69 events) needs about 34 years.
- **Handling:** the GF1 document is frozen, so its text is **not edited**. This correction is to be appended to the research memory (an append to a ledger needs your approval: see the decision list). GF1 stays record-only.

**Admin fee: 1.00% vs 0.75%. A difference of scope, now stated explicitly.**
- **0.75% a year** was the **historical** Study 4 rollover markup, frozen 2026-10-23 (`research/USDJPY_PREREGISTRATION.md:33`, `config.yaml` usdjpy_study1 costs). Study 4's results used it, and that is unchanged.
- **1.00% a year (1.50% stress)** is the **forward test's** admin fee, frozen in v0.2 on 2026-10-29 (`research/USDJPY_FORWARD_TEST_PREREG.md:98`, confirmed in v0.4) after the 10-29 research report recommended a higher markup.
- **Inconsistent text:** only `research/USDJPY_PIPELINE_DESIGN.md:90` (a 10-28 draft, superseded by v0.2) still says the forward pipeline uses 0.75%. A dated note is added there; the draft is not rewritten.
- **Study 5:** spot-only (no financing), so neither figure applies.
