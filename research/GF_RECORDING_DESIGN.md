# GF1/GF2 recording: implementation design (audit item 15; for the 2026-11-06 batch)

_Design only. It implements the frozen `research/GOLD_FORWARD_PREREG_GF1_GF2_v1.0.md` (sha256 c2e198c9…). Nothing here changes F001/F002, the gate, paper or financing. Counting starts on the first completed NYSE trading day after this code is live **and** its first evening pass is confirmed clean._

## 1. Isolation

**Today's coupling:**
- `paper.manage` and the gate loop over `cfg["rules"]` (F001, F002).
- They share one Book for the 2-position and 1.0x-gross limits (`src/live_usdjpy/gate.py:163-177`).

**GF1/GF2 are observation rules.** They have no ledger, no orders and no Book, so they live **outside** `cfg["rules"]`.

| Piece | Change |
|---|---|
| Registry | `KINDS` gains `"observation"` (`src/live_usdjpy/registry.py:27`): append-only, in the hash chain. Past records untouched |
| Config | A new block `live_usdjpy.observation_rules` holding the frozen parameters (σ window 60, z −1.5, event list, thresholds 100 / 30) and the prereg SHA-256 (pinned by a test) |
| Code | A new module `src/live_usdjpy/observe.py` with pure functions and one `record()` entry point |
| Runner | One call in the evening pass, after the daily GLD/SPY bars are confirmed (beside the backup block, `tools/usdjpy_pipeline.py:203-213`) |
| Scorer / STATUS | A separate "Forward observations (INFORMATION ONLY)" section: **counts only** before the thresholds |
| Untouched | `cfg["rules"]`, gate, paper, financing, notifications (one digest line with counts only) |

## 2. observe.py

**`gf2_day(day, bars_gld, events_asof)`:**
- Event day if the event store **as of 18:00 ET on day − 1** lists a scheduled CPI, Employment Situation, FOMC statement or Personal Income and Outlays release on `day`.
- Late-listed: published but not listed by the cut-off. Cancelled: listed but not published (excluded).
- Comparison day: everything else, except the trading day after an event day and days after a closure of more than 1 day.
- Returns `{date, class, r_log, flags}`. `r_log` is from consecutive SIP closes only; otherwise the day is excluded with a flag.

**`gf1_trigger(day, bars_gld, bars_spy)`:**
- Fires if r_GLD ≤ −1.5 × σ60(GLD) **and** r_SPY ≤ −1.5 × σ60(SPY), with σ60 over the 60 returns ending at day − 1.
- Records the date, both z-scores and flags (FOMC/release day, data flags). Overlap within 5 days links to the first trigger.

**`gf1_followups(registry, bars)`:** appends the t+1 and t+5 GLD returns when they complete. Never recomputed, never edited.

**`record(registry, now, bars, events_store_history)`:**
- Idempotency keys `gf2:<date>`, `gf1:<date>`, `gf1f:<date>:<h>`.
- All writes in one transaction.

**The event store's past state:** today `live/events/events.json` is rewritten each poll. `live/events/changes.jsonl` logs changes, but it isn't hash-chained. So **the batch also appends a daily 18:00 ET `note` record `event_calendar_asof`**: the list of the next day's scheduled releases with a SHA-256. GF2 reads that note, never the current store. This is required for the t−1 cut-off to be honest.

## 3. No-peek guard

- `scorer.observation_section()` returns counts only (event days, comparison days, exclusions, late-listed, triggers) until GF2 has 100 event days and GF1 has 30 independent triggers.
- A test asserts that no ratio or return statistic appears in STATUS, the digest or the weekly review below the thresholds.

## 4. Tests (all synthetic)

1. Event-day classification uses the t−1 18:00 ET calendar note, not the later store. A release added on day t is "late-listed".
2. Spillover, closure and missing-bar exclusions.
3. GF1 trigger thresholds on synthetic series; σ uses data up to t−1 only (a planted shock on t does not inflate σ).
4. Follow-ups are appended once; reruns are idempotent.
5. No-peek: counts only below the thresholds.
6. **Isolation:** on a recorded synthetic day, F001/F002 evaluation, fill and reconciliation records are byte-identical with and without `observe.record`. `observe` never writes `fill`, `order_event`, `risk_state` or `notification` (except the digest line).
7. Prereg SHA-256 pinned in config equals the frozen document's hash.

**Effort:** S–M. **Deployment:** in the Friday 2026-11-06 batch (it changes the runner).
