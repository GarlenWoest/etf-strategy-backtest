# USD/JPY trading-intelligence pipeline: design (draft v0.1, 2026-10-28)

_Design only. Nothing here is built, scheduled or connected. No broker, no orders, no credentials. Every output is labelled **EXPERIMENTAL SHADOW SIGNAL, not financial advice**. The candidate rules and risk limits are in `research/USDJPY_CANDIDATES_v0.1.md`; the broker options in `reports/paper_broker_options.md`._

## 1. Purpose and boundaries

The pipeline turns **today's** verified market state into one of two outputs per rule: a candidate trade or an explicit NO TRADE. A deterministic risk gate checks it, a fictional paper adapter records it, and it is scored later against what actually happened. It measures prospective, out-of-sample behaviour. It is **not** a backtest and **not** an execution system.

**Boundaries kept from the existing project:**
- **Monitoring side only.** It reads `live/` data from 2026, which is inside the locked holdout period, so nothing it produces may enter `data/`, `research_log.csv`, model fitting or strategy selection. The existing isolation tests are extended to cover the new package.
- **No new trials.** Shadow signals aren't pre-registered trials, don't change the cumulative N of 142, and can't validate anything. Any rule that later deserves a historical test must be pre-registered separately and counted in N.
- **Plain Python and deterministic.** There are no model calls in the loop. Claude may write commentary, but never decides an entry, exit or size.
- **One market:** USD/JPY. Gold and GBP/USD stay in monitoring mode. The design is written so a second specialist could reuse it later, but none is planned.

## 2. Data flow

```
 weekday run 16:45 ET (existing task, new step)
        |
 [1] MARKET STATE  <- market_intel snapshot (live/intel/latest.json) + completed daily bars
        |             + events (live/events/events.json) + clock (sessions, holidays, rollover)
        |             -> MarketState (every field carries source, timestamp, freshness)
        v
 [2] RULES v0.1    pure functions: rule(state) -> Candidate | NoTrade(reason)
        |             each rule versioned; parameters frozen in config before first use
        v
 [3] RISK GATE     deterministic checks (stale data, event blackout, exposure, loss limits,
        |             drawdown halt, integrity) -> APPROVED | BLOCKED(reasons)
        v
 [4] PAPER ADAPTER internal simulator (default): fills at the next fresh snapshot price
        |             +/- the cost model; accounting identical to fx_engine_v2 (currency balances,
        |             costs, hard 1x cap). Optional later: read-only OANDA practice pricing as a quote check
        v
 [5] REGISTRY      append-only, hash-chained JSONL: state digest, signal, gate decision,
        |             fills, exits (live/usdjpy/). Never edited; outcomes are separate records
        v
 [6] SCORING       at exit or expiry: realised return after costs and financing,
        |             vs baselines (flat, always-long, simple trend); NOTIFY only on resolution
        v
 [7] DASHBOARD     live/usdjpy/dashboard.md: open positions, exposure, limits used,
                      resolved results, "fewer than 30 resolved: not meaningful"
```

**Rhythm.** The rules in v0.1 are daily (decided on completed daily bars), so one evaluation per weekday run is enough. Nothing intraday is attempted: the scheduler only runs while the Mac is awake and the app is open, and HistData intraday use is blocked.

## 3. File layout (proposed; none exists yet)

| Path | Contents | Git |
|---|---|---|
| `src/live_usdjpy/state.py` | Builds `MarketState` from the existing modules; no network code of its own | tracked |
| `src/live_usdjpy/rules_v0_1.py` | The candidate rules as pure functions; version string in every output | tracked |
| `src/live_usdjpy/risk_gate.py` | Deterministic limit checks; returns every reason, not only the first | tracked |
| `src/live_usdjpy/paper.py` | Internal simulator ledger (incremental; same identities as fx_engine_v2) | tracked |
| `src/live_usdjpy/registry.py` | Hash-chained append-only store, shared with the trade-ideas plan | tracked |
| `src/live_usdjpy/scoring.py` | Outcomes, baselines, scorecard tables | tracked |
| `tools/usdjpy_pipeline.py` | CLI: `evaluate`, `score`, `dashboard`, `verify` | tracked |
| `config.yaml` `live_usdjpy:` | Rule parameters, cost model, risk limits (frozen before first use) | tracked |
| `live/usdjpy/registry.jsonl`, `outcomes.jsonl`, `ledger.json`, `dashboard.md` | Monitoring records | ignored; private backup only |
| `tests/test_live_usdjpy_*.py` | Rules, gate, adapter parity, registry tamper, scoring, isolation | tracked |

