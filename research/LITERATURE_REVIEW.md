# Literature review (Phase 0.5)

_Written 2026-10-22. 49 sources in `research/sources.csv` (S01–S49): 39 academic or regulator/issuer/government, 10 practitioner (blogs, replications, reviews). Quality ratings: 31 strong, 12 moderate, 6 weak._

## Bottom line first

1. **Trend filters on a single index ETF mostly cut risk; they do not reliably raise returns.** Over long samples, a 200-day moving average on the S&P 500 roughly matched buy-and-hold returns with about two-thirds of the volatility and half the drawdown (S14: 10.9% vs 9.1% CAGR, Sharpe 0.60 vs 0.30, 1928–2015, no costs). Out of sample the edge is smaller (S10, S13), and some researchers argue single-asset time-series momentum barely exists without volatility scaling (S04, S05).
2. **Leverage changes the picture, which is the main reason this project might find something.** Volatility drag on a daily-reset 3x fund is about 3σ² per year. That drag is much lower above the 200-day average, because volatility is lower there (S14, S16). This is the one mechanism where a trend filter plausibly adds return, not just reduces risk. It is also where the worst outcomes live: even the filtered 3x S&P strategy had a −92% maximum drawdown since 1928 (S14).
3. **Expect realistic Sharpe ratios of 0.3–0.6 for anything we test, before multiple-testing haircuts.** With roughly 120 variants, the Deflated Sharpe hurdle will be hard to clear. The most likely honest outcome is that few or no strategies pass Phase 6.
4. **Short-term mean reversion on SPY/QQQ has a real academic basis** (daily index autocorrelation turned negative in the 2000s, S36). But the popular RSI(2) rules have no rigorous cost-adjusted out-of-sample evidence (S38, S39). Expect high trade counts to make it the most cost-sensitive family.
5. **Base rates for retail traders are bad** (S42–S45). Nothing here should be read as a reason to expect $100 to become $1,000.

## Sources: how they were chosen

- **Included:** peer-reviewed papers and working papers (SSRN, NBER, arXiv, author pages); regulator, issuer and government pages; and practitioner material only where the author shows their method or replicates published work.
- **Discarded under rule (b):** signal sellers and course sites (e.g. Quantified Strategies, paid Substack "17 years out of sample" claims), screenshot-style blogs, and anything without methodology.
- **Not used because they looked like unauthorized copies** (Hard Rule 8): mirrored PDFs of AQR and Antonacci papers on third-party sites (trendfollowing.com, thechartist.com.au, an Indian university repository), Scribd copies, and "PDF download" pages for Chan, Clenow and Kaufman books.
- **Books:**
  - Lopez de Prado: used his free SSRN papers (S26, S27, S29).
  - Chan: used his blog (S38).
  - Carver: used his blog (S46, S47).
  - Antonacci: used a summary of his paper (S11) plus a replication (S12).
  - Thorp: used Rotando & Thorp (S40) and MacLean/Thorp/Ziemba (S41).
  - **Kaufman:** no legitimate free summary or author paper found, so not used.
  - **Clenow:** interview pages exist, but no transcript was available, so not used.
- **Videos and talks:** I found no published transcripts for the relevant Carver, Clenow or Asness talks, so I skipped them rather than guess (Hard Rule 8). The one talk-based source is a written summary of a 2010 Asness talk (S48), rated weak.
- **Prompt injection:** none of the pages or PDFs I read contained instructions directed at me.
- **Verification gaps:** several claims come from abstracts or summaries, because three PDFs could not be fully parsed with standard-library tools. Reading PDFs properly would need `pdftotext` (poppler), which is not on the allowed list, so I did not install it. Figures marked "from abstract" in `sources.csv` should be treated as approximate.

## What the evidence supports, by strategy family

