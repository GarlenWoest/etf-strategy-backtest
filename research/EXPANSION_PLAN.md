# Expansion plan: gold, USD/JPY and GBP/USD specialists

_Phase 0 deliverable, written 2026-10-23. Audit, gap analysis and prioritized plan only. **Nothing has been implemented.** Every later phase waits for your approval._

**Status labels used below:**
- **verified (file):** read from this repository.
- **verified (web, date):** checked online this session.
- **UNVERIFIED:** from a secondary source or not yet checked.
- **UNKNOWN:** no evidence yet.

---

## 1. Summary

- **What exists:** the repository is a clean, tested, well-documented research system for **daily, long-only, unleveraged** strategies on ETFs and index data. Its central result stands and is not rewritten: **0 of 134 pre-registered strategies were validated** (92 ETF, 26 commodity, 16 long-history).
- **What the new goal needs:** gold, USD/JPY and GBP/USD specialists need four capabilities the current system doesn't have:
  - shorting, FX financing and spread modelling;
  - multi-time-zone session logic;
  - point-in-time macro and event data;
  - a structured, queryable research memory.

  All four can be added as modules without touching the locked research or the holdout.
- **Three constraints drive the plan:**
  1. **Gold has no clean validation data left.** Its 2019–2023 window has been used by Studies 1–3, and 6 gold-only strategy families (plus multi-asset families that held gold) are already killed. The only untouched gold data is the 2024+ holdout, which can be used once.
  2. **Free intraday FX/gold data with bid/ask before 2024 isn't available without logins, third-party downloaders or payment.** Yahoo's free intraday history covers only the last 7–730 days, which is entirely inside the locked holdout. So every time-of-day claim is **UNKNOWN** until you approve a data source.
  3. **$100 can't trade spot FX unleveraged at most US dealers.** A 1,000-unit micro lot is ~10–13x leverage. The plan proposes notional-capped paper ledgers instead (section 6).
- **Recommendation: activate USD/JPY first** (section 12). Keep gold and GBP/USD in research and monitoring mode.

## 2. Phase 0 audit

### 2.1 Baseline (verified this session, 2026-10-23)
| Check | Result |
|---|---|
| Unit tests | **90 passed** (`pytest tests`), 3 library deprecation warnings |
| Working tree | Clean; local `main` at `38e6e7c` |
| Public GitHub `main` | `92234a2` (last API check); local commits `953bcc9`, `28b98fe`, `38e6e7c` not pushed |
| `research_log.csv` | 1,045 rows, 17 columns; **134 unique PRE-REGISTERED trial IDs** (V001–V134); 0 duplicate (id, phase, cost, params, period) rows |
| Holdout | `config.yaml dates.holdout_locked: true`; no research file contains 2024+ rows; long-history originals deleted after truncation |
| Code size | `src/` + `tools/` ≈ 5,950 lines; 21 tools, 11 source modules, 12 test files |

### 2.2 Inventory and public/private boundary
| Area | Contents | Public? |
|---|---|---|
| `src/` | `data`, `engine` (daily, long-only, no margin), `strategies`, `metrics`, `risk`, `validate` (walk-forward, bootstrap, DSR, Monte Carlo), `commodities`, `longhist` | Yes |
| `tools/` | Phase runners, report generators, downloaders, monitoring (`brief_market_data`, `watchlist_signals`, `paper_books`, `heartbeat`, `backup_private`), `md_to_pdf` | Yes |
| `tests/` | 90 tests: no-lookahead, costs, engine, DSR, release lags, NYSE calendar, paper books, heartbeat, backup allowlist | Yes |
| `reports/`, `research/` | All reports, charts, 49 + 153 graded sources, idea pool | Yes |
| `data/` | ~28 MB of Yahoo, FRED, AQR, Ken French, Shiller and World Bank files, all before 2024 | No (two `.gitkeep` placeholders only) |
| `briefs/`, `live/`, `paper/` | Weekly brief, watchlist state, paper books; exempt from rule 2 for these folders only | No; private backup prepared, waiting on your repo and token |
| `SUMMARY.md/.pdf`, `.backup.git/`, `vendor/`, `.venv/`, `tmp/`, `results/` | Local only | No |

