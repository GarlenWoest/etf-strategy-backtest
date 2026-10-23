# USD/JPY study 1: pre-registration (frozen before any backtest)

_Frozen 2026-10-23. Code: `src/specialists/usdjpy.py` (`build_trials`), `src/fx_engine.py`. Config: `config.yaml usdjpy_study1`. Log rows: `research_log.csv`, phase `fx1-freeze`. Research memory: `research/memory/research.jsonl`. **No backtest, return or Sharpe ratio on real USD/JPY data was computed before this freeze.**_

## Read this first

- **Weak single-pair evidence.** The strongest academic evidence for carry and momentum comes from portfolios of many currencies:
  - Lustig, Roussanov & Verdelhan 2011;
  - Menkhoff et al. 2012;
  - Burnside, Eichenbaum & Rebelo (2008), who find diversification raises carry Sharpe ratios by over 50%.

  Results on one pair should be expected to be weaker. That's the same narrow-universe problem behind the failures of Studies 1–3.
- **Strong contradicting evidence:**
  - interest differentials stop predicting dollar returns near zero rates, and Japan was near zero for much of 1999–2022 (Engel et al. 2022);
  - the classic carry pattern reversed after 2008 (Bussière et al. 2022, the "New Fama Puzzle").
- **Trial count:** 8 trials, so the cumulative N becomes 134 + 8 = **142**.
- **Holdout:** 2024 onward stays locked.

## Common design (all trials)

| Item | Specification |
|---|---|
| Market and instrument | USD/JPY spot, as a USD-based overlay (yen per USD); long = long USD / short JPY |
| Prices | FRED DEXJPUS (H.10 noon New York buying rate), daily; the only price source (Yahoo daily FX failed the cross-check) |
| Point-in-time inputs | US Treasury yields (DGS1/2/10) and DTB3 usable from the 2nd FX trading day after their date; JGB 1Y/2Y/10Y and VIX from the next FX trading day |
| Periods | Warm-up from 1990-01-02; in-sample 1991-01-02 to 2014-12-31; validation 2015-01-01 to 2023-12-31; holdout 2024+ locked |
| Decision time | Weekly, on the last FX trading day of each week, using only data knowable that day |
| Execution | Next FX trading day at the noon NY rate (lag 1). Robustness: lag 2 |
| Position | −1, 0 or +1 × equity in USD notional; **maximum gross notional 1.0× equity (no leverage)**; re-sized only on a change or if over the cap |
| Ledger | $10,000 virtual (PAPER), reported in % and per $100 |
| Cash | Earns DTB3 (act/360); Sharpe ratios are excess returns over T-bills, i.e. the overlay |
| Financing | Rollover at the differential: US DTB3 (act/360) minus JGB 1Y (act/365, a proxy for the Japanese short rate), accrued over calendar days |
| Costs | One-way 0.015% of notional traded (≈1.6 pips at 110 yen; conservative against reviewer-reported 0.35–1.5 pip spreads) plus a **0.75%/year rollover markup** on open notional. Both are multiplied ×2 and ×3 for sensitivity |
| Benchmarks (not trials) | UB01 flat (cash only; overlay Sharpe 0); UB02 always long USD/JPY 1× (unconditional carry) |

**Kill criteria:** the K1–K7 of Studies 1–3, adapted only for FX before seeing any result. A trial is killed if it fails any one.

| | Criterion |
|---|---|
| K1 | Validation Sharpe must exceed both 0 (flat) and UB02 (always long) |
| K2 | Deflated Sharpe ≥ 0.95 at N = 142, using the cross-trial variance of these 8 trials (same sample) |
| K3 | Profitable at 1× costs but not at 2× → killed |
| K4 | ≥ 30 position changes over in-sample plus validation, or ≥ 5 validation years if the median holding period is above 3 months |
| K5 | The other grid value of the same hypothesis must also pass K1 |
| K6 | Validation Sharpe ≥ 0.5 × in-sample Sharpe |
| K7 | The $10,000 ledger never falls to $2,000 or below in 1998-08 to 1998-12, 2008-09 to 2009-03, 2011-03 to 2011-04, or 2022 |

**Reported but not trials:** 2× and 3× costs, lag-2 execution, walk-forward (5-year train / 1-year test per hypothesis), bootstrap 95% confidence intervals, effective N.

## The trials

### UJ-H1: carry level (V135, V136)

**Economic rationale:** the forward-premium puzzle (Fama 1984). High-rate currencies have, on average, not depreciated enough to offset their rate advantage. Carry returns are compensation for crash and volatility risk (Lustig et al. 2011; Brunnermeier, Nagel & Pedersen 2008). The 1.0 pp threshold means carry is only held when the differential is large enough to pay for costs and crash risk.

**Contradicting evidence:**
- the effect is unstable and vanishes near zero rates (Engel et al. 2022);
- the sign reversed after 2008 (Bussière et al. 2022);
- single-pair carry is much weaker than portfolio carry (Burnside et al. 2008).

**Data:** US 1Y or 2Y yield; JGB 1Y or 2Y yield.

**Rule:** on each weekly decision day, compute the differential = US yield − JGB yield.
- Long if the differential is ≥ +1.0 pp.
- Short if it is ≤ −1.0 pp.
- Otherwise flat.

**Exit:** the next weekly decision that changes the target.

**Grid:** maturity 1Y (**V135**) or 2Y (**V136**).

**Horizon:** weeks to years.

**Accept / fail:** K1–K7.

### UJ-H2: differential momentum (V137, V138)

