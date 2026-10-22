# Can a $100 account reach $1,000 with simple ETF strategies? A pre-registered backtest study

_Final report. Data 2004-11-18 to 2023-12-29. The 2024 onward holdout was never opened. Last updated 2026-10-22._

## Verdict

**No.** I tested 92 pre-registered end-of-day strategies on gold, S&P 500, Nasdaq-100 and long Treasury ETFs and their 2x/3x leveraged versions, with realistic costs. **None survived the pre-agreed validation rules.** 13 of 92 had a better risk-adjusted return than a simple equal-weight portfolio of the four ETFs in the 2019–2023 out-of-sample period, but the best of them could be explained by luck from testing so many variants. Its Deflated Sharpe probability was 0.73, against the 0.95 required. The closest call, a monthly multi-asset trend filter, had a higher Sharpe ratio than the equal-weight portfolio (0.99 vs 0.81) but a lower return (10.3% vs 12.1% a year), with half the drawdown. That difference is not statistically reliable. Leveraged buy-and-hold raised returns in good years and lost 90%+ in bad ones (UPRO and TQQQ in 2008, TMF in 2020–2023). For a $100 account, monthly savings matter far more than strategy choice: $100 a month reaches $1,000 in 9 months. In the informational simulation, even the best near-miss took a median of about 11 years to get there from $100 alone. **The honest conclusion: nothing tested here beat a low-cost diversified index portfolio once overfitting was accounted for.**

## At a glance

| | |
|---|---|
| Question | Does any aggressive end-of-day strategy on 4 ETFs (+ leveraged versions) have a durable edge after costs? |
| Universe | GLD, SPY, QQQ, TLT; UGL (2x), UPRO, TQQQ, TMF (3x) |
| Data | Daily adjusted OHLC, 2004-11-18 to 2023-12-29 (Yahoo Finance); 3-month T-bill rate for cash |
| Design | 92 variants frozen before any backtest; in-sample 2006–2018, validation 2019–2023, holdout 2024+ (locked) |
| Statistics | Walk-forward, bootstrap confidence intervals, Deflated Sharpe Ratio (N = 92), 7 kill criteria |
| Result | **0 of 92 survive.** 5 near-misses failed only the Deflated Sharpe test |
| Engineering | Python, pandas/numpy/scipy; 57 unit tests; every run logged (764 rows in `research_log.csv`) |

## 1. What was tested

**Instruments.** Four unleveraged ETFs (GLD gold, SPY S&P 500, QQQ Nasdaq-100, TLT 20+ year Treasuries) and their leveraged counterparts (UGL 2x gold futures, UPRO/TQQQ/TMF 3x). Leveraged funds launched in 2008–2010. Before that I built synthetic daily series from the underlying ETF, the expense ratio, financing at the T-bill rate, and an extra cost calibrated on 2009–2018 overlap data.

**Strategies** (8 families, 92 variants; grids of 3–4 values, frozen in advance). Signals always come from the unleveraged ETF's close; positions can sit in the leveraged version.

| Family | Rule | Variants |
|---|---|---|
| S2 Trend | Hold when close > N-day moving average (N = 50/100/200), else cash | 24 |
| S3 Time-series momentum | Hold when the trailing 3/6/12-month return > 0 | 24 |
| S4 RSI(2) mean reversion | Buy when RSI(2) < 5/10/15, sell on a close above the 5-day average (SPY/QQQ) | 12 |
| S5 Rotation | Monthly: hold the single best 3/6/12-month performer, cash if all negative | 3 |
| S6 Leveraged rotation | Same as S5, held in the leveraged version | 3 |
| P1 Volatility-gated leverage | Above 200-day average: 3x if 20-day volatility < 15/20/25%, else 1x; below: cash | 6 |
| P2 Multi-asset trend | Monthly: 25% in each ETF above its 6/8/10/12-month average, rest cash | 8 |
| P3 RSI(2) with trend filter | S4 plus close > 200-day average | 12 |

P1–P3 came from a literature review of 49 sources (Gayed & Bilello 2016; Avellaneda & Zhang 2010; Faber 2007; Baltussen et al. 2019). They were approved before any backtest.

**Benchmarks:** buy-and-hold of each of the 8 ETFs, and an equal-weight portfolio of GLD/SPY/QQQ/TLT rebalanced monthly.

## 2. How it was tested