### 2.3 Scheduled tasks and their dependencies (verified from the task files)
| Task | Runs | Depends on | Writes |
|---|---|---|---|
| `watchlist-alerts` | Weekdays 16:45 ET | yfinance, `live/state.json`, NYSE calendar in `watchlist_signals.py` | `live/`, `paper/`, heartbeat |
| `weekly-market-brief` | Sundays 18:00 ET | `brief_market_data.py` (yfinance + FRED), web news, `paper_books.py`, `heartbeat.py`, `backup_private.py` | `briefs/`, the Book B journal through the script, backup |

**Dependency chain:** the watchlist writes `live/state.json`; Book A in `paper/` reads it; the brief reads the paper summary.

**Current state:**
- The paper books start 2026-10-26.
- The Book B journal is empty.
- `live/heartbeat.json` doesn't exist yet.

Any FX/gold expansion must leave this chain untouched.

### 2.4 Capability gaps in the existing code (verified by reading)
| Capability | Exists? | Detail |
|---|---|---|
| Daily backtest with next-open fills and costs | Yes | `src/engine.py` |
| Shorting | **No** | `long_only: true`; the engine refuses negative weights |
| Margin, leverage limits, FX financing/rollover | **No** | `margin: false`; cash earns T-bills only |
| Bid/ask spreads from data | **No** | Fixed half-spread and slippage parameters |
| Intraday bars, sessions, multiple time zones | **No** | Only an NYSE calendar (ET) in `watchlist_signals.py` |
| Japan/UK holidays, FX week (Sun 17:00–Fri 17:00 ET) | **No** | — |
| Point-in-time macro (vintages) | Partial | Release-lag rules for DFII10 and DTWEXBGS only; current vintage; revisions not modelled |
| Event database (scheduled releases, surprises) | **No** | — |
| Research library | Partial | CSV source lists with grades; no full-text search, no hypothesis linkage |
| Research memory | Partial | Append-only `research_log.csv`, `PROGRESS.md`, fingerprinted Book B journal; no forecast registry, no structured hypothesis store |
| Validation toolkit | Yes | Walk-forward, i.i.d. and block bootstrap, DSR with cumulative N, effective N, cost multipliers, kill criteria |
| ML pipeline | **No** | Deliberately absent so far |

### 2.5 Why Studies 1–3 failed (synthesis, from the reports)
1. **Too little clean data for the number of trials.** Five years of daily validation gives a Sharpe standard error of about ±0.45. With N in the hundreds, the luck level is about 0.7 Sharpe, so a modest real edge can't be distinguished from noise.
2. **Single-asset timing cuts risk, not return.** This held across ETFs (Study 1), commodities (Study 2) and 90 years of indexes (Study 3).
3. **Fragility.** 86 of 92 Study 1 trials failed the neighbour test. Study 3's passes vanished at 2x costs or with a one-month lag.
4. **One-off episodes.** Study 2's best result was carried by oil in 2021–2022.
5. **The literature's strongest effects are cross-sectional and diversified.** They work across 20–60 markets with volatility scaling, and they were proxied here with 3–4 instruments.

**Lesson carried into this plan:** a single FX pair or gold is a narrow universe. Hypotheses must be specific to that market (policy, intervention, rate differentials, scheduled events), not generic technical rules. The universe-size handicap must be stated up front.

### 2.6 Audit findings that need attention (no action taken)
- **Gold's validation window is spent:** 2019–2023 has been evaluated in all three studies, and any new gold test on it is contaminated.
- **Yahoo intraday history (1h ≤ 730 days, 1m ≤ 7 days) lies entirely in the 2024+ holdout.** Using it for research would breach rule 2.
- **FRED revisions aren't modelled.** ALFRED vintages would fix this; keyless access is UNVERIFIED, and an API key would be a credential that I can't handle.
- **Unpushed commits and a pending private backup.** Three local commits aren't on GitHub, and the private backup is waiting on your repo and token.

## 3. Gap analysis against the master instruction