**Economic rationale:** exchange rates respond to expected policy and fundamentals, so a shifting 2-year differential signals changing rate expectations. Chen & Tsang (2013) find that a downward shift of the US yield curve relative to the foreign one is followed by USD depreciation over subsequent months (US = home), with Japan in the sample.

**Contradicting evidence:**
- Chen & Tsang's own rolling out-of-sample forecasts do not consistently beat a random walk;
- their 1985–2005 sample overlaps our tuning period, so only our validation is independent;
- the zero-rate instability applies here too (Engel et al. 2022).

**Data:** US 2Y yield and JGB 2Y yield.

**Rule:** compute the change in (US 2Y − JGB 2Y) over L FX trading days.
- Long if it's positive.
- Short if it's negative.
- Flat if it's exactly zero or missing.

**Grid:** L = 63 (**V137**) or 126 (**V138**).

**Accept / fail:** K1–K7.

### UJ-H3: carry with a risk-off filter (V139, V140)

**Economic rationale:**
- Carry trades crash when risk appetite and funding liquidity fall, as in the USD/JPY crash of 7–8 October 1998 (Brunnermeier, Nagel & Pedersen 2008).
- High-rate currencies lose when global FX volatility rises (Menkhoff et al. 2012).
- The yen appreciates when US stocks fall and volatility rises (Ranaldo & Söderlind 2010).

Stepping out of carry in high-risk regimes should cut the worst losses.

**Contradicting evidence:**
- most of these effects are contemporaneous, not predictive;
- volatility timing failed out of sample in commodities (Kang & Kwon 2021, library C143), and in 103 equity strategies (Cederburg et al., C144).

**Data:** as H1 (2Y), plus the VIX or USD/JPY realized volatility.

**Rule:** apply H1 (2Y, ±1.0 pp), but go flat on decision days when the risk measure is above the 80th percentile of its trailing 252 values.

**Grid:** the risk measure.
- **V139:** the VIX.
- **V140:** USD/JPY 21-day realized volatility of daily log returns, annualized.

**Accept / fail:** K1–K7. K1 compares against UB02, not against H1.

### UJ-H4: relative yield-curve slope (V141, V142)

**Economic rationale:** the term structure carries information about future inflation and growth. Chen & Tsang (2013), with the US as home, state that "when the domestic yield curve shifts down or becomes steeper by one percentage point relative to the foreign one, home currency can depreciate by 3–4 percent over subsequent months". **The sign was taken from the paper's text before any data analysis.**

**Contradicting evidence:**
- the same out-of-sample weakness and sample overlap as H2;
- our 10y−2y spread is a simple stand-in for their Nelson–Siegel slope factor.

**Data:** US 2Y and 10Y yields; JGB 2Y and 10Y yields.

**Rule:** compute the relative slope RS = (US10 − US2) − (JGB10 − JGB2), and its change over L FX trading days.
- A rise (US curve relatively steeper) → short USD/JPY.
- A fall → long.
- No change or missing → flat.

**Grid:** L = 63 (**V141**) or 126 (**V142**).

**Accept / fail:** K1–K7.

## Considered and not pre-registered

| Idea | Why not |
|---|---|
| **Intervention-based trading rule** | The Ministry of Finance's 1991–2001 daily record was disclosed only in July 2001 (Ito 2003), so it wasn't observable at the time. Afterwards, yen-buying operations appear only in 2022 (validation), and the 2010–2011 yen-selling operations are a handful of days. Any rule would rest on one or two episodes, failing the "depends on one unusual event" test. Recorded instead as an **open research question**: a descriptive event study using publication dates. |
| FX price trend / time-series momentum | The family was already killed in Studies 1–3, and FX trend-rule profits disappeared by the early 1990s (Neely, Weller & Ulrich 2009) |
| Cross-sectional carry and momentum | Need many currencies; outside the three-market scope |
| COT positioning, consensus surprises, intraday sessions | Not needed by these hypotheses. Consensus forecasts are paid, and intraday data is deferred under your data decision |

## Answers to the 12-point research standard (before results)

1. **Why should the edge exist?** Risk compensation (carry), and slowly incorporated changes in rate expectations (H2, H4).
2. **What supports it?** Fama 1984; Lustig et al. 2011; Brunnermeier et al. 2008; Menkhoff et al. 2012; Chen & Tsang 2013; Ranaldo & Söderlind 2010.
3. **What contradicts it?** Engel et al. 2022; Bussière et al. 2022; Burnside et al. 2008 (single pair); Neely et al. 2009; Kang & Kwon 2021; Cederburg et al.
4. **Does it survive costs?** Tested at 1×, 2× and 3× costs.
5. **Are all attempts counted?** Yes: cumulative N = 142, and every run is logged.
6. **Does it survive unseen data?** Validation 2015–2023 is untouched by earlier studies; the holdout stays locked.
7. **Does it work across environments?** Walk-forward and stress periods (1998, 2008, 2011, 2022).
8. **Does it depend on one event?** The intervention rule was excluded for that reason; the K7 stress periods are reported.
9. **Is it feasible at our size?** A $10,000 virtual ledger at ≤ 1× notional; spot FX at $100 only with 1-unit sizing.
10. **Would a simpler strategy do as well?** UB02 (always long) and UB01 (flat) are the K1 benchmarks.
11. **What could make it stop working?** Zero-rate regimes, policy regime changes (the BoJ's yield-curve control), and crowded carry unwinds.
12. **What would make us reject it?** Any K1–K7 failure.
