# Study 6: design draft (3 trials at most; NOT pre-registered, nothing run)

_Draft 2026-11-02 at the owner's request. No data was loaded and no trial ID was assigned. It assumes STATS_POLICY v1.1 (draft) with t > 3 as the primary test; under v1.0, none of these trials could plausibly pass (hurdles in `research/STATS_POLICY_v1.1_DRAFT.md`). Every effect size below is an **[estimate]** or a literature figure tagged **[OV]** (not verified here). Power uses a normal approximation. Cumulative N would go 145 → 148._

## Trial 6a: turn-of-month (TOM) equity

- **Mechanism:** month-end and start-of-month flows (pension and payroll contributions, window dressing, mutual-fund inflows) concentrate equity returns around the turn of the month (Lakonishok & Smidt 1988; McConnell & Xu 2008 [OV]).
- **Rule (fixed):**
  - Long the market from the close of trading day −3 (enters for day −2) to the close of day +3 of the new month; flat otherwise.
  - Applied to US and developed ex-US daily market returns.
- **Data lineage:**
  - Ken French daily US market (Mkt-RF + RF), held: `data/raw/r8_kenfrench_daily/`, 1926–2023.
  - Ken French **developed markets** daily factors (Fama/French Developed 3 Factors [Daily]), **not held**, download needed [OV: daily developed series start ~1990-07]. Window **1990-07 to 2023-12** (the request said 1989; the developed data start limits it).
  - Copyright Fama & French; local use only.
- **Untouched?**
  - Calendar rules were never tested by this project, and US equities 1990–2023 were used only for monthly trend and momentum families (Study 3), not calendar effects.
  - **Published-sample overlap is large** (the TOM effect is well known since 1988), so this is weak confirmation (L10).
- **Benchmark (matched):** the same markets always long; the claim is about excess return *per day in the market*. Also, a placebo: the same number of days at a random fixed month offset.
- **Power [estimate]:** about 12 events a year per market, so ~400 events per market over 33.5 years.
  - At a per-event Sharpe d ≈ 0.15: t ≈ 3.1 (power about 0.53 against t > 3, 0.92 against 1.645).
  - The pooled US + developed panel adds effective breadth, but the regions are correlated.