| Family | Best evidence | What it says for our 4 instruments | Expected strength |
|---|---|---|---|
| Buy and hold | S14, S35 | SPY has had a positive equity premium. TLT's 1982–2021 bull market came from falling yields that cannot repeat from today's levels (S46 removes ~1.2%/yr bond tailwind). GLD has no reliable long-run real return (S32, S33). | Benchmark |
| Trend (price vs N-day MA) | S08, S13, S14, S03 | Lowers volatility and drawdowns; return edge small and concentrated in bear markets; many whipsaws. 50/100/200-day rules perform similarly on S&P (S14 Table 6). | Risk reduction: moderate. Return edge: weak. |
| Time-series momentum (3/6/12 m) | S01, S02, S04, S05 | Mathematically very close to the MA rule (S03). The strong published results depend on volatility scaling and diversification across ~60 futures, neither of which we have. | Weak for single unscaled ETFs |
| RSI(2) mean reversion | S36, S38, S39, S37 | Daily index autocorrelation has been negative since the 2000s, which favors SPY/QQQ. No credible cost-adjusted out-of-sample test of RSI(2) found. Unclear for GLD/TLT. | Plausible on equity ETFs; high cost risk |
| Cross-asset rotation (top-1, cash filter) | S11, S12, S10 | Absolute plus relative momentum reduced drawdowns in backtests. Results are fragile to lookback and rebalance date (S12). Holding one asset means no diversification. | Moderate in-sample; fragile |
| Leveraged versions | S14, S15, S16, S22 | Leverage helps only when volatility is low and trends persist. Unfiltered 3x buy-and-hold has had near-total drawdowns (S&P 3x: −99.9% since 1928, S14). | The main source of possible upside and of ruin |

### Instrument notes
- **SPY/QQQ:** strongest support for both trend filters (S14) and short-term reversal (S36). QQQ's higher volatility means far more decay in TQQQ: about 3 × 0.23² ≈ 16% a year, vs about 3 × 0.18² ≈ 10% for UPRO, before fees and financing.
- **TLT/TMF:** the stock–bond hedge is not structural. Correlation depends on whether inflation or growth shocks dominate, and it turned positive in 2022 (S35). Rotation strategies that assume "bonds rally when stocks fall" were hurt badly in 2022.
- **GLD/UGL:** gold is a short-lived safe haven in equity crashes (S34) but an unreliable inflation hedge, with long stretches of negative real returns after peaks (S32, S33). **UGL is 2x gold futures (Bloomberg Gold Subindex), not 2x GLD, and it is a commodity pool that issues a K-1 (S20).** Synthetic UGL built from GLD will therefore differ from real UGL (futures roll and financing), and its taxes are not "short-term gains taxed as ordinary income" (see open decisions).

## How leverage and volatility decay change results

- **The formula** (Avellaneda & Zhang, S16): the daily-reset fund's log return ≈ L × (underlying log return) − ((L² − L)/2) × σ² × t − expenses − financing.
  - For 3x the variance penalty is 3σ²; for 2x it is σ².
  - At 18% volatility (SPY) a 3x fund loses about 9.7% a year to volatility alone. At 23% (QQQ) about 16%. At 15% (TLT) about 6.8%. 2x gold at 16% loses about 2.6%.
  - On top come the expense ratio (0.78–0.95%) and financing on the borrowed (L−1) part, about (L−1) × T-bill rate.
- **Path matters, not just volatility:** trending low-volatility periods can produce more than L× the index return; choppy periods destroy value even when the index ends flat (S15, S17, S22: one 3x fund fell 53% while its index rose ~8%).
- **Why a trend filter interacts with leverage:** S&P 500 volatility has been much lower above its 200-day average than below it (S14). So a filter that holds 3x only above the average avoids the regime where the 3σ² penalty is largest.
- **Our synthetic formula** charges (L−1) × T-bill financing. The Gayed & Bilello results (S14) charged only a 1% fee and no execution costs, so they overstate real-world returns. We will measure synthetic-vs-real tracking error over 2009/2010–2023 in Phase 2.
- **Kelly** (S40, S41):
  - The growth-optimal fraction is roughly f* = excess return / variance. For the S&P with ~6% excess return and 18% volatility, f* ≈ 1.9.
  - A permanent 3x position is therefore above full Kelly. Above full Kelly, growth falls; at about 2× Kelly, expected growth is near zero; beyond that it is negative.
  - Estimation error in the mean makes over-betting more likely (S41).
  - **"All-in" 3x is not neutral aggression; on these estimates it lowers the median outcome.** Phase 7A will measure this directly.

## What has decayed since publication