- **No lookahead:** signals use data up to the close; trades fill at the next day's open. A unit test changes future prices and confirms that past signals, trades and equity are unchanged.
- **Costs:** half-spread 0.02% (unleveraged) or 0.05% (leveraged), plus 0.05% slippage, on every fill; $0 commission; fractional shares; $1 minimum order. Uninvested cash earns the T-bill rate. Every result was rerun at 2x and 3x costs.
- **Engine check:** buy-and-hold CAGR and max drawdown from the backtester match a direct pandas calculation to 2 decimals for all 9 benchmarks. A hand-calculated trade matches the engine on every cost line.
- **Splits:** in-sample 2006–2018 (tuning only), validation 2019–2023 (selection only), holdout 2024+ (never opened, never downloaded).
- **Walk-forward:** each year from 2011 to 2023, pick the parameter with the best Sharpe over the prior 5 years and use it the following year.
- **Multiple testing:** the Deflated Sharpe Ratio (Bailey & López de Prado 2014) gives the probability that a strategy's true Sharpe beats the best result expected by chance from 92 trials. Bootstrap 95% confidence intervals use 10,000 resamples with a fixed seed.
- **Kill criteria, applied mechanically.** A strategy dies if it fails any one:
  - K1: it doesn't beat both its own buy-and-hold and equal weight out of sample;
  - K2: Deflated Sharpe probability below 0.95;
  - K3: profitable at 1x costs but not at 2x;
  - K4: fewer than 30 trades (monthly strategies need 5 years of out-of-sample data instead);
  - K5: a neighboring parameter value fails;
  - K6: out-of-sample Sharpe below half of in-sample;
  - K7: $100 falls to $20 in 2008, the 2020 crash or 2022.

## 3. Results

![Equity curves](final_equity_curves.png)

**Full period, in dollars:** from $100 in January 2006, the four 1x near-misses ended 2023 with $355–$428, **less than** buy-and-hold equal weight ($530) or SPY ($529). Their advantage is smoother returns and smaller drawdowns, not more money. The leveraged version (V074) ended with $2224, with a 35% worst drawdown on the way.

**Out of sample (2019–2023):**
- 13 of 92 trials beat equal weight's Sharpe (0.81); 9 also beat buy-and-hold of their own instrument.
- In walk-forward (2011–2023), 1 of 30 strategy groups beat equal weight.
- **No trial reached a Deflated Sharpe probability of 0.95.**

| Best 5 out of sample | Validation Sharpe | 95% CI | Deflated Sharpe (N=92) | Validation CAGR | Max drawdown |
|---|---|---|---|---|---|
| V073 P2 sma_months=6 | 0.99 | [0.13, 1.92] | 0.73 | 10.3% | -11.6% |
| V079 P2 sma_months=12 | 0.96 | [0.06, 1.86] | 0.70 | 9.9% | -11.5% |
| V075 P2 sma_months=8 | 0.93 | [0.05, 1.84] | 0.68 | 9.8% | -11.5% |
| V074 P2 sma_months=6 | 0.91 | [0.00, 1.82] | 0.67 | 22.4% | -32.5% |
| V021 S2 N=200 | 0.90 | [0.02, 1.81] | 0.66 | 17.6% | -23.3% |
| Equal weight (benchmark) | 0.81 | | | 12.0% | -25.6% |
| SPY (benchmark) | 0.72 | | | 15.8% | -33.7% |

### Kill table

![Kill matrix](final_kill_matrix.png)

| Criterion | Trials failing |
|---|---|
| K1 beats own B&H and EW | 83 |
| K2 DSR >= 0.95 | 92 |
| K3 survives 2x costs | 4 |
| K4 enough trades | 39 |
| K5 neighbors also work | 86 |
| K6 OOS >= half of IS | 12 |
| K7 no $20 ruin in stress | 0 |

Full per-trial reasons: [`kill_table.md`](kill_table.md).

### Why everything failed

1. **The required edge was too large for the data.** Five years of daily returns give a Sharpe ratio a standard error of roughly ±0.45. With 92 trials, the best result expected from pure noise is a Sharpe of about 0.71. The best real result (0.99) clears that, but not by enough to be 95% confident.
2. **Single-ETF timing rules mostly reduce risk; they don't add return.** Trend filters on one ETF usually lagged buy-and-hold on Sharpe (S2 median in-sample Sharpe 0.26 vs SPY 0.42), consistent with the academic literature (Zakamulin 2015; Huang et al. 2020).
3. **Results were fragile.** 86 of 92 trials also failed the neighbor test: a nearby parameter value didn't hold up out of sample. The edge, where it appeared, depended on the exact setting.
4. **Costs hurt the active strategies.** The RSI(2) family turns its account over 11–32 times a year; at 3x costs its Sharpe fell by up to 0.41.
5. **Diversification was the hidden winner.** The equal-weight portfolio of four uncorrelated-ish assets had a Sharpe of 0.81, higher than SPY's 0.72, with no rules at all. The near-miss P2 strategies are essentially that portfolio plus a trend filter.

## 4. Informational Monte Carlo — NOT VALIDATED, FAILED DSR

> Every strategy below was **killed**. This section answers "what if?" for illustration only. It replays 2019–2023 daily returns in random 20-day blocks (10,000 paths, 30-year horizon). It assumes the future looks like a strong stock market. Not a recommendation.