| Phase | Requirement | Exists | Gap | Blocked by |
|---|---|---|---|---|
| 1 | Three specialists, one active | — | Registry, per-market config, folders, holdout policy | Your approval |
| 2 | Market clock (IANA, sessions, DST, holidays, rollover) | NYSE calendar only | Full clock module | None (stdlib `zoneinfo`); optional holiday package needs approval |
| 2 | Best and worst time windows by evidence | — | Intraday history with bid/ask before 2024 | **Data access** (section 7) |
| 3 | Citation-backed knowledge library | 202 graded sources in CSV | Schema, migration, search, evidence classes A–F, dedupe | None (stdlib `sqlite3` FTS5) |
| 4 | GitHub technology review | Earlier README survey (20 repos) | Deep review of 8+ candidates | Approval before running any code |
| 5 | Event and news intelligence, point-in-time | Release-lag rules for 2 series | Event DB, official calendars, vintages | Consensus forecasts are paid; ALFRED access UNVERIFIED |
| 6 | Persistent, immutable research memory | Log + journal fingerprints | Hypothesis, forecast and incident stores with a hash chain | None |
| 7 | Pre-registered market-specific hypotheses | Pre-registration practice exists | FX engine (short, financing, spread), new splits | Phases 1, 6; your split decision |
| 8 | Careful ML | — | Everything | Phase 7 baselines first |
| 9 | Decision report | Weekly brief (no decisions) | Per-specialist report; must say ABSTAIN / UNKNOWN | Phases 2, 5, 7 |
| 10 | Per-market paper ledgers | 4 ETF paper books | FX/gold ledgers with financing, margin, sessions | Phases 1, 7; your sizing decision |
| 11 | Daily, weekly and monthly monitoring | Weekday and Sunday tasks + heartbeat | Extend to FX hours and markets | Phase 10 |
| 12 | QA and adversarial tests | No-lookahead and release-lag tests | DST, holiday, closed-market, bad-fill, fake-headline tests | Built alongside each phase |

## 4. Already tested and killed: do not retest without a materially new hypothesis

**Cumulative trial count: N = 134.** The next trial ID is V135, and every new trial raises N.

| Family | Instruments | Trials | Study | Why it died |
|---|---|---|---|---|
| Price vs N-day SMA (50/100/200) | GLD, SPY, QQQ, TLT + 2x/3x | V001–V024 | 1 | K1, K2, K5; gold Sharpe 0.09–0.38 vs 0.56 buy-and-hold |
| Time-series momentum, 3/6/12 months (return > 0) | Same | V025–V048 | 1 | Same; gold 0.18–0.41 |
| RSI(2) mean reversion (± 200-day filter) | SPY, QQQ + 3x | V049–V060, V081–V092 | 1 | Costs, K1, K5 |
| Top-1 rotation (1x / leveraged) | GLD/SPY/QQQ/TLT | V061–V066 | 1 | K1, K5 |
| Volatility-gated leverage | SPY/UPRO, QQQ/TQQQ | V067–V072 | 1 | K1, K5 |
| Multi-asset trend, 6/8/10/12 months | 4 ETFs + leveraged | V073–V080 | 1 | DSR 0.67–0.73 < 0.95 (closest calls) |
| TSMOM basket vs T-bills | GLD/SLV/USO (+2x) | V093–V098 | 2 | K1, K2, K5 |
| Volatility-scaled EWMAC(16,64) trend | **Gold only** and basket | V099–V104 | 2 | K1, K2; gold Sharpe 0.13–0.17 |
| Dual momentum | GLD/SLV/USO (+2x) | V105–V110 | 2 | DSR ≤ 0.43; oil-driven |
| **Gold real-yield filter** (DFII10 20 vs 120/250) | GLD, UGL | V111–V114 | 2 | K1, K2; 0.16–0.49 vs 0.56 |
| **Gold dollar-trend filter** (DTWEXBGS vs SMA) | GLD, UGL | V115–V118 | 2 | K1, K2; −0.05 to 0.18 |
| Multi-asset trend, 90 years | Stocks/bonds/commodities/gold | V119–V122 | 3 | Failed every robustness check |
| Monthly TSMOM per asset, incl. **gold** | 4 index series | V123–V134 | 3 | Era rule / DSR |

**Researched but deliberately not tested** (weak or contrary evidence, or data not free), in `research/IDEA_POOL_COMMODITIES.md`:
- gold seasonality, the gold/silver ratio and the copper/gold ratio;
- GVZ volatility regimes and inflation regimes;
- carry and term structure, basis-momentum, hedging pressure (COT cross-section) and skewness.

**Not yet tested at all:** anything on USD/JPY or GBP/USD; intraday or session effects; event-reaction rules; FX carry. The only FX-related signal so far was the dollar index used as a gold filter.

**Gold-specific constraint:** a new gold hypothesis must be materially different, for example an event or policy mechanism rather than another price-trend variant. It also needs either untouched data (pre-2004 daily futures/spot, if obtainable, or the 2024+ holdout used once) or must be declared exploratory.