- **Anomalies in general:** returns about 58% lower after publication (S30).
- **Faber's 10-month trend model:** Sharpe ~0.81 in 1972–2005 vs ~0.68 in 2006–2025 (S10, third-party). Faber's own 2018 update says it held up in real time (S09).
- **Fast trend following:** profits fell after 2008 in many futures (S06). For us this mainly concerns the 50-day variant.
- **Daily index autocorrelation:** changed sign from positive to negative (S36). Daily momentum-style rules on SPY that worked before ~2000 may now work in reverse. This is the regime change that favors mean reversion.
- **Stock–bond correlation:** the 2000–2021 negative correlation ended in 2022 (S35).
- **Volatility management:** published alphas largely fail in real-time tests (S24).

## Typical realistic Sharpe ratios (annual)

| Strategy | Range seen in the sources |
|---|---|
| SPY buy-and-hold, long history | ~0.3–0.45 (S14: 0.30 from 1928; S46: 60/40 0.38 since 1982, 0.24 without secular tailwinds) |
| Single-asset 200-day trend on S&P, no costs | ~0.6 in sample (S14); lower out of sample (S13) |
| Diversified multi-asset trend (Faber-style) | ~0.7 out of sample (S10) |
| Professional diversified trend, net | ~0.3–0.5 (S46) |
| Retail day traders | negative for >97% (S45) |

**What this means for Phase 6:** the Deflated Sharpe Ratio penalizes the best of N trials.
- A rough estimate: with a 5-year out-of-sample window, a Sharpe ratio's standard error is about 0.45. The best of ~100 near-random independent trials would then reach a Sharpe of about 1 by luck alone.
- Our variants are highly correlated, so the effective number of trials is lower and the hurdle smaller. But it is still well above 0.5.
- **I expect most or all strategies to fail the DSR ≥ 0.95 criterion.** This is an estimate; Phase 5 will compute it properly.

## Common mistakes the plan already guards against, and a few it doesn't yet

Already covered by your rules:
- lookahead (signal at close, fill at next open)
- survivorship and mixed adjusted/unadjusted prices
- tuning on the test period
- ignoring costs
- hiding failed variants
- annualizing Sharpe naively when returns are autocorrelated (S31)

Not yet covered; I suggest adding these to the Phase 3/5 tests:
1. **Correlated variants:** trend (2) and TSMOM (3) are nearly the same signal (S03). The DSR should use the effective number of independent trials, not the raw count. I will report both.
2. **Rebalance-date luck:** monthly rotation results can change a lot with the day of the month (S12). Report rotation results for month-end and for a mid-month offset as a robustness check. This is not an extra tuned parameter.
3. **Expense ratios are a point in time:** using today's figures for 2004–2010 synthetic history is an approximation. I will note it, not tune it.
4. **Leveraged ETF overnight gaps:** a 3x fund can lose more than 33% if the index gaps down over a third. The synthetic series cannot go below zero, but a real fund could be closed. Flag only.

## Proposed additional strategies (max 3, for your approval)

All signals come from the unleveraged ETF's close, with execution at the next open, as in the main plan. Each runs on the unleveraged and leveraged versions unless stated.

### P1. Volatility-gated leverage (equity ETFs)
**Source:** S14 (volatility much lower above the 200-day MA), S16 (drag = (L²−L)/2·σ²), S25 (vol targeting helps equities). Counter-evidence: S24.
**Rules** (pairs SPY→UPRO and QQQ→TQQQ only):
- If close > 200-day SMA **and** 20-day realized volatility (annualized, from daily close-to-close returns) < threshold V: hold the 3x ETF.
- If close > 200-day SMA and volatility ≥ V: hold the 1x ETF.
- If close ≤ 200-day SMA: cash (earning T-bills).
- Evaluated daily.

**Grid:** V ∈ {15%, 20%, 25%}. MA length is fixed at 200 (not tuned) to limit variants.
**Variants:** 3 thresholds × 2 pairs = **6**.
**Why it is different from strategy 2:** it uses leverage only in the regime where decay is smallest, and steps down to 1x in high-volatility uptrends.

### P2. Multi-asset trend portfolio (Faber-style)
**Source:** S08, S09, S10.
**Rules:**
- At each month-end, hold 25% in each of GLD, SPY, QQQ, TLT whose close is above its N-month SMA of month-end closes. Each excluded asset's 25% goes to cash.
- Rebalance monthly to equal 25% slices.
- Leveraged version: the same signals, with each slice held in UGL / UPRO / TQQQ / TMF.