Chance that $100 reaches $1,000 before falling to $20, and median years to $1,000 (no monthly additions):

| Series | 20% invested | 50% invested | 100% invested |
|---|---|---|---|
| V073 P2 6-month 1x | 0%, over 30 yrs | 1%, over 30 yrs | 94%, 23 yrs |
| V074 P2 6-month leveraged | 2%, over 30 yrs | 98%, 19 yrs | 100%, 11 yrs |
| Equal weight (benchmark) | 0%, over 30 yrs | 28%, over 30 yrs | 95%, 20 yrs |
| SPY buy-and-hold (benchmark) | 0%, over 30 yrs | 78%, 26 yrs | 98%, 15 yrs |
| UPRO buy-and-hold (benchmark) | 85%, 23 yrs | 98%, 11 yrs; 1% hit $20 first | 82%, 7 yrs; 18% hit $20 first |

With **$50 or $100 added per month**, every series reaches $1,000 in roughly 0.7–1.4 years, mainly because of the deposits. Details: [`INFORMATIONAL_phase7a_monte_carlo.md`](INFORMATIONAL_phase7a_monte_carlo.md).

## 5. Limitations

- **Single data source.** All prices come from Yahoo Finance via yfinance (downloaded 2026-10-22). The planned cross-check against Stooq was impossible: its download now sits behind a bot-verification page. Two suspected stale-price stretches (QQQ Aug 27–29 2012; UGL May 18–22 2018) remain unresolved. Rerunning all 92 trials with those days interpolated changed no conclusion (in-sample Sharpe moved by at most 0.016; validation not at all).
- **Synthetic leveraged history before 2008–2010.** UGL, UPRO, TQQQ and TMF did not exist in 2004–2008, so their pre-launch history, including the 2008 crash, is modelled. After calibration the synthetic series track the real funds closely (correlation 0.996–0.999). In 2019–2023 they still differed by about a point a year: UGL optimistic (+1.5 pp/yr); UPRO optimistic (+1.2 pp/yr); TQQQ optimistic (+1.0 pp/yr); TMF pessimistic (-0.7 pp/yr). UGL tracks gold futures, not GLD, adding further tracking error.
- **Short validation window.** Five years (2019–2023) is too short to separate a modest edge from luck. That is the main reason the Deflated Sharpe test failed.
- **2019–2023 regime bias.** The validation period was strong for US large-cap tech (QQQ Sharpe 0.86) and historically bad for long Treasuries (TMF −18%/year, −92% drawdown). Rules that favored equities and avoided bonds look better than they likely are in general.
- **Model simplifications:** today's expense ratios applied to all history; fills at the open with fixed cost assumptions (no market impact; leveraged ETFs can gap more than 33% in a day); the Monte Carlo's constant position sizing ignores rebalancing costs. Taxes were not computed, because no strategy survived. If revisited: short-term gains are taxed as ordinary income (example rates in `config.yaml`: 12% federal + 2.75% Ohio; change for your situation), and **UGL issues a K-1** (commodity pool; futures gains roughly 60% long-term / 40% short-term).
- **The holdout (2024 onward) was deliberately left unopened.** It remains a clean test set for a future, separately pre-registered study.

## 6. What a future study would need to do differently

1. **Test far fewer ideas, chosen more carefully.** The Deflated Sharpe hurdle grows with the number of trials. A study of 5–10 variants motivated by economics would need a much smaller edge to pass.
2. **Use longer out-of-sample evidence.** Use futures or index data back to the 1970s (or earlier) for the underlying markets, so validation spans several regimes, including inflation-driven bond bear markets.
3. **Diversify across many markets, not 4 ETFs.** The trend-following evidence that holds up (e.g. Hurst, Ooi & Pedersen 2017) comes from 50+ futures markets with volatility scaling, not single-asset timing.
4. **Get a second, independent data source** (e.g. issuer NAV histories or a licensed vendor) and resolve data anomalies before testing.
5. **Pre-register the holdout test now:** if a new, independently motivated strategy is defined, run it once on 2024 onward and accept the result.
6. **Treat contributions as the main lever for small accounts.** At $100, saving rate and diversification dominate any timing rule tested here.

## Reproducibility

- **Code:** `src/` (data, engine, strategies, metrics, validation, risk); `tools/` (each phase's runner and report); `tests/` (57 tests: lookahead, costs, cash interest, adjusted prices, the $1,000 switch, synthetic formula, kill rules, Monte Carlo).
- **Records:** `research_log.csv` logs every run, including failures; `config.yaml` holds every parameter; `PROGRESS.md` holds the decision history; `AUDIT.md` holds the third-party code audit.
- **Environment:** seed 20261022. Python 3.14.8, pandas 3.1.0, numpy 2.5.4. Data hashes are in `data/raw/download_meta.json`.

_This is a research exercise, not financial or tax advice._