## 5. Proposed architecture (modular extension; nothing existing is modified)

```
src/clock.py               market clock: IANA zones, sessions, DST, holidays, rollover, weekend
src/specialists/           base.py + gold.py, usdjpy.py, gbpusd.py (status: active / monitoring)
src/fx_engine.py           new engine: long/short, spread from data or model, rollover financing,
                           notional cap; the existing src/engine.py stays untouched
src/library/               SQLite + FTS5 knowledge library (stdlib only), evidence classes A–F
src/memory/                append-only hypothesis, experiment, forecast and incident ledgers (hash-chained)
src/events/                official release calendars, release timestamps, point-in-time vintages
config.yaml                new top-level block `specialists:`; existing blocks unchanged
research/library/          bibliographic metadata (public); no copyrighted full texts
data/raw/fx/, data/raw/macro/, data/raw/events/   git-ignored, with holdout truncation as now
reports/specialists/<market>/   eligibility and window reports
```

**Principles:**
- **Existing guarantees carry over:** every new module gets no-lookahead and holdout tests.
- **Shared, preserved infrastructure:** the existing engine, studies, tasks and paper books are used by the specialists but never modified. New engines and ledgers sit beside them.
- **Gated status:** a specialist's status changes from *monitoring* to *active* only by your explicit decision.
- **Data stays private:** no market data or private research is ever published.

## 6. $100 feasibility by market (item a)

| Market and vehicle | Minimum trade | Leverage needed at $100 | Costs | US regulatory limits | Tax (US) | Feasible at $100 unleveraged? |
|---|---|---|---|---|---|---|
| **Gold: GLD / IAU / GLDM** | $1 fractional (broker-dependent; GLD-specific eligibility UNVERIFIED) | None | ER 0.40% / 0.25% / 0.10%; model 0.07% one-way | US equity hours only (9:30–16:00 ET plus extended) | Grantor trust: long-term gains as collectibles (max 28%), short-term ordinary | **Yes** |
| Gold: spot XAU/USD via a US retail FX dealer | — | — | Spread + financing | CFTC actual-delivery rule (28 days) makes leveraged retail spot metals effectively unavailable; one 2022 report of unleveraged spot at FOREX.com (UNVERIFIED) | Unclear (Section 988 vs other) | **Effectively no** |
| Gold: COMEX GC (100 oz) / MGC (10 oz) | 1 contract | MGC notional ≈ $20,700 at the end-2023 price → **~200x** | Commission + spread; margin ≈ $1,700–1,900 (third-party) | Futures account minimums $0–2,000 (conflicting) | Section 1256 60/40 | **No** |
| **USD/JPY: US retail FX** (NFA-member dealer) | 1 unit on OANDA's v20 platform (non-US help pages; US UNVERIFIED); 1,000 units (micro lot) on MT4-style platforms | 1,000 units = $1,000 notional → **10x**; with 1-unit sizing, 100 units ≈ $100 → 1x | Spread (measure; not yet sourced) + daily rollover (rate differential minus dealer markup) | Max leverage **50:1 for majors (2% deposit)** (CFTC 2010 rule via NFA; current NFA list UNVERIFIED) | **Section 988 ordinary** by default; election into 60/40 possible (timing rules disputed: UNVERIFIED) | **Only with 1-unit sizing** |
| USD/JPY: CME 6J / micro MJY | 1 contract | 6J ≈ 12.5M yen (tens of thousands of USD); MJY ≈ 1.25M yen (≈ $8–9k at 2023 rates) | Exchange + commission | Futures margin | 60/40 | **No** |
| **GBP/USD: US retail FX** | Same as USD/JPY | 1,000 GBP ≈ $1,200–1,300 notional at 2023 rates (approx.) → **~12–13x**; 1-unit sizing → ≤1x | Spread + rollover | 50:1 (major) | Section 988 / election | **Only with 1-unit sizing** |
| GBP/USD: CME 6B / micro M6B | 1 contract | 6B = £62,500; M6B = £6,250 (≈ $8k) | Exchange + commission | Margin | 60/40 | **No** |

**Conflicts with "do not use leverage to manufacture returns":**
- Any FX dealer with a 1,000-unit minimum (10–13x at $100).
- All gold and FX futures (≥ ~80x).
- Leveraged ETFs (UGL etc.), which carry daily-reset leverage by design.

