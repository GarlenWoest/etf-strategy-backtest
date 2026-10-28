# Phase B: read-only current-market intelligence (2026-10-28)

_Plain Python, no LLM calls, no orders, no broker. Code: `src/market_intel.py` (logic) and `tools/market_intel.py` (`snapshot`, `verify`). Thresholds: `config.yaml market_intel`. Output: `live/intel/` (private, git-ignored); an aggregate-only accuracy report in `reports/market_intel/`. Tests: `tests/test_market_intel.py` (13). No vendor quotes appear in this report._

## 1. What each observation carries

Every observation records:
- the source, symbol and quote type ("indicative last price, not executable", "ETF last trade", "futures, 10-min delayed");
- the source timestamp (UTC), retrieval timestamp (UTC) and the source's own time zone;
- its age, the expected update interval and any delay the source declares;
- whether its market session is open;
- a **freshness status**.

**Freshness statuses:**

| Status | Meaning (thresholds in `config.yaml`) |
|---|---|
| LIVE | Market open and the source timestamp is ≤ 180 s old (no declared delay) |
| DELAYED | Market open and ≤ 20 min old, or the source declares a delay (COMEX via Yahoo: 10 min) |
| CLOSED_LAST_PRICE | Market closed, and the last price is from within 15 min before the close (FX: Fri 17:00 NY; NYSE: 16:00 ET; CME metals: 17:00 ET) |
| CURRENT | An official daily or weekly reference within its maximum age (ECB 4 days; Fed H.10 12 days, as it's published weekly) |
| STALE | Anything older. **Never treated as current.** |
| UNAVAILABLE | No value, no timestamp, or a timestamp in the future |

**Each specialist gets one of three verdicts:**
- **DATA OK:** the primary price is fresh and 20-day volatility could be computed from completed daily bars.
- **STALE MARKET DATA:** the primary price is stale.
- **INSUFFICIENT DATA:** anything else.

**What LIVE does and doesn't mean:** it describes the age of the source's own timestamp. It does **not** prove the source is close to the real market. Yahoo's latency is not measured, because there's no executable reference to measure it against.

## 2. Instruments, and how gold is defined

| Specialist | Primary instrument | What it is | Not used, and why |
|---|---|---|---|
| USD/JPY | Yahoo `JPY=X` last price | Indicative, unofficial client; **not executable** | Yahoo bid/ask: **rejected**. On 10-28 the last price lay outside bid/ask by more than 0.10%. |
| GBP/USD | Yahoo `GBPUSD=X` last price | Same | Yahoo bid/ask: **rejected**. On 10-28 the bid was above the ask. |
| Gold | **GLD** (NYSE Arca), the gold ledger's existing vehicle | ETF trade price per share; tracks gold less fees; trades 09:30–16:00 ET only | — |
| Gold (context) | COMEX gold futures `GC=F` (front contract) | Exchange futures, USD per ounce; nearly 24-hour trading; differs from spot by the basis and jumps at contract rolls; Yahoo declares a 10-minute delay | Never mixed with GLD as if identical |
| Gold | XAU/USD spot | **Unavailable:** no licensed free source (LBMA prices need an IBA licence) | Never inferred from GLD or GC=F |

## 3. Latest snapshot (2026-10-28, 17:59 UTC = 13:59 New York)

- **FX:** market open; New York session active.
- **Primary prices:** USD/JPY LIVE (1 s old), GBP/USD LIVE (35 s), GLD LIVE (0 s); GC=F DELAYED (600 s, 10-min declared delay).
- **All three specialists: DATA OK.**
- **20-day realised volatility** (estimate from completed daily bars through 10-27): USD/JPY 5.0%, GBP/USD 4.8%, GLD 17.3%, GC=F 15.7%.
- **Official references:**
  - ECB 10-28 cross rates: USD/JPY 157.963 (±1.2 pips from rounding), GBP/USD 1.32876 (±0.7 pips), CURRENT.
  - Fed H.10 10-23 noon New York: USD/JPY 156.87 and GBP/USD 1.3375. CURRENT, 5 days old: it's published weekly, so never a current price.
- **Idempotence:** three runs today wrote 12 observation lines; repeats are skipped by key.

## 4. Independent accuracy check (`reports/market_intel/accuracy_2026-10-28.md`)

Yahoo's 1-minute prices for the last 7 days were compared with official references **at the references' documented times**. The price used is the close of the 1-minute bar ending exactly at the reference time; a later bar is never used (tested).

| Market | Reference (documented time) | Days compared | Median abs diff | Max abs diff | Reference's own rounding |
|---|---|---|---|---|---|
| USD/JPY | ECB cross (~14:10 CET) | 7 of 7 | 0.82 pips | 2.10 pips | ±1.2 pips |
| USD/JPY | Fed H.10 (12:00 New York) | 4 of 4 | 0.45 pips | 0.80 pips | ±0.5 pips |
| GBP/USD | ECB cross (~14:10 CET) | 7 of 7 | 1.18 pips | 1.66 pips | ±0.7 pips |
| GBP/USD | Fed H.10 (12:00 New York) | 4 of 4 | 0.55 pips | 3.58 pips | ±0.5 pips |

**Other measures:**
- **Coverage:** minutes with no Yahoo bar during FX market hours: USD/JPY 185 of 9,777 (1.89%); GBP/USD 199 of 9,777 (2.04%).
- **Outliers:** one-minute moves over 10 robust σ: 0 (USD/JPY), 2 (GBP/USD), not yet explained.
- **Volatility cross-check:** the 20-day estimate is 4.3% from ECB fixes vs 5.0% from Yahoo (USD/JPY), and 4.6% vs 4.8% (GBP/USD). They agree in size; part of the gap is that they're measured at different times of day.

**What this shows:** at 22 time-aligned moments over 7 days, Yahoo's indicative USD/JPY and GBP/USD prices agreed with two official references within 2.1 and 3.6 pips.

**What it can't show:**
- executable prices, spreads or slippage;
- accuracy between those moments;
- latency;
- anything for gold (no independent licensed reference for GLD or COMEX futures here).

It is **not** a percentage accuracy claim. The ECB time is approximate ("normally around 14:10 CET"), and H.10 rates are buying rates, not mid-market rates.

## 5. Licensing of the sources used

| Source | What we know | Status |
|---|---|---|
| Yahoo via yfinance | Unofficial client of a consumer website; Yahoo's terms were not re-read in this phase | **Uncertain.** Personal research only; values stay in `live/` and are never published |
| ECB reference rates | "for information purposes only"; using them for transactions is "strongly discouraged" (ECB page, read 10-28) | Fine for checking; not for trading |
| Fed H.10 via FRED CSV | Fed data, certified "for customs purposes"; FRED terms ask permission only for third-party copyrighted series | Fine for research and checking |
| Bank of England spot rates | Observation time **not documented** on the page read; LSEG content in them may not be redistributed | **Not used** |

## 6. Executable bid/ask needs a broker or a paid feed (decision for you)

Nothing was set up.

| Option | Cost | Login and credentials | Prices | Notes |
|---|---|---|---|---|
| OANDA v20 API, practice account | Free (third-party sources; signup terms vary by region) | Account and personal API token (you would hold it; rule 1 forbids me handling it) | OANDA's own bid/ask: executable at OANDA only | Documented practice endpoints (developer.oanda.com) |
| Interactive Brokers (IDEALPRO) | FX quotes need no extra subscription (IBKR docs); a funded account with about $500 is required for API data | Brokerage account, API acknowledgement, TWS or gateway running | IBKR's executable quotes | A real broker account: highest setup burden |
| Massive (formerly Polygon) Currencies Starter | $49/month (Massive docs) | Account and API key | Aggregated bid/ask, **not executable** | Free tier no longer has real-time FX |
| TrueFX real-time | $4,950–7,450/month | Account | Indicative (Integral) | Out of budget |
| Stay as is | $0 | none | Indicative last price only | Spreads and costs stay unverified |

## 7. How it could run regularly (decision for you; nothing scheduled)

| Option | Claude usage | Runs when | Approval needed because |
|---|---|---|---|
| A. macOS LaunchAgent runs the plain Python `snapshot` 3–4×/day | **None** (no LLM) | Mac awake and logged in; missed if asleep or off | It writes a file outside trading-research (`~/Library/LaunchAgents`), which is persistent configuration |
| B. Add `snapshot` to the existing weekday 16:45 task | Small: one extra command per run, 5 runs a week | Claude app open | It changes a scheduled task |
| C. A new Claude scheduled task 3×/day | 15 extra full sessions a week. Rough guide: the existing weekday session took 30 s to 3 min and about 77 transcript messages; I can't measure tokens exactly | Claude app open | New task, Claude usage |
| D. A cloud scheduler (e.g. GitHub Actions on the private repo) | None | Even when the Mac is off | External hosting; market data would leave the Mac |

**Recommendation:** A, or B to start. Neither is truly unattended: if the Mac sleeps, nothing runs, and the report says so through the freshness statuses.

## 8. Isolation from research

- Tests assert that no research module or tool imports `market_intel` or reads `live/`. The only exception is `src/memory.py`, which merely defines the private forecast-ledger path.
- The writers refuse any path outside `live/intel/` and `reports/market_intel/`.
- Current data is from 2026, inside the locked 2024+ holdout period. It is monitoring data and never enters `data/`, `research_log.csv` or any study.

## 9. Not done in Phase B (by design)

- Economic events (Phase C). The FOMC meeting of **October 27–28, 2026** was verified on federalreserve.gov's calendar; the release time isn't on that page and is not claimed here.
- News, trend assessments and the full daily report (Phase I).
- Any forecast or signal.