**Grid:** N ∈ {6, 8, 10, 12} months.
**Variants:** 4 × 2 = **8**.
**Why it is different:** strategies 2 and 5 are single-asset; this one keeps diversification, which is where most out-of-sample trend evidence comes from.
**Note on kill criteria:** it is monthly, so it falls under the "≥5 years out of sample" rule rather than the "≥30 trades" rule.

### P3. RSI(2) mean reversion only in an uptrend
**Source:** S36 (negative daily index autocorrelation), S39 (the original rule used a 200-day filter), S38.
**Rules:**
- Buy at the next open when RSI(2) (Wilder, reused from the audited repo) closes below X **and** the close is above the 200-day SMA.
- Exit at the next open after a close above the 5-day SMA.
- Same exit as strategy 4; the only change is the trend filter.

**Grid:** X ∈ {5, 10, 15}.
**Instruments:** all 4, unleveraged and leveraged.
**Variants:** 3 × 4 × 2 = **24**.
**Why:** avoids buying dips inside bear markets, the main known failure mode of strategy 4.

### Variant count if all three are approved

| Group | Variants |
|---|---|
| Strategy 2 (trend) | 3 × 4 × 2 = 24 |
| Strategy 3 (TSMOM) | 24 |
| Strategy 4 (RSI(2)) | 24 |
| Strategy 5 (rotation) | 3 |
| Strategy 6 (leveraged rotation) | 3 |
| P1 | 6 |
| P2 | 8 |
| P3 | 24 |
| **Total tested variants** | **116** |

Benchmarks (9 buy-and-hold series) are reported but not counted as trials. If you reject some proposals, the count drops; it is frozen before any backtest runs.

## Open decisions for you
1. **Approve, edit or reject P1, P2 and P3.** After that the strategy list is frozen.
2. **UGL tax treatment:** UGL is a commodity pool issuing a K-1. Its futures gains are generally taxed 60% long-term / 40% short-term regardless of holding period, and K-1s complicate tax filing. Options:
   - (a) keep UGL and model its tax as 60/40 (an estimate, not tax advice);
   - (b) keep it but flag it, using your ordinary-income assumption;
   - (c) drop UGL and use GLD only.
   I recommend (a) for the backtest, with the K-1 hassle noted for Phase 8.
3. **State tax (example: Ohio):** Ohio taxable income up to $26,050 is taxed at 0%; above that, the marginal rate is 2.75% (S49). The project uses 2.75% as an **example default**, since it is the marginal rate above the threshold. Change it for your situation.
4. **TQQQ expense ratio:** ProShares shows gross 0.94% / net 0.78% with a waiver dated through 2026-09-30, which may have lapsed. I propose using the **gross 0.94%** (conservative) unless you prefer net.

## Frozen strategy list (approved 2026-10-22)

Decisions:
- P1 approved (6 variants).
- P2 approved (8 variants).
- P3 approved, restricted to SPY/QQQ and UPRO/TQQQ.
- Strategy 4 (plain RSI(2)) is restricted the same way.

| Group | Variants |
|---|---|
| S2 trend (N = 50/100/200; 4 ETFs; 1x and leveraged) | 24 |
| S3 time-series momentum (3/6/12 months; 4 ETFs; 1x and leveraged) | 24 |
| S4 RSI(2) (5/10/15; SPY, QQQ; 1x and leveraged) | 12 |
| S5 rotation (3/6/12 months) | 3 |
| S6 leveraged rotation (3/6/12 months) | 3 |
| P1 volatility-gated leverage (15/20/25%; SPY→UPRO, QQQ→TQQQ) | 6 |
| P2 multi-asset trend (6/8/10/12 months; 1x and leveraged) | 8 |
| P3 RSI(2) with 200-day filter (5/10/15; SPY, QQQ; 1x and leveraged) | 12 |
| **Total trials (used in the Deflated Sharpe Ratio)** | **92** |

The 9 buy-and-hold benchmarks are not counted as trials. Every variant is pre-registered in `research_log.csv` with IDs V001–V092 (benchmarks B01–B09). No strategy, parameter or instrument may be added after this point.

Other decisions:
- UGL is taxed as 60% long-term / 40% short-term (futures treatment), and the final report flags that UGL issues a K-1.
- State tax: example default Ohio 2.75%; federal: example default 12% ordinary, 0% long-term. Change for your situation.
- TQQQ expense ratio: gross 0.94%.
- TMF's expense ratio must be confirmed from the prospectus or an SEC filing in Phase 2. If it can't be confirmed, stop and ask.
