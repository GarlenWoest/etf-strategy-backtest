# Idea pool: gold and commodities (Phase 9d)

_Written 2026-10-22. Nothing in this file has been backtested, and nothing is pre-registered. Every source ID (C###) refers to [`sources_commodities.csv`](sources_commodities.csv)._

**Evidence grades:**
- **strong:** several peer-reviewed studies with long histories or out-of-sample tests, and the rule works on a single ETF.
- **moderate:** good sources, but the evidence is indirect (futures cross-sections, contemporaneous correlations), or credible counter-evidence exists.
- **weak:** blogs, theses or in-sample-only studies, or the best evidence argues against the idea.

Grades describe the evidence, not my expectation of passing K1–K7.

## Read this first: what the ETF study already showed about gold
The 92-trial study already tested two families on gold:
- **Trend:** GLD and UGL with 50/100/200-day SMAs, V001–V018.
- **Time-series momentum:** 3/6/12-month lookbacks, V025–V042.

**All 12 gold variants were killed.** Out of sample (2019–2023), their Sharpe ratios were −0.04 to 0.41, against 0.56 for buy-and-hold GLD. The validation window is unchanged at 2019–2023, so re-testing gold-only trend on it is not a fresh test: those exact years have already been seen for gold. Ideas below that overlap the earlier trials are marked **[overlap]**.

Two more structural points:
- **Rules the instruments impose:** signals come from ETF closes (no Yahoo futures OHLC; see `reports/data_quality_commodities.md`). Fills are at the next open with the same cost model, and spare cash earns T-bills.
- **Universe:** GLD (gold), SLV, USO and CPER, plus UGL, AGQ and UCO as 2x versions. There is no liquid leveraged copper ETF. DGP traded only about $0.1M a day in 2023, so it is excluded as illiquid.
- **CPER needs your decision:** it is unusable before 2017 (see the data report). Every multi-commodity idea below assumes copper is handled by one of the data report's options (a), (b) or (c).

## Ranked ideas

### I01. Multi-commodity time-series momentum basket. Evidence: strong
- **Rule:** at each month end, for each of gold (GLD), silver (SLV), oil (USO) and copper (CPER), hold a 25% slice if its L-month total return beats the T-bill return over the same L months; otherwise that slice sits in T-bills. Fill at the next open.
- **Grid:** L ∈ {3, 6, 12} × {1x, leveraged where it exists (UGL, AGQ, UCO; copper stays 1x)} = **6 trials**.
- **Supporting sources:**
  - Moskowitz, Ooi & Pedersen 2012 (C108): 24 commodities among 58 futures, 1–12-month persistence.
  - Hurst, Ooi & Pedersen 2017 (C002).
  - Babu et al. 2020 (C001).
  - Baltas & Kosowski (C139).
  - Levine et al. 2018 (C014).
  - Faber 2007 (C128) and a replication (C129).
- **Counter-evidence:**
  - Kim, Tse & Wald (C110): most of the TSMOM edge comes from volatility scaling.
  - Elaut & Erdős (C111): it breaks down for long stretches in single markets.
  - Zaremba (C118): weak in heavily financialized markets such as gold and oil.
- **Why it ranks first:** diversification across markets is where the academic evidence is strongest, and the ETF study's 4-asset version (P2) was its closest near-miss.
- **[overlap]:** the gold leg overlaps V025–V042.

### I02. Gold trend exit (moving-average filter). Evidence: strong, [overlap: already killed]
- **Rule:** hold GLD (or UGL) while the GLD close is above its N-day SMA; otherwise T-bills.
- **Sources:** Bartsch, Baur, Dichtl & Drobetz 2018 (C015) tested more than 4,000 gold timing rules with data-snooping controls, and only trend-following exits survived. Also Faber (C128) and Alpha Architect trend signals (C102).
- **Not recommended to re-test:** this is V001–V018, killed in Phase 6. The Bartsch result is mainly about cutting drawdowns, not beating buy-and-hold on Sharpe, which is what K1 requires.

### I03. Volatility-scaled trend (Carver-style continuous forecast). Evidence: moderate
- **Rule:** for each commodity, compute the forecast = EWMA(16) − EWMA(64) of the close, divided by 64-day price volatility, and clip it to [−2, 2]. Long-only, so negative forecasts become 0.
- **Weight:** weight = forecast / 2 × (target vol 20% / 60-day realized vol), capped at 100% per instrument at 1x. A leveraged version uses UGL/AGQ/UCO for weights above 1x of the underlying. Weekly rebalance, with a 10% no-trade band.
- **Grid:** target vol {15%, 20%, 25%} × {gold only, 4-commodity basket} = **6 trials**.
- **Supporting sources:** Carver (C119, C120), Moskowitz, Ooi & Pedersen (C108), Fan, Li & Liu 2018 (C053), and Moreira & Muir (C142).
- **Counter-evidence:** Kang & Kwon 2021 (C143) found volatility management in commodity futures **failed out of sample**. Cederburg et al. (C144) found the same for 103 equity strategies.

### I04. Dual-momentum rotation across commodities. Evidence: moderate
- **Rule:** at each month end, rank GLD, SLV, USO and CPER by L-month total return. Hold the top one if its return beats T-bills; otherwise T-bills.
- **Grid:** L ∈ {3, 6, 12} × {1x, leveraged} = **6 trials**.
- **Sources:**
  - Miffre & Rallis 2007 (C011).
  - Fuertes, Miffre & Rallis 2010 (C012).
  - Quantpedia, Dual vs Single Momentum in Commodities (C149). It warns that much of the parameter space fails to beat the naive benchmark.
  - Antonacci (C151, C152).
- **Weaknesses:** the academic evidence is long-short across 20–30 futures; a top-1-of-4 long-only rule is a thin proxy. The ETF study's own rotation trials (V061–V066) were killed.

### I05. Gold real-yield filter. Evidence: moderate
- **Rule:** hold GLD (or UGL) when the 20-day average of the 10-year TIPS real yield (FRED DFII10) is below its 120-day average, i.e. real yields are falling. Otherwise T-bills. Signal on day t uses DFII10 up to t−1, because FRED values publish the next morning.
- **Grid:** {20/120, 20/250} × {1x, 2x} = **4 trials**.
- **Supporting sources:**
  - Barsky & Summers 1988 (C121): theory.
  - Erb & Harvey 2013 (C106).
  - World Gold Council GRAM (C025).
  - Data commentary C028, C029, and the Elfenbein real-rate rule (C123).
- **Counter-evidence:** the gold–real-yield link broke from 2022 (C146 Janus Henderson; C147 Goldmoney disputes the cause). That break sits inside the validation window, so this is a genuinely hard test.
- **Overall:** strong evidence for a contemporaneous link; little published evidence that the signal predicts.

### I06. Gold dollar-trend filter. Evidence: moderate
- **Rule:** hold GLD (or UGL) when the broad dollar index (FRED DTWEXBGS, lagged one day) is below its 200-day average; otherwise T-bills. Before 2006 there is no broad index; the in-sample period then starts in 2006, or uses DTWEXM, which runs until 2019.
- **Grid:** SMA {100, 200} × {1x, 2x} = **4 trials**.
- **Sources:** Capie, Mills & Wood 2005 (C021), Pukthuanthong & Roll 2011 (C023), Kunkler & MacDonald 2016 (C022), and Joy 2011 (C024).
- **Weakness:** all four document a contemporaneous negative gold–dollar relation, not a predictive one.

### I07. Commodity value (5-year reversal) rotation. Evidence: moderate
- **Rule:** at each month end, hold the commodity ETF with the largest 5-year price decline (lowest close ÷ close 60 months earlier, adjusted). Optionally, it must also pass I01's 12-month TSMOM filter; otherwise T-bills.
- **Grid:** {with, without filter} = **2 trials**.
- **Sources:** Asness, Moskowitz & Pedersen 2013 (C090), and Alpha Architect's summary of seven centuries of commodity reversals (C103).
- **Weaknesses:**
  - The evidence is cross-sectional across many commodities.
  - With only 4 ETFs and a 60-month warm-up, the first signal is around 2011–2016, depending on USO and CPER.
  - Switches are rare, so the K4 rule (30 round trips, or 5 out-of-sample years for monthly strategies) is at risk.

### I08. Short-term reversal in commodity ETFs. Evidence: moderate
- **Rule:** each Friday close, buy the one of GLD, SLV, USO and CPER with the worst 5-day return, and hold it for 5 trading days. Optionally, only when that ETF is above its 200-day SMA.
- **Grid:** {no filter, filter} × {1x, 2x} = **4 trials**.
- **Sources:**
  - Wang 2004 (C048): short-term reversal in futures.
  - Kang et al. 2026 (C049): momentum vs reversal depends on who is trading.
  - Rossi, Zhang & Zhu 2025 (C047): basis reversal, which needs curve data.
- **Weakness:** weekly turnover makes it the most cost-sensitive idea here.

### I09. Inflation-regime commodity switch. Evidence: weak
- **Rule:** hold the equal-weight commodity basket (GLD/SLV/USO/CPER) when the 10-year breakeven inflation rate (FRED T10YIE, lagged one day) is above its value 126 trading days earlier. Otherwise hold SPY.
- **Grid:** lookback {63, 126} = **2 trials**.
- **Sources:** Neville et al. 2021 (C054), and Man Group pieces (C055, C056).
- **Weakness:** the inflation regimes in Neville et al. are defined after the fact, so there is no evidence that a real-time signal works.

### I10. Gold volatility-regime filter. Evidence: weak
- **Rule:** hold UGL when ^GVZ (lagged one day) is below its 252-day median; otherwise hold GLD at 1x. A cash variant holds GLD versus T-bills instead. Data start in mid-2008, so in-sample runs 2009–2018.
- **Grid:** **2 trials**.
- **Sources:** Moreira & Muir (C142), with Kang & Kwon (C143) against it, out of sample. The GVZ explainer (C114) is rejected marketing. No paper tests GVZ timing directly.

### I11. Gold/silver ratio mean reversion. Evidence: weak
- **Rule:** compute the ratio GLD/SLV, normalized at the start, and its 252-day z-score. Hold SLV when z > +1, and GLD when z < −1 or in between.
- **Grid:** z threshold {1, 1.5} = **2 trials**.
- **Sources:**
  - UC Denver J.P. Morgan Center report (C060).
  - Escribano & Granger 1998 (C112) is the best academic test, and finds cointegration only in some periods, with silver's forecastability lost out of sample.
- Most other material on the ratio was broker or blog marketing and was rejected.

### I12. Copper/gold ratio risk switch. Evidence: weak
- **Rule:** hold SPY when the CPER/GLD ratio (HG=F/GC=F before 2017) is above its 200-day average; otherwise hold GLD.
- **Grid:** **1–2 trials**.
- **Sources:** Oort 2020 BSc thesis (C124), and ETFdb (C126), which reports that the link unravelled after 2020.

### I13. Seasonality (gold autumn effect; oil driving season). Evidence: weak. Recommend dropping
- **Gold rule:** hold GLD from September to November only.
- **Oil rule:** hold USO from February to May only.
- **Supporting sources:** Baur 2013 (C016), and Borowski 2019 (C018).
- **Against:**
  - The 2024 replication found the autumn effect **reversed** in recent data (C017).
  - CXO found no reliable monthly pattern in USO (C094).
  - Ewald et al. 2022 (C092) is in-sample only.

### I14. Static SPY/gold mix. Benchmark candidate, not a timing idea
- **Rule:** 70% SPY and 30% GLD, rebalanced monthly.
- **Sources:** Baur & Lucey 2010 (C127) shows gold is a hedge on average and a short-lived safe haven.
- **Proposal:** add it as a benchmark next to SPY and buy-and-hold gold, not as a trial.

## Flagged: needs data that isn't free, so dropped
| Idea | Why it can't be tested | Sources |
|---|---|---|
| Carry / term structure: long backwardated, avoid contango | Needs second-contract futures prices with history; Yahoo has front-month only | C007–C010, C013, C116, C117 |
| Momentum + term-structure double sort | Same | C012, C097 |
| Basis-momentum | Needs the first and second nearby contracts | C088, C089 |
| Short-term basis reversal | Needs the curve | C047 |
| Hedging pressure (COT positioning) | COT is free weekly from CFTC, but the evidence is a long-short cross-section across many futures; there's no single-market evidence for 4 ETFs | C084, C085 |
| Skewness factor | A cross-section of 27 futures; on 4 ETFs it's a weak proxy | C086, C087 |

One untested free proxy is possible for oil carry: the USO-minus-USL return spread (front month vs a 12-month strip). It isn't in the literature, so I would only pre-register it if you want an explicitly exploratory trial.

## Dropped for other reasons
- **Gold around FOMC announcements:** the pre-FOMC drift exists only in US equities (C133, Lucca & Moench), and gold's reaction is intraday (C132).
- **Real gold price valuation** (Erb & Harvey; buy when gold/CPI is below its long-run mean): only one or two regime changes in 2004–2023, so it fails K4 by design.
- **Course sellers, signal services and newsletters** were rejected at grading: 36 rejected strategy sources (see the `decision` column).

## Instrument feasibility for a $100 account
Prices are 2023-12-29 closes from the downloaded data. No later prices were looked at. Fees are issuer or exchange figures where I found them (sources in the CSV); figures marked "unverified" come from one or two secondary sources.

| Instrument | Possible with $100? | Minimum | Ongoing cost | Leverage | Tax (US) |
|---|---|---|---|---|---|
| GLD (gold) | Yes, if the broker allows fractional shares. GLD-specific fractional eligibility is unverified; 1 share = $191 | $1 at Schwab, Fidelity or Robinhood for eligible ETFs | ER 0.40%; very liquid | 1x | Grantor trust: long-term gains taxed as collectibles (max 28%), short-term as ordinary income; no K-1 |
| IAU (gold) | Yes; 1 share = $39 | 1 share or fractional | ER 0.25% | 1x | Same as GLD |
| GLDM (gold) | Yes; 1 share = $41. Only exists from June 2018, so too short for in-sample testing | Same | ER 0.10% | 1x | Same as GLD |
| SLV (silver) | Yes; 1 share = $22 | Same | ER 0.50% | 1x | Same as GLD (collectibles) |
| USO (oil) | Yes; 1 share = $67 | Same | Total expenses about 0.6–0.8% plus futures roll (contango) drag | 1x | Commodity pool: K-1, 60/40 blended rate on the futures it holds |
| CPER (copper) | Yes; 1 share = $24, but thin ($1.3M a day in 2023) | Same | ER about 0.97% plus roll | 1x | K-1, 60/40 |
| UGL (2x gold) | Yes; $6M a day in 2023 | Same | ER 0.95% plus daily-reset drag | 2x daily | K-1, 60/40 |
| AGQ (2x silver) | Yes; $21M a day | Same | ER 0.95% plus drag | 2x daily | K-1, 60/40 |
| UCO (2x oil) | Yes; $72M a day; 5 reverse splits, and −57% on 2020-04-21 | Same | ER about 1.4% plus roll and drag | 2x daily | K-1, 60/40 |
| DGP (2x gold ETN) | Not recommended: $0.1M a day | Same | Fee not verified; issuer credit risk | 2x | ETN treatment (not verified) |
| MGC micro gold futures | **No** | Exchange margin about $1,700–1,900. Broker minimums vary ($0 at NinjaTrader; $1,500–2,000 elsewhere; conflicting reports) | Commissions plus exchange fees per side (not verified) | Notional 10 oz ≈ $20,700, about 200x a $100 account; a $10/oz move = $100 | Section 1256: 60/40, marked to market at year end |
| SIL micro silver futures | **No** | Margin about $4,000+ | Same | Notional 1,000 oz ≈ $23,900 | Section 1256 |
| MCL micro WTI futures | **No** | Margin about $550–600 | Same | Notional 100 bbl ≈ $7,200; a $1/bbl move = $100, the whole account | Section 1256 |
| US spot XAU/USD (forex dealer) | **Effectively no** | CFTC's actual-delivery rule (C065) treats leveraged retail metal trades not delivered within 28 days as futures. One 2022 report says FOREX.com offers US clients only unleveraged spot metals (unverified). Non-US offers (10 oz minimum) don't apply to a US account | Spread plus financing | None for US retail (as reported) | Unclear: Section 988 applies to currencies; treatment of a spot-metal contract is unresolved |
| Physical gold (1 g bar) | Technically yes (1 g ≈ $67 at end-2023 spot) | 1 g bar | 7.7–30% premium on small bars plus shipping, and a dealer buy-back spread: roughly 10–30% round trip | 1x | Collectibles (max 28%) |

**Bottom line:** with $100, the realistic instruments are the ETFs: GLD/IAU/GLDM, SLV, USO and CPER at 1x, and UGL/AGQ/UCO at 2x. Micro futures need 5–40x the account just for margin. Spot XAU leverage isn't available to US retail. Physical gold costs 10–30% per round trip. I have not switched any instrument.

## Trial count if everything ranked were pre-registered
- I01 6, I03 6, I04 6, I05 4, I06 4, I07 2, I08 4, I09 2, I10 2, I11 2, I12 2 = **40**. I02 and I13 are excluded.
- That gives cumulative N = 92 + 40 = **132** for the Deflated Sharpe. The fewer ideas you pick, the lower the DSR hurdle.
