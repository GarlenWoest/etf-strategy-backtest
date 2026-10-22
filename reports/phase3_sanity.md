# Phase 3 sanity check (in-sample only)

_Window 2004-11-18 to 2018-12-31 (3553 trading days, 14.12 years). Risk layer off: the $1,000 switch would otherwise cap positions once a $100 account passed $1,000. Python 3.14.8, pandas 3.1.0, numpy 2.5.4, seed 20261022 (not used)._

**Method:**
- **Direct:** read straight from `data/clean/prices/*.csv` with pandas: $1 bought at the open of 2004-11-19 (first fill after the 2004-11-18 close), marked at each close. The equal-weight portfolio is rebalanced to 25% each at the open after every month's last trading day. Computed independently of `src/engine.py` and `src/metrics.py`.
- **Engine (no costs):** `run_backtest` with half-spread, slippage and the $1 minimum order set to 0. The only difference from Direct is one night of T-bill interest on the starting cash before the first fill.
- **Engine (1x costs):** the normal configuration (costs and the $1 minimum order), shown for information.

| Instrument | Data | CAGR direct | CAGR engine (no costs) | CAGR engine (1x costs) | Max DD direct | Max DD engine (no costs) | Max DD engine (1x costs) |
|---|---|---|---|---|---|---|---|
| GLD | real | 7.36% | 7.36% | 7.36% | -45.56% | -45.56% | -45.56% |
| SPY | real | 7.58% | 7.58% | 7.57% | -55.19% | -55.19% | -55.19% |
| QQQ | real | 11.16% | 11.16% | 11.16% | -53.40% | -53.40% | -53.40% |
| TLT | real | 5.86% | 5.86% | 5.85% | -26.59% | -26.59% | -26.59% |
| UGL | synthetic to 2008-12-03, then real | 7.77% | 7.77% | 7.76% | -75.93% | -75.93% | -75.93% |
| UPRO | synthetic to 2009-06-25, then real | 7.54% | 7.54% | 7.54% | -95.54% | -95.54% | -95.54% |
| TQQQ | synthetic to 2010-02-11, then real | 16.62% | 16.62% | 16.62% | -94.60% | -94.60% | -94.60% |
| TMF | synthetic to 2009-04-16, then real | 6.93% | 6.93% | 6.92% | -67.22% | -67.22% | -67.22% |
| EW 4 (monthly) | real | 8.93% | 8.93% | 8.92% | -26.58% | -26.58% | -26.44% |

**Largest gap, direct vs engine (no costs): CAGR 0.00068 percentage points, max drawdown 0.00000 percentage points. Match at 2-decimal rounding on every row: YES.**

**Effect of the $1 minimum order (equal weight, no costs):** with the minimum on, the engine skips rebalance trades under $1, which is about half of them on a $100 account (352 trades vs 724 without the minimum). Weights drift between rebalances, giving CAGR 8.95% and max drawdown -26.42% instead of 8.93% and -26.58%. This is the realistic behavior of a $100 account, not an engine error. The 1x-costs column includes it.

Leveraged ETFs use the spliced clean series: synthetic (with calibrated extra cost) before launch, real after. These are not trial results. They are benchmarks, and in-sample only.

## Hand-checked trade: first SPY buy (1x costs)

Signal: buy-and-hold target 100% SPY, decided at the close of 2004-11-18. Executed at the open of 2004-11-19.

| Line | By hand | Engine |
|---|---|---|
| Starting cash | $100.000000 | |
| Overnight T-bill interest: rate(2004-11-18) = IRX 2.087% / 100 / 252 = 0.00008282 | +$0.008282 | |
| cash at open | 100.008282 | 100.008282 |
| exec price | 79.576583 | 79.576583 |
| shares | 1.256755 | 1.256755 |
| notional at open | 99.938325 | 99.938325 |
| half-spread $ | 0.019988 | 0.019988 |
| slippage $ | 0.049969 | 0.049969 |
| commission $ | 0.000000 | 0.000000 |
| total paid | 100.008282 | 100.008282 |

Arithmetic:
- Open = 79.520918 (adjusted). Cost rate = half-spread 0.02% + slippage 0.05% = 0.07%.
- Execution price = 79.520918 × 1.0007 = 79.576583.
- Shares = 100.008282 / 79.576583 = 1.256755 (fractional).
- Half-spread cost = shares × open × 0.0002 = $0.019988. Slippage = shares × open × 0.0005 = $0.049969. Commission = $0.
- Check: notional + half-spread + slippage + commission = $100.008282 = cash spent.
- Cash after the fill: $0.000000.

**Sell side (from the equal-weight run):** 2005-02-01 sold 0.029180 TLT at open 45.034346. Execution price = open × (1 − 0.0007) = 45.002822 (engine 45.002822). Half-spread $0.000263, slippage $0.000657, commission $0, net proceeds $1.313164.

Hand calculation equals the engine record on every line: **yes**.
