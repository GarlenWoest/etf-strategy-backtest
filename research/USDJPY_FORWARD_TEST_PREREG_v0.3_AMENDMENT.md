# USD/JPY forward test: v0.3 source amendment

**Status: FROZEN 2026-10-29, before the first forward scan.** The forward registry holds 0 scans and 0 evaluations (checked 2026-10-29 20:0x ET). Owner decision 2026-10-29.

**What this does:** it amends `research/USDJPY_FORWARD_TEST_PREREG.md` (v0.2, frozen, sha256 `763f8dc3…`). That file stays unchanged and pinned by its own test.

**What it changes:** **only the data sources** and **the start and catch-up rule** below. Unchanged:
- every rule parameter (F001 and F002);
- sizing, costs and the fill convention;
- financing conventions, baselines, metrics, minimum samples, and the success, failure and stop rules;
- forward N = 2 and historical N = 142.

**Trial IDs stay F001 and F002.** v0.2 says any change gets a new forward-trial ID. This amendment is the single recorded exception: **v0.2 never ran** (no scan, no evaluation, no observation exists under it), so nothing was seen that could have influenced this change. The rule versions become 0.3.

**Why:** Yahoo's Terms of Service prohibit collecting data "using any automated means" and using it to create a "database, archive, … data feed" (section 2(d), items 9–10; read 2026-10-29). The forward system must run unattended, so its prices move to sources whose terms allow programmatic access.

## 1. Sources (replacing every Yahoo input in v0.2)

| Input | v0.2 | v0.3 |
|---|---|---|
| USD/JPY entry reference, marks, exit checks | Yahoo `JPY=X` last price | **OANDA v20 practice API**, pricing endpoint: mid = (bid + ask) ÷ 2. LIVE requires OANDA's price time to be ≤ 180 s old (market_intel freshness rules) |
| USD/JPY daily bars (σ60, z-scores, 12-month return) | Yahoo daily closes, complete after 00:00 UTC | **OANDA daily mid candles,** 17:00 New York alignment; only candles flagged `complete`; each labelled with the New York trade date it ends on |
| SPY daily bars (F001's second leg) | Yahoo daily closes | **Alpaca market data, IEX feed,** raw (unadjusted) daily close; complete after 16:15 ET. Note: the IEX close is the last IEX trade and can differ slightly from the consolidated close |
| GLD (gold reference; observation only) | Yahoo | **Alpaca IEX** two-sided quote mid while NYSE is open; otherwise the last IEX daily close, labelled CLOSED_LAST_PRICE |
| GBP/USD (monitoring only) | Yahoo | **OANDA v20 practice** |
| Rates for financing; D2 constant; events | FRED/BoJ; Fed H.10; official calendars | Unchanged |

**What the new sources are, and aren't:**
- **OANDA practice quotes are the venue's indicative practice prices.** They're **not executed fills**, and practice can differ from live.
- **The bid/ask spread is recorded at every scan, descriptively only.** The cost model stays the frozen assumption (fill at mid × (1 ± 0.015%)); measured spreads are reported next to it, never substituted.
- **Read-only access is enforced in code:** `src/live_usdjpy/sources.py` allows only GET requests to allow-listed pricing, candle, quote and bar endpoints on hard-wired hosts, and a test blocks any order, trade, position or account-changing call.
- **Credentials stay with the owner:** they're held in the macOS Keychain and never written to records.

## 2. Start and catch-up rule

- **First forward scan:**
  - **F001** is evaluated on the latest completed USD/JPY bar.
  - **F002** is evaluated on the most recent month-end bar **on or after 2026-10-30** that hasn't been evaluated yet. This captures the 2026-10-30 decision if the first scan comes after that close.
- **Later scans** evaluate, in date order, every completed bar since the last evaluated one (F001), and the latest unevaluated month-end (F002).
- **DETECTED LATE:** any signal detected more than 30 minutes after its bar completed (OANDA candle end, 17:00 New York) is recorded and alerted as "DETECTED LATE (system was not running at bar completion)", never as a live detection.
- **Entries still need everything in v0.2:** a LIVE price at the time of entry, every gate, and the entry window counted from detection.
- **Gap records:** a gap between runs is recorded with its duration, and whether the Mac's power log shows sleep in it.

## 3. Data governance and licensing

- **Owner decision D1 applies unchanged:** trailing windows (σ60, 12-month returns, 250-day volatility medians) of current data may reach into 2024–2026, for computing live signals only. No returns, performance or rule evaluation on 2024+ data outside the forward registry.
- **Retention:** OANDA and Alpaca data are used for internal research monitoring only, kept under `live/` (private), and never published.