**Proposed paper-ledger sizes:**
- **Gold:** keep **$100** in GLD, unleveraged; it's feasible as is. This matches the existing books.
- **USD/JPY and GBP/USD:** a **$10,000 virtual ledger each**, with a hard rule that **gross notional ≤ 1.0x equity**: no leverage, ever, without a separate decision. Results are reported in % and as "per $100" figures. A 1,000-unit micro lot is then 0.1–0.13x, so position sizes are realistic at any US dealer. The $100 version is only executable at a 1-unit dealer, which is to be confirmed with the broker by you; I won't contact or connect to brokers.
- **Every ledger** is labelled PAPER, FICTIONAL MONEY, EXPERIMENTAL.

## 7. Data availability (item b)

| Data | Source | Free? | History | Granularity | Bid/ask | Point-in-time | Notes |
|---|---|---|---|---|---|---|---|
| USD/JPY, GBP/USD daily | FRED H.10 (DEXJPUS, DEXUSUK) | Free | 1971+ | Daily noon NY buying rate | No | Rates not revised (UNVERIFIED) | One fixing per day at noon ET; good for daily research |
| USD/JPY, GBP/USD daily OHLC | Yahoo via yfinance (`JPY=X`, `GBPUSD=X`) | Free | About 2003+ (UNVERIFIED) | Daily | No | n/a | Quality to validate; already the project's ETF source |
| FX and gold intraday, recent | Yahoo | Free | 1h ≤ 730 days, 1m ≤ 7 days | Intraday | No | n/a | **Entirely 2024+, i.e. holdout: unusable for research** |
| FX and gold tick/1-min with bid/ask | Dukascopy | Free download | Years (range UNVERIFIED) | Tick / 10 s / bars | **Yes** | n/a | Terms unread; bulk download may need their software or a third-party tool → **approval needed** |
| FX 1-min | HistData.com | Free | Years (UNVERIFIED) | 1 min | License and bid/ask UNVERIFIED | n/a | Check terms before any download |
| FX tick | TrueFX | Free with registration | UNVERIFIED | Tick | Yes | n/a | Needs a login → your decision; I can't hold credentials |
| GLD daily | Yahoo | Free | 2004-11+ (in `data/`) | Daily | No | n/a | Already validated in Phase 2 |
| Gold futures daily | Yahoo `GC=F` | Free | 2000-08+ (in `data/`) | Daily | No | n/a | Signal quality only (data report) |
| Gold monthly | World Bank Pink Sheet | Free | 1960+ (in `data/`) | Monthly average | No | n/a | Averages; used in Study 3 |
| LBMA gold price | ICE Benchmark Administration | **Paid / licensed** | 1968+ | Daily | — | — | FRED removed it in 2022 |
| Gold ETF flows, central-bank purchases | World Gold Council Goldhub | Free with registration | Varies | Monthly/weekly | — | Partly | Login → your decision |
| US yields (2y, 10y, real, breakeven) | FRED | Free | 1962/1976/2003+ | Daily | — | Current vintage only | Already used (DFII10, T10YIE) |
| Japan yields (JGB) | Japan MoF yield-curve CSV | Free (UNVERIFIED access) | 1974+ (UNVERIFIED) | Daily | — | — | To check in Phase 5 |
| UK gilt yields, Bank Rate | Bank of England database | Free (UNVERIFIED access) | Decades | Daily | — | — | To check |
| Policy decisions and dates | Fed, BoJ, BoE websites | Free | Decades | Event | — | Yes (dated statements) | Scrape-free manual or official lists |
| Japan intervention records | Japan MoF | Free | Daily since 1991-04 (verified (web)) | Daily amounts | — | **Published with a lag** (schedule UNVERIFIED) | Rare ground truth for intervention studies; must use publication dates, not intervention dates |
| COT positioning (JPY, GBP, gold) | CFTC | Free | 1986+ | Weekly | — | Tuesday data released Friday 15:30 ET | — |
| Macro vintages | ALFRED | Free; **keyless CSV UNVERIFIED** | Decades | Per release | — | **Yes** | An API key would be a credential (rule 1): you'd create it and store it yourself, or we use manual downloads |
| Release calendars (BLS, BEA, ONS, Fed, BoE, BoJ) | Official sites | Free | Recent years; history varies | Event | — | Yes | — |
| **Consensus forecasts** | Bloomberg, LSEG/Refinitiv, Trading Economics API, etc. | **Paid** (prices UNVERIFIED) | — | Per release | — | Yes, if licensed | Free calendar sites generally forbid scraping |
| Historical FX spreads, institutional | LSEG, Bloomberg, CME DataMine, TickData | **Paid** (prices UNVERIFIED) | — | Tick | Yes | — | — |
| News archives | Reuters, AP, Bloomberg, WSJ, FT | Paid / blocked (the brief task can't reach most) | — | — | — | — | — |

**Phases that depend on paid or login-gated data:**
- **Phase 2:** time-of-day windows need intraday bid/ask history before 2024.
- **Phase 5:** surprise measurement needs consensus forecasts; vintages need ALFRED access.
- **Phase 7:** announcement-reaction hypotheses need the same.
- **Phase 10:** realistic FX spread modelling.

**Free data supports:** daily USD/JPY research (FRED 1971+), rate differentials, intervention event studies, COT, and the market clock and library.

## 8. Intraday windows you can realistically act on (item d)

**Assumptions:** you're in New York, on a full-time schedule (roughly 09:00–17:00 ET), with no automated execution (rule 1).

| Window (ET) | What is happening | Usable? |
|---|---|---|
| 06:00–08:30 | London morning (London opens 03:00 ET); US data at 08:30 | **Yes**, before work. Placing orders right before 08:30 releases is high-risk; pre-set orders only |
| 08:30–17:00 | NY session, London–NY overlap 08:00–12:00 ET; GLD trades 09:30–16:00 | **Mostly no:** at work; only orders placed in advance |
| 17:00 | FX daily roll (rollover/financing charged); "daily close" | **Yes:** natural daily decision point |
| 18:00–23:00 | Sydney open; **Tokyo open = 19:00 ET (US daylight time) or 20:00 ET (US standard time)**; Japan has no DST | **Yes:** evening. Relevant for USD/JPY |
| Fri 17:00 – Sun 17:00 | FX market closed; weekend gap risk | Decisions only |

**Implications:**
- Strategies that need watching during the work day can't be acted on.
- Research should focus on **daily or multi-day horizons with decisions at fixed, actionable times**: 17:00 ET close snapshots, an evening Tokyo-open entry, or a pre-work entry.
- Intraday time-of-day research is still useful for **safeguards** (when not to enter), which needs the intraday data in section 7.

## 9. Holdout and multiple-testing policy for new studies (proposal; needs your approval)

- **The 2024+ holdout stays locked for all three markets.** Monitoring data never enters research files.
- **Cumulative N continues from 134 for the Deflated Sharpe.** I'd also report the per-market family count and the effective N.
- **USD/JPY and GBP/USD (untouched by earlier studies):**
  - in-sample 1990-01 to 2014-12;
  - validation 2015-01 to 2023-12;
  - holdout 2024+.
  - Daily data from FRED H.10 make 1990+ available.
- **Gold:** new tests on 2019–2023 count as **exploratory only**. Options for a confirmatory test:
  - pre-2004 daily history, if a licensed or free daily spot/futures series is found;
  - a single, pre-registered use of the 2024+ holdout, which spends it permanently.
- **The kill criteria K1–K7 stay unchanged, with FX additions:** net of spreads and rollover; K4 trade counts on actual round trips; K7 on a per-$10,000 basis.

## 10. GitHub and research resources (preliminary; deep review is Phase 4)

**Activity and license, checked via the GitHub API 2026-10-23:**
| Repo | Stars | License | Last push | Fit for this project (preliminary) |
|---|---|---|---|---|
| nautechsystems/nautilus_trader | 30.7k | LGPL-3.0 | 2026-10-23 | Event-driven, FX-capable, bid/ask, sessions. Strongest candidate *if* intraday research is approved; heavy (Rust build) |
| microsoft/qlib | 49.6k | MIT | 2026-10-22 | ML research pipeline for equities; useful ideas for dataset versioning; likely oversized for 3 instruments |
| microsoft/RD-Agent | 15.0k | MIT | 2026-10-21 | LLM-driven research loop. **Risk:** automated idea generation inflates the trial count; not before Phase 6 memory and N accounting |
| QuantConnect/Lean | 22.2k | Apache-2.0 | 2026-10-23 | Full C# engine; replaces rather than extends; not recommended |
| polakowo/vectorbt | 9.5k | NOASSERTION (custom; UNVERIFIED) | 2026-10-23 | Fast vectorized sweeps encourage mass parameter search; license to check |
| kernc/backtesting.py | 9.1k | **AGPL-3.0** | 2026-08-05 | Copying code into this MIT repo would force AGPL; reference only |
| AI4Finance-Foundation/FinGPT | 21.4k | MIT | 2026-09-23 | News sentiment LLMs; unproven predictive value; Phase 8+ at most |
| AI4Finance-Foundation/FinRL-Trading | 3.8k | Apache-2.0 | 2026-09-18 | Reinforcement learning; insufficient data for a credible RL validation at 1–3 instruments |

**Smallest-viable-stack hypothesis:**
- Keep the existing engine and validation code, and add `fx_engine.py` and `clock.py` using only the standard library and the packages already installed.
- Consider `nautilus_trader` only once intraday bid/ask data is approved, after a security review like the day-trader-skill audit.
- Nothing is installed or run without approval.

**Books (Phase 3; lawful access only):**
- **Authors' own free papers:** López de Prado (SSRN) and Carver (blog) are already used.
- **Official or educational material that may exist:** Aronson (evidence-based technical analysis), Harris (market microstructure lectures), Campbell–Lo–MacKinlay (lecture notes).
- **Likely no lawful free access** (summaries and author interviews only): Kaufman, Clenow, Schwager, Grinold–Kahn, Ilmanen, Chan.
- **To search:** FX microstructure (Lyons; Evans), currency risk premia (Lustig–Verdelhan; Menkhoff et al.), intervention (BIS and BoJ papers), gold (World Gold Council research; Erb–Harvey).

## 11. Prioritized implementation plan with session effort (item e)

**Effort:**
- **S:** under half a session.
- **M:** about one session.
- **L:** several sessions.

| # | Step | Phase | Effort | Needs approval / data |
|---|---|---|---|---|
| 1 | Specialist registry, `specialists:` config block, folder layout, holdout and N policy written into config | 1 | S | Your OK on sections 6, 9, 12 |
| 2 | Market clock: IANA zones, sessions, DST transitions, FX week, rollover, US/UK/Japan holidays (rule-based like the NYSE calendar), adversarial DST tests | 2 | M | None (stdlib); a holiday package would need approval |
| 3 | Research memory: append-only, hash-chained hypothesis, experiment, forecast and incident ledgers; retrieval before new experiments | 6 | M | None |
| 4 | Knowledge library: SQLite FTS5 schema, migrate 202 existing sources, evidence classes A–F, dedupe, last-verified dates | 3 | M (build) + L (ongoing curation) | None for the build; deep reading is ongoing |
| 5 | USD/JPY free daily data: FRED H.10, US/Japan yields, MoF intervention records, COT; validation and holdout truncation as in Phase 2 | 5 | M | Japan MoF and BoJ access to verify; stop if a source needs a login |
| 6 | FX engine: long/short, spread model, rollover from rate differentials, notional cap, closed-market guard; tests incl. adversarial | 7 | L | None |
| 7 | GitHub deep review (read-only, like AUDIT.md) | 4 | M | Approval before running any code |
| 8 | USD/JPY literature review: rate differentials, carry and crash risk, intervention effects, safe-haven behaviour, contradicting studies | 3 | L | None |
| 9 | Pre-register 3–6 USD/JPY hypotheses (daily horizon, actionable times), then run in-sample → validation → kill table | 7 | L | Your approval of the hypothesis list |
| 10 | Per-specialist decision report (must output ABSTAIN / UNKNOWN when evidence is missing) | 9 | M | Steps 2–9 |
| 11 | USD/JPY paper ledger ($10k, ≤1x notional) inside the existing weekday task | 10–11 | M | Approval |
| 12 | Event database and point-in-time vintages | 5 | L | ALFRED access; consensus data is paid |
| 13 | Intraday time-of-day study and safeguards | 2 | L | **Intraday data approval** |
| 14 | ML baselines (regularized regression, gradient boosting) vs simple rules | 8 | L | Only after step 9 shows something worth modelling; new packages need approval |
| 15 | Gold and GBP/USD specialists to research depth | 1–7 | L each | After USD/JPY completes a full cycle |

The adversarial QA tests (Phase 12) are built inside each step, not separately.

## 12. Recommendation: activate USD/JPY first (item f)

**Why USD/JPY:**
1. **Clean data.** No earlier study touched it, so 2015–2023 is a genuine validation window. Gold's is spent.
2. **Specific, economically explainable mechanisms:** US–Japan rate differentials, BoJ policy shifts, carry and its unwinds, and MoF intervention. Intervention has an **official dated record since 1991**, a rare source of ground truth for event studies (with the publication lag respected).
3. **Free long data:** daily rates since 1971 (FRED H.10), plus yields on both sides and COT positioning.
4. **It fits your schedule.** The Tokyo session opens at 19:00 or 20:00 ET, and the 17:00 ET daily close is a natural decision point.

**Honest risks:**
- The strongest academic FX evidence (carry, momentum) is **cross-sectional across many currencies**. Single-pair versions are weaker, which is the same universe-size problem that sank Studies 1–3.
- Carry trades carry crash risk.
- Spot FX at $100 needs 1-unit sizing or the $10,000 notional-capped ledger.
- The engine needs shorting and financing before any test.

**Why not the others first:**
- **Gold:** 6 gold-only families already killed (SMA trend, TSMOM, volatility-scaled trend, real-yield filter, dollar filter, monthly TSMOM), a contaminated validation window, and the only clean data is the one-shot holdout.
- **GBP/USD:** its distinctive mechanisms (UK data surprises, fiscal events) depend most on paid consensus data and intraday history.

Both stay in monitoring mode. The existing gold monitoring (watchlist, paper books, brief) keeps running unchanged.

## 13. Decisions needed from you before Phase 1

1. **First specialist:** USD/JPY (recommended), gold, or GBP/USD.
2. **Paper ledger sizes:** gold $100 unleveraged; FX $10,000 each with gross notional ≤ 1.0x; reporting in % and per $100.
3. **Study splits for FX:** in-sample 1990–2014, validation 2015–2023, holdout 2024+. Gold: 2019–2023 re-use is exploratory only.
4. **Data access needing logins or third-party tools** (each a separate yes/no): Dukascopy, HistData, TrueFX, WGC Goldhub, an ALFRED key. I won't hold credentials. If you approve, you'd download files yourself into a folder I then validate, or create and store a key yourself.
5. **Dependencies:** none needed for steps 1–6. Is a holiday library acceptable, or should calendars be rule-based like the existing NYSE calendar (my default)?
6. **Publication:** may the new code, tests and bibliographic library be public like the rest? Market data and private ledgers would stay private.
7. **Housekeeping:** push the three local commits; create the private backup repo.

## 14. Sources used for this plan (verified web, 2026-10-23)

- **CFTC/NFA retail FX leverage:** CFTC 2010 final rules (2% deposit for majors = 50:1; 5% others = 20:1) as reported by [Euromoney](https://www.euromoney.com/article/b12kht4m12njyr/fx-news-cftc-releases-final-rules-covering-retail-fx) and [Wikipedia](https://en.wikipedia.org/wiki/Retail_foreign_exchange_trading). The current NFA list is UNVERIFIED.
- **OANDA minimum trade size:** 1 unit on its v20 platform ([OANDA help, non-US](https://help.oanda.com/au/en/faqs/minimum-trade-size.htm)). The US minimum is UNVERIFIED.
- **Japan intervention records:** daily records since April 1991 ([Federal Reserve IFDP 824](https://www.federalreserve.gov/Pubs/IFDP/2005/824/ifdp824.htm)). The publication schedule is UNVERIFIED.
- **Section 988 / 1256:** secondary sources ([BDO](https://www.bdo.com/insights/tax/proposed-treasury-regulations-address-non-application-of-section-1256-to-over-the-counter-foreign), [Benzinga](https://www.benzinga.com/money/how-do-forex-taxes-work)). Election timing is disputed: UNVERIFIED.
- **Dukascopy access:** third-party descriptions only ([TheoryCraft library](https://github.com/theorycraft-trading/dukascopy)). The terms are unread.
- **GitHub metadata:** GitHub REST API, 2026-10-23.
- **From this repository:** gold, futures and tax facts in `research/IDEA_POOL_COMMODITIES.md` and `research/sources_commodities.csv`; trial history in `research_log.csv`; study results in `reports/`.

_This file is the planning record for future sessions. Update it, don't overwrite it, as decisions are made._
