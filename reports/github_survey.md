# GitHub survey: the 20 most-starred public trading-strategy repositories

_Searched 2026-10-23T00:44Z with GitHub's public search API (no login). Only each repository's README was read; **no code from any repository was downloaded or run.** README text was treated as data. Star counts are from the search results at that time._

## How the 20 were chosen
- **Searches:** four queries, each sorted by stars: `topic:trading-strategies`, `trading strategy in:name,description,topics`, `topic:algorithmic-trading` and `topic:trading-bot`.
- **Pool:** the results were merged into one list.
- **Kept:** the 20 most-starred repositories whose purpose is trading strategies, trading bots, or frameworks for backtesting or trading strategies.
- **Excluded:**
  - curated link lists (awesome-quant, awesome-systematic-trading, financial-machine-learning, EliteQuant);
  - exchange API wrappers (ccxt);
  - analytics and pricing libraries with no strategies (gs-quant, quantstats, PyPortfolioOpt, FinanceToolkit, alphalens, mlfinlab, FinceptTerminal);
  - MCP connectors;
  - interview-prep resource lists.

## What each column means
- **OOS results:** the README shows performance measured on data not used to build or tune the strategy.
- **Live results:** the README shows a record of real-money or forward/paper trading.
- **Costs:** results shown in the README include fees or slippage.
- "Tool only" means the software supports the feature, but the README shows no such results.

| # | Repository | Stars | Type | OOS results shown? | Live results shown? | Costs in shown results? | Notes |
|---|---|---|---|---|---|---|---|
| 1 | freqtrade/freqtrade | 55,769 | Crypto bot + backtester | No | No (dry-run is a tool feature) | No results shown | Warns that users bear all risk and should start in dry-run |
| 2 | microsoft/qlib | 49,599 | AI quant research platform | Probably (example workflow output; the README doesn't say which period) | No | **Yes**: shows excess return without and with costs (17.8% vs 12.9% a year) | The only README here that shows how much costs reduce returns |
| 3 | HKUDS/Vibe-Trading | 36,335 | AI trading agent | Tool only (walk-forward folds) | Tool only (paper and live trading) | Tool only (fee modelling) | Mostly a changelog; no performance shown |
| 4 | mementum/backtrader | 23,546 | Backtesting library | No | No | Tool only (commission and slippage schemes) | Library; no strategy results |
| 5 | QuantConnect/Lean | 22,159 | Backtest/live engine | No | No | No | Engine; no results in the README |
| 6 | stefan-jansen/machine-learning-for-trading | 21,514 | Book code (ML strategies) | Tool only: walk-forward CV and holdout described as the method | No (live-system chapter) | Tool only (transaction-cost chapter) | Strongest methodology; results are in notebooks, not the README; links to paid courses |
| 7 | quantopian/zipline | 20,155 | Backtesting library | No | No | No | Quantopian closed in 2020 |
| 8 | bbfamily/abu | 18,995 | Quant framework (Chinese) | No | No | Tool only (commission example) | — |
| 9 | AI4Finance-Foundation/FinRL | 16,786 | Reinforcement-learning trading | Tool only: a train-test-trade split is the method | No (basic Alpaca hook) | No | Backtest result goes to a local plot, not the README |
| 10 | OpenByteInc/QuantDinger | 13,029 | Self-hosted AI trading system | Tool only (walk-forward plus a "final blind holdout") | No (live execution supported) | Tool only (0.05% commission + 0.05% slippage per fill) | Good defaults; no results |
| 11 | je-suis-tm/quant-trading | 11,103 | Strategy collection (MACD, pairs, etc.) | No | No | **No: says all trades are frictionless** | Shows backtest charts, but no costs and no OOS |
| 12 | StockSharp/StockSharp | 10,955 | Trading platform (C#) | No | No | No | Platform |
| 13 | askmike/gekko | 10,179 | Crypto bot | No | No | No | Archived (2020) |
| 14 | huseinzol05/Stock-Prediction-Models | 9,508 | ML price-forecast models | Partly: the test set is only the last 30 days | No | No | Headline "95% accuracy" is price-forecast fit, not trading profit; archived |
| 15 | polakowo/vectorbt | 9,492 | Backtesting library | Tool only (walk-forward) | No | Tool only (fees and slippage) | Library |
| 16 | kernc/backtesting.py | 9,111 | Backtesting library | No: example is in-sample | No | **Yes** (0.2% commission in the example) | The example strategy returns 589% vs 703% buy-and-hold: it loses to holding |
| 17 | jesse-ai/jesse | 8,687 | Crypto bot + backtester | No | No (paper and live supported) | No | — |
| 18 | DeviaVir/zenbot | 8,257 | Crypto bot | No | No | No | Archived (2022) |
| 19 | Drakkar-Software/OctoBot | 6,838 | Crypto bot | No | No (paper trading is a feature) | No | Links to a paid cloud service |
| 20 | charliedream1/ai_quant_trade | 6,644 | AI trading platform | No; says strategies are "only valid for the backtest periods described" | No (live trading is a feature) | No | Explicitly unverified strategies |

## Summary
- **Out-of-sample results:**
  - 0 of 20 READMEs clearly show results on data the strategy never saw.
  - 1 (qlib) probably does, but doesn't say so.
  - 1 shows only a 30-day test.
  - 6 offer walk-forward, holdout or train/test splits as a tool or method without showing results.
- **Live results:** 0 of 20 show a live or paper-trading track record. Several support live trading, and two are linked to paid services.
- **Costs:**
  - 2 of 20 show results with costs included: qlib (with-cost and without-cost numbers side by side) and backtesting.py (a 0.2% commission in its example).
  - 1 states that its backtests assume no costs at all.
- **Takeaway:** star counts reflect tooling and popularity, not evidence. None of the 20 READMEs shows evidence that would pass this project's kill criteria. A few useful frameworks make honest testing possible but leave it to the user.