- **Costs:** about 24 trades a year. Round trip about 0.02–0.05% for a broad ETF (Study 1's ETF cost assumption) → about 0.5–1.2% a year: **costs likely decide it** (K3).
- **Reject if:** t ≤ 3 on the US series (primary); placebo ≥ TOM; negative at 2x costs; reversed sign in either half (1990–2006 / 2007–2023).
- **$100–$1,000:** implementable with fractional shares of a broad US ETF (SPY/VTI) and a developed ex-US ETF (EFA/VEA) at brokers that offer fractions [OV: broker-specific]. Commissions are zero at most brokers; spreads remain.
- **External benchmark:** none needed (always-long is the benchmark).

## Trial 6b: diversified volatility-scaled trend (~20 markets)

- **Mechanism:** time-series momentum across asset classes (Moskowitz, Ooi & Pedersen 2012; Hurst, Ooi & Pedersen 2017 [L0 in library]): slow-moving information and hedging demand. Single-market evidence is weak (Study 1/3, F002), and **breadth is the point**.
- **Rule (fixed):**
  - Monthly, the sign of the 12-month return per market.
  - Each position scaled to 10% annualized volatility (σ60).
  - Equal risk across markets, total gross capped.
- **Markets and data lineage, about 20:**
  - **G10 FX vs USD (9 pairs):** Board H.10 daily noon rates. The Board package holds them; the GBP and JPY series are registered already, the others would need to be extracted from the same package.
  - **Bond yields:** US 10y (Board H.15). Others are OECD long-term rates **monthly only** (OECD SDMX, terms permissive). **Daily non-US bond futures data: no free licensed source [gap].**
  - **Equity indices (~6):** **gap:** no free licensed daily index history for most regions. Ken French daily *regional* factors (US, Europe, Japan, Asia-Pacific ex Japan; held for US only) can stand in for regional equity.
  - **Gold:** **no untouched licensed daily series** (Study 5 finding); LBMA is licensed. Gold would be monthly World Bank averages only, or excluded.
  - **Realistic count with free licensed daily data:** about 9 FX + 1 US bond + 4 regional equity = **~14 markets**, from 1990-07.
- **Benchmark (matched):** the same markets always long, vol-scaled the same way (as requested). External, for reference only: managed-futures ETFs **DBMF, KMLM, CTA** (live track records from 2019/2020/2022 [OV]), not comparable over 1990–2023.
- **Power [estimate]:** published diversified-trend Sharpe is about 0.7–1.0 pre-2010 and lower after [OV]. The *excess* over vol-scaled always-long is perhaps 0.3–0.5.
  - At 0.4 over 33.5 years: t ≈ 2.3, so power about 0.25 against t > 3 and 0.75 against 1.645.
  - **It fails the owner's ≥ 0.5 power requirement under t > 3 unless the true excess Sharpe is ≥ about 0.52.**
- **Costs:** monthly rebalancing across ~14 markets; FX at the frozen 0.015% one-way plus financing (carry is part of the return here; the Board/OECD short rates are needed: OECD IR3TIB monthly, terms permissive).
- **Reject if:** t ≤ 3 vs the matched benchmark; worse worst-drawdown than the benchmark; reversal in either half.
- **$100–$1,000:** not implementable directly (14 instruments, futures minimums). Practical exposure is a managed-futures ETF (DBMF, KMLM, CTA) [OV: expense ratios ~0.75–0.95%].

## Trial 6c: G10 FX carry + momentum + value cross-section

- **Mechanism:**
  - **Carry:** compensation for crash risk (Menkhoff et al. 2012, FX005 [L2]; Brunnermeier, Nagel & Pedersen 2008, FX002 [L2]).
  - **Momentum:** cross-sectional currency momentum (Menkhoff et al. 2012 JFE, FX008 [L1]).
  - **Value:** PPP reversion (Asness, Moskowitz & Pedersen 2013 [OV]).
  - Combined because the three are weakly correlated.
- **Rule (fixed):**
  - Monthly, rank 9 non-USD G10 currencies on three signals: carry (3-month rate differential vs USD), momentum (12-month spot return), value (5-year real-exchange-rate deviation, CPI-based).
  - Average the ranks; long the top 3, short the bottom 3, equal weight, gross 1x.
- **Data lineage:**
  - Spot: Board H.10.
  - Short rates: OECD IR3TIB monthly (OECD terms permissive; FRED copies not used, RR-1).
  - CPI: OECD monthly.
  - All pre-2024, from 1990.
- **Untouched?**
  - Single-pair carry is burned for USD/JPY (Study 4). This is a cross-section, a different trial family, but GBP and JPY overlap.
  - **Published-sample overlap is large** (the canonical datasets are 1976/1983–2009/2010 [L: FX005, FX008]).
- **Benchmark (matched):** the **dollar factor** (equal-weight long all 9 vs USD), as requested, plus flat.
- **Power [estimate]:** combined G10 carry/momentum/value Sharpe about 0.5–0.8 pre-2008, much lower after (the 2008 carry crash) [OV].
  - At 0.5 over 33.5 years: t ≈ 2.9, so power about 0.46 against t > 3 (≈ 0.5 only at a true Sharpe ≥ about 0.52).
- **Costs:** monthly turnover of about 6 pairs; FX at 0.015% one-way (2x/3x checks) plus financing (carry is earned through financing, so financing is part of the signal and must use the same rate series).
- **Reject if:** t ≤ 3 vs the dollar factor; negative at 2x costs; one signal alone explains it (report each component separately, descriptively only).
- **$100–$1,000:** implementable at OANDA US with 1-unit sizing (6 pairs × small notionals) [OV: OANDA US unit sizing]. Financing at broker rates differs from the model. External benchmark: none suitable (no liquid G10 cross-section ETF).

## Summary

| Trial | Power ≥ 0.5 at a realistic effect under t > 3? | Main gap |
|---|---|---|
| 6a TOM | Borderline yes (~0.53 at d = 0.15) | Costs; published-sample overlap |
| 6b Trend | **No** at excess Sharpe 0.4 (~0.25) | Market coverage (no free daily equity/bond data); power |
| 6c FX cross-section | Borderline no (~0.46 at Sharpe 0.5) | Post-2008 decay; published-sample overlap |

**Recommendation:** register **6a** and **6c**. Register 6b only if you accept power below 0.5, or if broader licensed data (paid) is approved. 6b is better served by holding a managed-futures ETF as an *observation* (DBMF/KMLM) than by a historical trial.