## 4. Module boundaries and reuse

| Existing component | Reused for | How |
|---|---|---|
| `src/market_intel.py` + `tools/market_intel.py` | Entry and mark prices; freshness | `state.py` reads `live/intel/latest.json` and uses `freshness_intraday()`, `freshness_daily_close()`, `realized_vol()`. A price that isn't LIVE or DELAYED is never used for an entry |
| `src/events.py` + `live/events/events.json` | Event blackout windows; context | `upcoming()` gives scheduled events; the gate blocks entries inside blackout windows. Events without a published time (BoJ) block the whole Tokyo day |
| `src/clock.py` | Trading days, sessions, rollover | `fx_market_open()`, `fx_trade_date()`, `rollover_days()` (triple rollover), `jp_bank_holidays()` / `us_board_holidays()` for expiry counting |
| `src/fx_engine_v2.py` | Accounting reference | The paper ledger uses the same balance identities. A daily **parity check** replays the ledger's target path through `run_balance()` and requires equity to agree within a stated tolerance; any difference is reported, not hidden |
| `tools/heartbeat.py` | Run and step records | New step name `usdjpy`; notification delivery recorded as today |
| `src/memory.py` (`Ledger`) | Hash-chain method | `registry.py` uses the same SHA-256 chaining, as a separate store (research memory and monitoring records never mix) |
| `src/knowledge.py` | Evidence shown beside each signal | Read-only lookups with reading depth (L0–L3) attached |
| `tools/backup_private.py` | Backup | `live/usdjpy/` is already inside the `live/` allowlist; no change needed |

**Dependency rule:** research code (`src/engine*`, `src/strategies*`, `src/specialists/`, studies) must never import `src/live_usdjpy/`; `src/live_usdjpy/` may import research utilities (clock, engine v2), never the reverse. This is enforced by a test.

## 5. Records and integrity

- **Every evaluation writes a record**, including NO TRADE and BLOCKED. A missing record therefore means the run didn't happen, and the heartbeat shows that.
- **Contents of each record:** a digest of the market state (prices, sources, timestamps, freshness); the rule version and parameter hash; the signal; the gate decision with all reasons; the planned fill; the record's SHA-256 chained to the previous record.
- **Fills and exits** are new records referencing the signal ID. Nothing is ever rewritten.
- **Writes** use a temporary file plus an atomic swap, per Phase B. The chain is verified at the start of every run; a break blocks new entries and raises an alert.
- **Idempotent:** a key of (rule, trade date) prevents duplicate signals if a run repeats.

## 6. Scoring and baselines

- **Exit reasons:** invalidation, target, expiry, gate-forced exit (for example a drawdown halt).
- **Daily-bar evaluation.** If invalidation and target are both touched on the same day, it counts as invalidation. A gap through a level is filled at that day's open, not at the level.
- **Return after costs and financing:**
  - Costs: the one-way cost (config default 0.015%, unverified), applied to entry and exit.
  - Financing: the US–Japan short-rate differential minus the 0.75%/yr markup, from the same rate stand-ins used by Study 4. It's labelled an estimate until broker swap data exists.
- **Baselines over the same window and size:** flat (0); always long USD/JPY; a simple trend rule (sign of price vs its 20-day average).
- **Reporting:** by rule, by session at entry, and with or without events in the window. Every table carries "Fewer than 30 resolved signals: nothing here is statistically meaningful."

## 7. What this design does not do

- No real-time or intraday trading.
- No broker connection: the OANDA practice option is a later, separately approved, read-only quote check.
- No automatic promotion of a rule. Moving from shadow signal to paper-trading candidate needs your explicit decision and a pre-registered historical test.
- No use of HistData intraday data.
- No consensus-based "surprise" measures: no licensed source exists.

## 8. Build order (after approval; after Phase B)

1. Registry with tamper tests.
2. `MarketState` with freshness tests.
3. Rules as pure functions, with hand-checked fixtures.
4. Risk gate, one test per limit.
5. Paper adapter plus the fx_engine_v2 parity test.
6. Scoring with hand-checked cases.
7. Dashboard.
8. Weekday-task step (diff shown first).

Each step gets its own tests and commit. Nothing runs on a schedule until you approve the task diff.
