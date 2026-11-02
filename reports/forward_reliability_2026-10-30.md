# Forward system: reliability, meaningful alerts and readiness (next phase, started 2026-10-30)

_One report for this phase, updated phase by phase. Monitoring side only: no frozen rule, historical result, paper-book rule or research record is changed. Nothing here is validated or financial advice._

## A. Verified state (2026-10-30, 09:40 ET; read-only checks)

| Claim in SUMMARY.pdf | What was checked | Result |
|---|---|---|
| 313 passing tests | `pytest tests` | **313 passed** |
| LaunchAgent running | `launchctl print`: runs, last exit; `runner.out.log`; `runner.err.log` | **55 runs, last exit 0, every line RUN OK, 0 RUN ERROR, error log empty.** No gap record: the Mac stayed awake on AC |
| Hash-chained registry | `usdjpy_pipeline.py verify` | **Chain intact, 100 records** |
| Scheduled scans | Every `scan_run` with its `market_state` and `reconciliation` | **14 scans** (10-29 20:07 manual kickstart + 13 scheduled, hourly at :02 from 21:02 ET). Every one: state ACTIVE, both reconciliation checks OK, all three specialists DATA OK, USD/JPY LIVE. Daily bars dated 10-29 (correct until today's 17:00 ET bar) |
| Rules | `evaluation` records | Only the first scan evaluated (F001 NO TRADE, F002 NOT DUE). Later scans correctly evaluated nothing: no new daily bar has completed since 10-29 17:00 ET |
| Event monitor | Agent polls at 06:02, 08:47 (08:35 release + 5 min) and 09:02 ET, each exit 0 | Working. BoJ 10-30 statement recorded as PUBLISHED (official PDF) |
| MARKET WATCH | `market_watch` records | 10-29: W003 BoJ (alerted), 2 W004 silent baselines. 10-30 06:02 ET: **W004 new MoF monthly release** (alerted) |
| Notifications | Every `notification` and `delivery` record | 6 queued since the install, each sent exactly once on Pushover (HTTP 200), no duplicates, no failures. The MoF alert (NORMAL, queued 06:02 ET in quiet hours) was held and sent at 07:02 ET as designed |

**Acceptance tests (true status):**
- **J: PASSED (real, scheduled).** 10 consecutive scheduled scans, 21:02–06:02 ET, each complete and reconciled, with no duplicate alert, hash failure, unhandled exception or gap. Re-checked independently of the watcher. An engineering checkpoint only.
- **H: NOT PASSED.** Scheduled scans complete without Claude, and the runner's TEST notification was **accepted by Pushover** (HTTP 200, 20:17 ET 10-29). Arrival on the phone has **not** been confirmed by the owner, and HTTP 200 doesn't prove it.
- A–G, I, K, L: pass on synthetic fixtures only (unchanged).

**Defects found in Phase A (fixed in Phase C unless noted):**
1. **Negative quote age on every scan** (−0.7 to −4.8 s, and −34 s at 06:02 ET). Cause: the snapshot's age is measured from the run's start time, which is taken before the event poll and the price request (the 06:02 run polled events for about 30 s first). Freshness was never wrong in the unsafe direction (a quote can't be younger than the run), but ages are misstated.
2. **Spreads aren't stored** in `market_state` (v0.3 says they are recorded at every scan).
3. **Yahoo-era labels** in records and alerts (`JPY=X`, `GBPUSD=X`); stale digest and status-page text.
4. **No registry backup** (fixed in Phase B).
5. The official BoJ statement became PUBLISHED, but nothing tells the owner about important new official information (Phase E policy).

## B. Forward-registry backup (2026-10-30)

**Before:** the live database was (correctly) excluded from the private backup, but no snapshot was ever made. The forward record existed only on this Mac.

**Built** (`src/live_usdjpy/backup.py`, `usdjpy_pipeline.py backup …`, config `live_usdjpy.backup`):
- **Consistent snapshot** with SQLite's online backup API, taken inside the runner's file lock, so no scan writes at the same time. Includes writes still in the WAL. Fsynced.
- **Verification** on a read-only connection before anything is published: `PRAGMA integrity_check` = ok; the full hash chain recomputes; the record count and last hash equal the live registry's; the JSONL export has one line per record. A failed check publishes nothing.
- **Published** (only after verification) to `live/usdjpy_backup/`: `registry_snapshot.sqlite`, `registry_export.jsonl` and `manifest.json` (time, records, last hash, SHA-256s).
- **Dated local copies** in `live/usdjpy/local_snapshots/` (newest 30 kept).
- **When:** once per New York day at the first run after 17:30 ET (after the daily bar), whenever the newest verified snapshot is older than 30 h, or immediately if none exists. A failure is retried at most hourly.
- **Record:** every attempt and restore test is a `backup` record in the registry (new record kind; append-only like everything else).
- **Alerts (HIGH, RISK/SYSTEM, once per reason per New York day):** 2 consecutive failed attempts; newest verified snapshot older than 30 h; off-site copy older than 9 days (or still missing 9 days after 10-30). The off-site age is read from the local `.backup.git` refs, without network access.
- **Digest line:** last verified snapshot and the off-site state.

**Private-backup permissions: no change.** `tools/backup_private.py` is untouched. Its allow-list (`paper/`, `live/`, `briefs/`) already covers `live/usdjpy_backup/`. Its existing exclude rule `live/usdjpy/*.sqlite*` keeps the live databases, their WAL/SHM files, the DEMO registry and the dated local copies out. A test runs those exact pathspecs and shows that only the three published files would be added. The snapshot contains the same private records as `live/` already does (prices, notifications); it goes only to the private repository.

**Off-site timing.** The private backup is pushed only by the Sunday Claude task, so the first off-site copy of the registry is due Sun 11-01 18:00 ET, and the off-site recovery point is up to 7 days old. A daily push by the runner would shorten that, but it is a scheduled-task change: proposed in section G, not applied.

### Recovery procedure (registry lost or corrupted)

1. **Stop the runner:** `launchctl bootout gui/$(id -u)/local.trading-research.usdjpy-runner`.
2. **Keep the damaged files:** move `live/usdjpy/registry.sqlite`, `-wal` and `-shm` to a dated folder; never delete them.
3. **Pick the newest good snapshot:** `live/usdjpy_backup/registry_snapshot.sqlite`, else the newest file in `live/usdjpy/local_snapshots/`, else the private repository (clone it, or `git --git-dir=.backup.git show origin/main:live/usdjpy_backup/registry_snapshot.sqlite > restored.sqlite`).
4. **Verify it:** `.venv/bin/python -I tools/usdjpy_pipeline.py backup restore-test` (published copy), or `--source offsite` (the copy last pushed to the private repository).
5. **Restore:** copy the verified file to `live/usdjpy/registry.sqlite`, then run `usdjpy_pipeline.py verify` (chain intact) and `status`.
6. **Record the loss honestly:** append a `note` stating the snapshot used, its last seq and time, and that records after it are lost. Lost scans aren't recreated; the catch-up logic re-evaluates missed bars and labels them DETECTED LATE.
7. **Restart:** `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.trading-research.usdjpy-runner.plist`.

### Results

- **First live snapshot:** taken by the scheduled 09:47 ET run (`backup OK (100 records)`). A second one, taken with `backup snapshot` at 09:47:50 ET after a fix (below), has 102 records and passes integrity and chain checks (SHA-256 `a09c52f5…`).
- **Restore tests (published copy):** PASS both times. Every restored record equals the live registry's record with the same seq; the temporary folder under `tmp/` was removed.
- **Private-backup dry run** (`git add -n` with the unchanged pathspecs, nothing staged): only `live/usdjpy_backup/manifest.json`, `registry_export.jsonl` and `registry_snapshot.sqlite` would be added; no live database, WAL file or local copy.
- **Defect found and fixed during the test:** the first snapshot kept SQLite's WAL journal mode, so opening it left `-wal`/`-shm` side files. Snapshots are now converted to a single self-contained file (journal mode DELETE) before verification; a test pins it.
- **Runner after the change:** the 10:02 ET scheduled scan completed cleanly (RUN OK, reconciled, empty error log; chain intact, 109 records).
- **Tests:** 323 pass (+10: snapshot with un-checkpointed WAL writes, tamper detection, restore pass and manifest mismatch, due timing and retry, health alerts and their daily deduplication, stale off-site copy, off-site grace, the private-backup path rules).
- **Off-site (owner decision 10-30, option c):** after the verified evening snapshot the runner now runs the existing `tools/backup_private.py run` (allow-list check, commit, push, confirm GitHub's main) with only PATH and HOME in its environment, and records the one-line result. 2 consecutive failed pushes raise a HIGH alert. First push 10:05 ET (commit `0b21229`, 29 files, all under `paper/`, `live/`, `briefs/`; the only database is the published snapshot). **Off-site restore test from the private repository: PASS** (102 records, integrity ok, chain intact, every record equal to the live registry).
- **Acceptance H: PASSED** (owner confirmed 10-30 that the runner's TEST arrived on the phone; recorded in the registry as an owner-confirmed delivery and a note).
- **Not yet verified:** the push from inside the LaunchAgent itself (first one after the 17:30 ET snapshot today; the Keychain credential helper under launchd is untested).

## C. Market data audit (2026-10-30)

- **Quote age fixed.** Ages are now measured from the moment the response arrived (`retrieved_utc`), not from the run's start. Each request records `request_utc` and `retrieved_utc`; the server's HTTP Date header gives a venue clock offset (1 s resolution). First real check: USD/JPY quote stamped 0.08 s after receipt, venue clock +0.1 s from the Mac: within tolerance. The −34 s case is explained (a 30 s event poll ran before the request).
- **Clock skew:** a quote stamped more than 2 s after its own receipt gets a `CLOCK SKEW` note; preflight reports an offset above 5 s as DEGRADED.
- **Quotes and spreads in every `market_state`** (`quotes` block): source, symbol, quote time, request and retrieval times, bid, ask, spread, spread in pips, freshness and its note, clock note and offset, tradeable flag, and every missing or invalid field by name (missing side, non-positive price, crossed or locked quote). An invalid quote is UNAVAILABLE, never used as a price. Each record carries the note that spreads are descriptive and **the frozen cost model (0.015% one-way, 0.030% stress) is unchanged and never substituted**.
- **Labels:** new records use the v0.3 symbols (`USD_JPY`, `GBP_USD`, `SPY`, `GLD`) with a `bar_sources` map; alerts say "USD_JPY (OANDA practice, indicative)"; the config's MARKET WATCH labels, the status page's scheduler line and rule versions and the digest's paper-position text are corrected. **Old records are unchanged**; code still reads the old keys.
- **OFFICIAL RELEASE alerts** (owner request): NORMAL, information only, when the event monitor confirms a USD/JPY-relevant Fed, BoJ or key BLS/BEA release (Employment Situation, CPI, GDP, Personal Income and Outlays) as PUBLISHED: source, title, time and link; no figures or interpretation; only publications detected in the last 24 h; once per event. MoF releases stay with W004. **First real one: the BoJ 10-30 statement, accepted by Pushover at 10:17 ET.** The Employment Cost Index (10-30) was correctly not alerted (not on the key list).
- **Defect found and fixed (today's F002 decision):** if the scan after 17:00 ET ran before OANDA flagged the daily candle complete, the bar counted as covered; on a Friday (FX closed) the next scan would have been Sunday and the month-end decision would have been caught up late. The runner now keeps scanning every run (up to 6 h) until it has seen the new bar.
- **Tests:** +5 (retrieval-time age with a 30 s pre-request delay; clock skew; crossed, locked and missing quotes; invalid quote → UNAVAILABLE; release alerts once, no replay, no figures; the bar-wait plan).

## D. Preflight and readiness (built 10-30; wired into the runner after 17:30 ET so the first F002 decision ran on unchanged code)

Before every scan the runner checks, and records as a `preflight` record, whether the system can **operate** correctly. It is not a market view and has no score.

| Check | BLOCKED when (fails closed) | DEGRADED when |
|---|---|---|
| Market data sources | price or bar request failed → rule evaluation, paper entries and position monitoring off | — |
| USD/JPY quote | invalid quote, or not LIVE while FX is open → paper entries and position monitoring off | — (market closed is INFO) |
| Clock | — | CLOCK SKEW note, or venue offset above 5 s |
| GBP/USD, gold data | — | not DATA OK while their market is open (observation only) |
| USD/JPY daily bars | newest bar more than 6 h overdue → rule evaluation off | bar due but not yet complete |
| SPY daily bars | no SPY bar for an NYSE trading day → rule evaluation off (F001 would otherwise record NO TRADE for a data gap) | — |
| Calendars | calendar error → paper entries off | — |
| Event monitor | store missing or older than 26 h → paper entries off (blackouts unknown) | — |
| Risk engine | kill switch ON, HALTED, unreadable → paper entries off | REDUCING |
| Registry | chain broken or not writable → evaluation and entries off | — |
| Reconciliation | last one failed → paper entries off | — |
| Previous run | — | ended with an error (it already sent its own HIGH alert) |
| Notifications | — | a sendable notification not accepted by any provider for 30 min (quiet-hours holds excluded) |
| Backup | — | any backup problem (it has its own HIGH alerts) |

- **Verdict:** READY / DEGRADED / BLOCKED, plus the fail-closed capability list. Shown in STATUS.md (every check), in the digest, and with `usdjpy_pipeline.py preflight` (dry run).
- **Fail closed, observation continues:** a failed fetch no longer ends the run with an error. The scan is skipped, the preflight is recorded, and notifications, digest and backup still run. Deferred rule evaluations are caught up later (labelled DETECTED LATE if more than 30 minutes after the bar). With a stale or invalid price, no invalidation, entry or exit is decided; an open paper position triggers a HIGH "PAPER POSITION UNMONITORED".
- **Alerts without flapping:** a problem must persist for 2 consecutive scans. BLOCKED → HIGH; DEGRADED → NORMAL; once per problem set per New York day; a NORMAL "MONITORING RECOVERED" when it clears.
- **Real run (DEMO registry, real read-only APIs, 10:29 ET):** READY, every check OK.

## E. Alerts, tickets and notification policy (built 10-30; wired after 17:30 ET)

**Level A, phone alert:** the title is the lock-screen line (`USD/JPY | EXPERIMENTAL SETUP`, `USD/JPY | OFFICIAL RELEASE`, `SYSTEM ALERT`). The body has at most six short lines: what happened, the direction (only if a rule supplies one), the key reason, the authorization line, the event time with status, and the ticket pointer.

| Classification | Authorization line |
|---|---|
| EXPERIMENTAL SETUP (F001, F002) | WATCH ONLY. NOT VALIDATED. No real-money trade. |
| PAPER POSITION (shadow ledger) | SHADOW PAPER LEDGER ONLY (simulated). No real-money trade. |
| APPROVED PAPER SETUP (none exist) | PAPER ONLY. No real-money trade. |
| MARKET WATCH / OFFICIAL RELEASE | INFORMATION ONLY. |
| SYSTEM ALERT / MONITORING STATUS | ACTION or status line, pointing to STATUS.md |
| DAILY DIGEST | NOT A TRADING SIGNAL. |

**Level B, copy-ready ticket:** for every setup that reaches TRIGGERED or later, a fixed 20-field plain-text ticket (MARKET … ALLOWED ACTION) is built **only from recorded values**: the setup's rule signal, the gate decision, the order and fill records, and the scan's recorded quote. Anything not recorded reads UNKNOWN or NOT APPLICABLE.
- A paper fill is labelled "simulated … NOT an executable price".
- The invalidation is labelled "checked at scans only: not a stop order, no guaranteed exit price".
- The planned loss is labelled "gaps can lose more".
- ALLOWED ACTION: "WATCH ONLY … No real-money trading is authorized."

Tickets are immutable, versioned `ticket` records (a new version when the content changes, with its SHA-256). STATUS.md prints the latest ticket per setup as plain text plus the version history; `usdjpy_pipeline.py ticket SETUP_ID [--version N]` prints one.

**Notification policy:**

| To the phone | Logged for the digest only |
|---|---|
| HIGH and RISK/SYSTEM alerts (never capped or suppressed) | setup watching, expired, resolved |
| setup triggered, blocked, entered, exited, invalidated; paper-position updates | W002 regime change; W003 "event within 24 h" |
| OFFICIAL RELEASE; W004 MoF; W005 outage; USD/JPY W001 big move | gold and GBP/USD W001 big moves |
| TEST; the daily digest | over the cap of 6 non-HIGH phone alerts per day; a title already sent within 6 h; anything not sendable within 12 h (never pushed stale) |

- **Records:** every routing decision is a `delivery` record with its reason, so nothing disappears silently.
- **MARKET WATCH:** W001–W005 meanings are unchanged; only their delivery changed.
- **Digest:** six short lines (system verdict, data currency, new setups, paper positions, attention items, what was logged without a phone alert), plus the backup line and "NOT A TRADING SIGNAL".
- **Status labels:** QUEUED / ACCEPTED BY PROVIDER / DELIVERED (owner-confirmed) / ACKNOWLEDGED / FAILED / LOGGED FOR DIGEST / EXPIRED UNSENT. HTTP 200 is only ACCEPTED BY PROVIDER.

**Tests:** +18 for D and E. Short phone text with the ticket pointer; ticket fields and labels; versions only on change; routing to the digest with reasons; dedup, daily cap and expiry, with HIGH never suppressed; a stale price blocks entries and exits; a rule-evaluation block defers instead of recording NO TRADE; preflight alerts only on persistence, with recovery. Plus the 11 preflight unit tests.

## F. Delivery, acknowledgements and independent risk monitoring (2026-10-31, branch `phase-fi`; merged only after Sunday's 17:02 ET scan is verified)

**Delivery status, as the system now reports it:** QUEUED → ACCEPTED BY PROVIDER (HTTP 200: the provider took it; **not** proof that a phone showed it) → DELIVERED (provider receipt, or owner-confirmed) → ACKNOWLEDGED; or FAILED, LOGGED FOR DIGEST, EXPIRED UNSENT, NOT ACKNOWLEDGED (expired).

- **Pushover receipts exist only for emergency priority**, which the system uses only for HIGH alerts. Each run now polls their official receipts (`/1/receipts/<id>.json`, read-only) and records, once each, delivered to a device, acknowledged, or expired without acknowledgement. Everything else stays ACCEPTED BY PROVIDER. The digest lists HIGH alerts that expired unacknowledged.
- **Real check:** the receipt of the 10-29 HIGH alert (the false "DIGEST MISSING") shows **delivered to a device (last 21:02:43 ET), never acknowledged, expired 21:07:43 ET**. It repeated every 5 minutes for an hour. Tapping "Acknowledge" on an emergency alert stops the repeats and is now recorded.
- **ntfy fallback:** fallback after 2 failed primary attempts, with backoff respected, is tested. Every failed attempt is recorded, nothing is resent after acceptance, and no notification or trading record is duplicated. A **real** send through the system's own ntfy sender (DEMO registry) is queued: it fell in quiet hours, so it goes at 07:01 ET 10-31. Arrival on the phone needs your confirmation.
- **Fix:** ntfy title headers are made ASCII-safe (a non-ASCII title would have failed the request).

**Independent risk monitoring (audit against the code):**

| Question | Finding |
|---|---|
| Risk checks at the claimed cadence | Yes: with a position or pending setup and FX open, every run (15 min) scans and manages positions (test) |
| Stale prices can't create false exits | Yes since Phase D while FX is open. **Defect fixed:** while FX was closed, `manage()` still exited on the closed-market last price (e.g. the scan right after Friday 17:00). Now an exit condition met without a tradable price becomes **EXIT PENDING** (one NORMAL alert) and fills at the first live price after the reopen, with the weekend gap taken as it comes. The pending decision takes precedence over later exit reasons |
| Exposure recalculated after fills | Yes: from the post-fill ledger, moving with the mark (test) |
| Drawdown and daily loss after interruptions | Yes: rebuilt from append-only position snapshots; a reopened registry gives identical peak, day-start and cash (test). Limitation: if the Mac sleeps through a day start, "day start" is the first scan of that day |
| Position or balance discrepancy → HALTED | Yes: reconciliation mismatch → HALTED + HIGH (existing test) |
| An exit condition can't go unnoticed | Price blocked → HIGH "PAPER POSITION UNMONITORED"; market closed → EXIT PENDING; **new:** a scan gap over 2 h with a paper position open → HIGH (was 30 h for everything) |
| Closures and weekend gaps | Handled as above; no stop is presented as guaranteed (tickets say "not a stop order, no guaranteed exit price") |

Approved risk limits unchanged. **Tests:** +10 (receipts, fallback, cadence, pending exits including through the scanner, interruption, exposure, gap with a position).

## G. Yahoo migration and duplicated scheduled work (2026-10-31, branch)

**Source check, criteria fixed before running** (`tools/migration_check.py`): S1 coverage of every instrument-day 10-26..30; S2 opens within 0.10% and S3 closes within 0.10% of the prices the books actually used; S4 watchlist month-end targets reproduced.

| Feed | S1 | S2 opens | S3 closes | S4 signals | Result |
|---|---|---|---|---|---|
| Alpaca IEX (single exchange) | pass | **14 of 75 over** (worst AGQ −0.42%) | **4 of 75 over** (worst AGQ −0.38%) | pass | **FAIL**: not used |
| Alpaca SIP (consolidated; free plan, data ≥ 15 min old) | pass | all within (worst TQQQ 0.075%) | identical | pass (09-30 and 10-30) | **PASS** |

**Replay proof** (books replayed from the start with the new source, compared with the stored books through 10-30): identical trade decisions (8 of 8), identical share counts, every book value within **0.0002%**. Stored books untouched.

**Migrated on the branch:** `paper_books.py` and `watchlist_signals.py` now read quoted/adjusted daily bars from Alpaca SIP, cash dividends from Alpaca corporate actions (added to the read-only allow-list), and the T-bill from FRED DTB3 instead of `^IRX`. Book and watchlist rules are unchanged; the source label in `paper/inputs/` changes.
- **Not verified:** dividends against a second vendor (no further Yahoo download). Only a plausibility check: 13 monthly payments for IEF/TLT, 4–5 quarterly for SPY/QQQ/VTI and the leveraged funds, none for GLD/SLV/USO/UGL/AGQ/UCO.
- **Still on Yahoo:** `tools/market_intel.py` (weekday step 2b; superseded by the runner) and `tools/brief_market_data.py` (Sunday brief; not in the approved scope).

**Proposal for the scheduled tasks (NOT applied; your approval needed):**

*Weekday task "watchlist-alerts":*
```diff
-## Step 2b: market data snapshot (read-only; indicative prices; no signal)
-cd … && .venv/bin/python -I tools/market_intel.py snapshot 2>/dev/null
-…record step snapshot…
-## Step 2c: official economic event poll (read-only; no signal)
-cd … && .venv/bin/python -I tools/events.py poll 2>/dev/null
-…record step events…
```
Why: the LaunchAgent takes an OANDA/Alpaca snapshot every hour and polls the official calendars four times a day plus after releases; step 2b is the last automated Yahoo use; step 2c duplicates the runner's poll. The finish line would drop "each market's status from step 2b". Steps 0, 1, 2, 3 and 4 stay (watchlist and paper books then run on Alpaca SIP).

*Sunday task "weekly-market-brief":*
- Option 1 (recommended): migrate `tools/brief_market_data.py` to the same Alpaca SIP module (needs your approval, since it wasn't in the 10-29 scope) and change the Sources line from "Yahoo Finance (yfinance), FRED" to "Alpaca (consolidated SIP), FRED".
- Keep Step C (private backup): the runner now pushes daily, but the Sunday push is still needed to include the new brief.
- Optional: point to the new weekly review (`live/usdjpy/reviews/`) in the Sunday notification.

*Also noted:* the Claude tasks' own PushNotification is unreliable (Remote Control); their NOTIFY lines could go through the plain-Python notifier instead. That's a larger change, so it's left as an option.

## H. Weekly opportunity review (2026-10-31, branch)

`src/live_usdjpy/review.py`; written automatically to `live/usdjpy/reviews/week_<Monday>.md` at the first run after Saturday 12:00 ET (FX closed), with a NORMAL "Weekly review ready" notification; `usdjpy_pipeline.py weekly-review [--date]` prints any week. Ten factual sections:
1. opportunities;
2. experimental ideas and their status;
3. approved paper signals (none);
4. resolved paper positions;
5. blocked, invalidated or expired setups;
6. notification failures and delivery counts;
7. readiness and data quality (verdict counts, DEGRADED/BLOCKED checks, runner gaps);
8. official events;
9. expected vs observed;
10. lessons and standing limitations.

Below 30 resolved signals it says **no statistical conclusion is possible**, and it never suggests parameter changes or new strategies. Real test on a copy of the live registry (week of 10-26) shows the F002 trigger and block, the F001 watch, the BoJ statement, the MoF release and the 27-minute sleep gap. **Tests:** +2.

## Financing audit, Phase A: read-only diagnosis (2026-11-01, 19:10–19:45 ET)

**Baseline:** git `50ebd74`; forward registry chain intact (277 records); 359 tests pass; consistent backup-API copy at `tmp/audit_financing/registry_baseline_20261101T1903.sqlite` (ignored). **Open paper position:** F002-2026-10 LONG, entered 2026-11-01 19:02 EST ($737.59, 0.074x). **No financing has accrued yet**: 0 financing records. The first accrual is the Monday 11-02 17:00 EST roll, booked by the 17:02 scan. The MontyFinance repo (read-only, `~/untitled folder/montyfinance-research`) was used only as untrusted reference.

### Defects (verified on current main, reproduced with synthetic inputs and the real functions)

| # | Defect | Where | Evidence |
|---|---|---|---|
| F1 | **A missing rate accrues at 0%** (`ru[0] or 0.0`, `rj[0] or 0.0`). The record keeps `r_usd = None` with an "UNKNOWN" note, but equity is booked as if the rate were 0 | `src/live_usdjpy/paper.py` `accrue` | Long 0.5x, 1 roll: USD leg +0.5556 with the rate, **0.0000** without (hand: 5000 × 0.04/360). Short: −0.5556 vs 0.0000 |
| F2 | **A failed fetch is cached as the day's rates.** A later success is ignored until the next UTC date (00:00 UTC = 19:00 EST) | `tools/usdjpy_pipeline.py` `fetch_rates` (the cache key is the UTC date; a failed leg is stored as `(None, "UNKNOWN …")`) | Timeout, then FRED answers 15 minutes later: still `None` from the cache; fixed only on the next UTC day |
| F3 | **No HTTP status check or parse validation:** a 503 page or an empty body becomes "UNKNOWN (IndexError)", so it is F1 again | `fetch_rates` | 503 HTML and empty body reproduced |
| F4 | **No maximum age** on either series; old observations are reused indefinitely (the observation date survives only inside the info string) | `fetch_rates`, `accrue` | Design inspection; the JPY observation in use is 2026-09-01 (61 days old today) |
| F5 | **False reconciliation HALT possible:** the v2 parity replay uses the *first known* rate for the whole path (default 0.0), while the ledger books 0 on missing days | `paper.py` `v2_replay` | 0.5x, one valid roll then 4 missing: ledger vs v2 differ by **$2.51 > $2 tolerance → HALTED**. With all rates valid, the gap is a constant ~$0.83 (entry-day timing) and never trips |
| F6 | **Catch-up rolls use today's rates for past rolls** (mild accounting look-ahead after an outage) | `accrue` (one `rates` dict for all rolls since the last) | Design inspection |
| F7 | **Scorer baselines treat a missing rate as 0** (`r_usd or 0`). Reporting only, not the ledger | `src/live_usdjpy/scorer.py` `pair_pnl` | Design inspection |
| F8 | **ETF books:** DTB3 is forward-filled with no age limit. A total fetch failure fails the whole update (fail closed: no 0%, the books simply aren't updated). A FRED gap longer than 15 days would give NaN interest | `tools/paper_books.py` (`irx.ffill()`), `tools/market_data_alpaca.py` `fred_dtb3` | Design inspection; no NaN in `values.csv` |

**Not defects:**
- One leg failing doesn't affect the other leg (reproduced).
- A genuine 0% is recorded as `0.0`, distinct from `None` (reproduced).
- Observations aren't relabelled with today's date; the original date is kept in the info string.
- No rate input uses data before it is published; DTB3 for day *d* is the prior trading day's value.
- No Yahoo data feeds any forward, paper or watchlist calculation.

**Already occurred?** **No.** No financing has accrued in the forward ledger. The ETF books' cash interest through 10-30 used Yahoo ^IRX (3.998%/yr on 10-30) with no NaN or 0 rows. Earlier failed rate fetches can't be detected after the fact (fetch outcomes aren't logged), but before 11-01 19:02 EST there was no open position for them to affect.

**Out of scope, flagged only:**
- `tools/events.py` `reactions()` still downloads **Yahoo 1-minute data** on every automated event poll. It feeds no calculation, but it is still automated Yahoo collection.
- The pre-registration says results are reported "with and without financing"; the scorer doesn't show a "without" variant.

### Rate definitions

| Series | Use | Source and ID | Type | Units | Frequency, observation date, typical availability | Revisions | Latest (seen 11-01) | Fitness as a financing proxy |
|---|---|---|---|---|---|---|---|---|
| DTB3 | Forward ledger, USD leg; ETF books' cash interest | FRED (Fed H.15), DTB3 | 3-month T-bill, secondary market, **discount basis** | % per year | Daily (US business days); posted with a ~1 business-day lag (Friday's value appears Monday) | Rare | 4.00% on 10-29 | Short USD rate; a reasonable stand-in for the USD side of tom-next, but not an overnight rate and not discount-to-yield converted |
| IRSTCI01JPM156N | Forward ledger, JPY leg | FRED mirror of OECD MEI: Japan "immediate rates: call money/interbank" | **Monthly average** of the overnight call rate | % per year | Monthly, dated the 1st of the month; September's value was available by 10-29 (~1 month after month end) | OECD can revise | 1.043% for Sep 2026 (Aug 0.977%) | Right instrument (overnight call), wrong timing: a monthly average up to ~3 months old lags BoJ policy moves |
| JGB 1Y (MoF) | **Historical Study 4 only** (`usdjpy_study1`, frozen) | MoF JGB yields | Government bond yield | % per year | Daily | — | not fetched by the forward system | Not used by the forward ledger. MontyFinance's "three definitions" mixes two systems |
| BoJ uncollateralized overnight call rate (daily) | **Not used** | BoJ Time-Series Data API | Overnight money-market rate (the policy-target rate) | % per year | Daily, next business day | Rare | not fetched | Best proxy for the JPY side; would be a new source |

**Against the frozen pre-registration** (§4: "US: 3-month T-bill (FRED DTB3). Japan: overnight call rate (BoJ Time-Series API or FRED mirror)… **A missing rate input uses the last known value, flagged STALE.** Results are then reported with and without financing"):
- **(a) Compliance fix:** F1 books 0% where the pre-registration requires carrying the last known value forward, flagged STALE. F2 and F3 are how that happens.
- **(a) Compliant:** DTB3, and the 1.00% (base) and 1.50% (stress) admin fees.
- **(b) Amendment candidate:** "FRED mirror" is ambiguous. FRED has no daily mirror of the BoJ call rate; the code uses the OECD monthly average, which is defensible but lagged. A v0.4 amendment could name the BoJ daily rate (new source).
- **(b) Amendment candidate:** the pre-registration sets no maximum age for carry-forward. Adding one, with UNRESOLVED beyond it, tightens it and would be part of v0.4. Never silently.

**Broker financing, kept separate:**
- **A, our frozen proxy:** USD leg × DTB3 × d/360; JPY leg × call rate × d/365; minus |USD exposure| × 1.00%/yr × d/365; at each 17:00 ET roll; Wednesday ×3.
- **B, OANDA US's stated method** (official page, verified in the 10-29 report): notional × (liquidity-provider tom-next rate ± an annualized admin fee) ÷ 365, charged at 5 p.m. ET, typically ×3 on Wednesdays; 1.00%/yr for the bucket that includes USD/JPY.
- **C, verified broker observations:** none.
- **D, estimates:** everything we book is A, an estimate.
- No change to the cost assumptions is proposed. A separately approved check of OANDA practice financing charges could be added later.

**The MontyFinance prototype** (`research/bot_candidates/freshness_gate.py`):
- **Tests:** 8 test functions with 11 assertions. Its report says both "8 tests" and "5 unit tests"; 8 is correct.
- **Coverage:** frequency and lag classification for DTB3, the monthly JPY series and COT; carry-forward.
- **Not covered:** fetch, cache, accounting, 0% vs missing, negative or invalid values, or parity.
- **Flaw:** `resolve_rate` gives a fresh value the observation date `as_of`, i.e. **relabels it with today's date**.
- **Stale threshold:** ~156 days for the monthly series.
- **Disagreement:** it says the latest JPY observation on 10-31 was 08-01; we observed **09-01 on 10-29**.

### Proposed policy (implemented only after your approval)

- **States:** VALID, VALID_ZERO, LATE, STALE, MISSING, FETCH_FAILED, UNRESOLVED. Each observation stores source and ID, currency, raw value and units, normalized decimal, observation date, fetch time, last successful retrieval, age, cadence, state, carried-forward flag and error.
- **Validation:** finite numbers only; percent → decimal once; −5% … +25% accepted (negative is valid); an observation date in the future is rejected.
- **Cache:** the last *successful* observation per series is kept separately from the last attempt and its error. A failure is never cached as success. On failure, retry at the next run, at most once per 15 minutes (no storms). A later success replaces the failure state. Carried values keep their original observation date.
- **Thresholds (observation age at roll time):**
  - **DTB3:** VALID ≤ 3 US business days (normal lag 1–2, plus one for a holiday weekend); LATE, carried forward and flagged, at 4–5; STALE above 5 business days (a full week missing is an outage).
  - **IRSTCI01JPM156N (observation dated the 1st of the month):** VALID ≤ 95 days (month span ~31 + verified ~30-day publication lag + slack); LATE at 96–125 (one more month missing); STALE above 125 days. That is stricter than the prototype's ~156, so months-old data doesn't stay acceptable just because the series is monthly.
- **Accrual:**
  - VALID, VALID_ZERO and LATE book normally; a carried value is labelled CARRIED_FORWARD with its original date. This **is** the pre-registration's "last known value, flagged" rule, so it's a compliance fix.
  - STALE or no value at all: the roll is booked as **UNRESOLVED** (position, roll, missing source, reason, inputs), never 0%. Once acceptable data exists, an appended **TRUE-UP** record carries the exact amount per original roll date. **This part goes beyond the pre-registration: v0.4 amendment, your approval needed.**
  - Each roll uses the observations available at that roll's time, which fixes F6.
- **Parity (F5):** the v2 replay uses the same per-roll resolved rates. UNRESOLVED rolls are excluded from both sides and listed, so they can't cause a false HALT.
- **Readiness:** a stale or unresolved financing input is **DEGRADED, not BLOCKED**. At the maximum 0.5x size a full day's carry is about $0.28, roughly 0.003% of equity, far below every risk limit (−1% daily, −3%, −5%). It can't materially move sizing or risk checks. No numeric limit changes.
- **Rollback:** a config flag (`live_usdjpy.financing.policy: v1|legacy`).
- **Recording:** one canonical JPY definition, recorded in the research memory ledger as a compliance note.
- **ETF books:** same states for DTB3; no NaN or 0 interest is ever booked silently.
- **Scorer baselines:** use the same resolved rates.

**Can the fix be in place before the Monday 17:00 EST roll?** Yes, if you approve by about Monday 14:00 ET. Implementation and tests take a few hours, and edits go in between runs. Without the fix, Monday's accrual is still correct whenever FRED answers, as it did all weekend; the risk is only an outage at that moment. On F002's 0.074x position the worst case is about $0.08 a day.

**Reopen-grace proposal (separate approval given; built after this phase):** 30 minutes after the Sunday 17:00 ET reopen. Outage/recovery alerts for STALE or UNAVAILABLE prices are not sent if the price is LIVE again by the 17:32 scan. Everything is still recorded, and preflight's 2-scan rule and every HIGH alert are unchanged. Today's prices recovered by 17:17.

## Financing audit: implementation, reconciliation and final status (2026-11-01 evening, EST)

### Phase E: reconciliation

**None needed.** The forward registry held **0 financing records** before the fix went live (21:48 EST). The only open position, F002-2026-10, has not reached a roll yet; its first is 2026-11-02 17:00 EST. The ETF books' cash interest used valid T-bill data on every processed day (no NaN, no zero rows). No correction records are proposed.

### A. Defect verification

| Claim / finding | Exists on current main before the fix? | Path | Evidence | Fixed before? |
|---|---|---|---|---|
| A missing rate accrues at 0% | **Yes** | `paper.py accrue` (`ru[0] or 0.0`) | Reproduced: USD leg $0.5556 → $0.0000 | No |
| A failed fetch is cached for the day | **Yes** | `usdjpy_pipeline.fetch_rates` (UTC-date cache) | Reproduced | No |
| No HTTP or parse validation | **Yes** | `fetch_rates` | 503 page and empty body → missing → 0% | No |
| No maximum age | **Yes** | `fetch_rates` / `accrue` | Inspection | No |
| False HALT through v2 parity (missing rates) | **Yes** | `paper.v2_replay` (first known rate, default 0) | 0.5x with 4 missing rolls: $2.51 > $2 | No |
| Catch-up uses today's rates for past rolls | **Yes** | `accrue` | Inspection | No |
| "JPY defined three ways" | **Partly.** JGB 1Y is in the frozen *historical* study config, not the forward ledger | — | `config.yaml usdjpy_study1` | — |
| A genuine 0% treated as missing | **No** (0.0 is recorded distinctly) | — | Reproduced | — |

### B. Data sources

- **US:** FRED DTB3, 3-month T-bill (discount basis), daily, ~1 business day publication lag.
- **JPY:** FRED IRSTCI01JPM156N, the OECD monthly average of the call rate, dated the 1st of the month, available about a month after month end. Now the canonical v0.4 definition.
- **Not used:** the BoJ daily call rate. It would be the better JPY proxy; it's a **separate proposal, not applied**: a new read-only source (BoJ Time-Series Data API), its own validation, and a v0.5 amendment.
- **What remains an approximation:** everything. DTB3 isn't a tom-next rate and the OECD series isn't a broker charge. The admin fee (1.00% base, 1.50% stress) follows OANDA US's stated fee, but no broker charge has been observed. **Broker financing is still estimated.**

### C. Changes (commits `a8ef21a` … `8ca22ff`; live from 21:48 EST)

- **`src/live_usdjpy/financing.py` (new):**
  - strict fetch validation;
  - a cache of successful observations only, each with its first-seen time;
  - one retry per 15 minutes after a failure;
  - per-roll resolution: VALID / VALID_ZERO / LATE (carried forward) / STALE / MISSING, with the original observation date and age.
- **`paper.py`:**
  - per-roll rates;
  - UNRESOLVED rolls book nothing and record the legs;
  - an appended TRUE-UP for the original roll date (to the legs, or to cash with a recorded conversion if the position has closed);
  - recompute handles both;
  - the v2 parity replay uses the same per-roll rates and is deferred, not failed, while a roll is unresolved;
  - `financing.policy: legacy` for rollback.
- **Runner:** uses the cache. Readiness reports financing as DEGRADED only. Scorer baselines use the same per-roll rates, and say UNKNOWN (never 0) if a roll is unresolved.
- **ETF books:**
  - The T-bill observation date and age are kept in `paper/inputs/`.
  - LATE is carried forward and flagged.
  - STALE or missing leaves the day UNRESOLVED (`paper/interest_unresolved.csv`, append-only, in the crash-safe commit set), with a TRUE-UP later.
  - The DTB3 fetch is validated.
- **Also approved and applied:**
  - **W005 reopen grace:** stale-price outages within 30 minutes after the Sunday 17:00 ET reopen are recorded, and alerted only if prices are still stale afterwards. HIGH alerts are unaffected.
  - **Event reactions:** the Yahoo 1-minute download was removed from `tools/events.py`. New reactions read UNKNOWN; earlier ones are kept. A compliant source (for example OANDA practice candles) is a later proposal; no new endpoint was added.
- **Compatibility:** old records are unchanged and still read. The old tuple-shaped rate input still works, and a None in it is now UNRESOLVED.

### The ~$0.83 ledger vs v2 parity gap with all rates valid

- **Cause:** the two sides count financed days differently.
  - The ledger books whole 17:00 ET rolls, including the roll right after entry. Its Wednesday triple roll covers the coming weekend in advance (FX spot settlement).
  - The v2 replay accrues calendar days between its first and last daily mark.
- **Measured** (0.5x, today's rates, net carry $0.2757 per financed day): Mon–Tue 1.00 day of carry; Mon–Wed 3.00; Mon–Fri 3.00; Mon to next Mon 1.00; Mon to next Wed 3.01; 4 weeks 3.02.
- **It doesn't grow with hold length:** it swings between about 1 and 3 days of net carry.
- **It isn't an accounting error:** it is a timing-convention difference (prepaid weekend vs calendar accrual).
- **Headroom:** the $2 tolerance equals 7.3 days of today's carry at the maximum size. It could be exceeded only if net annual carry rose above about 4.9%. Tolerance unchanged.

### Flagged, not fixed (outside the approved scope; decision needed)

**False reconciliation HALT from price moves on the entry day.**
- **Cause:** `v2_replay` groups marks by UTC date and takes each day's *last* mark. On the entry day, that treats the latest price as the entry price, so every move between the fill and 19:00 EST (00:00 UTC) shows up as a ledger-vs-v2 mismatch. From the next UTC day the gap freezes at that amount.
- **Today:** F002-2026-10's last stored reconciliation shows ledger +$0.98 vs v2 −$0.11, a $1.09 gap before any financing.
- **Risk:** a move of about 43 pips from the entry mid before Monday 19:00 EST would push F002 past $2, giving HALTED plus a HIGH alert. At 0.5x, about 6 pips would do it.
- **Effect if it happens:** new entries are blocked until a manual `resume`. Exits, marks and the ledger are unaffected.
- **Proposed fix:** start the replay from the entry fill's mid instead of the day's last mark (a fix to the comparison, not the tolerance).

### D. Reconciliation

No affected records; nothing recorded vs recalculated to show; no corrections proposed.

### E. Testing

- **Baseline:** 359 pass (`50ebd74`).
- **After:** **398 pass** in the main checkout, including the private paper-data tests; 0 failures. +39 new tests:
  - fetch failures: timeout, 429, 5xx, empty, HTML, malformed, NaN, units, future date;
  - cache and retry, one leg failing, cache kept through an outage;
  - ages: Monday after a weekend, Fed holiday, monthly lag, LATE and STALE edges;
  - zero and negative rates, no look-ahead;
  - **independent arithmetic reference** (shares no code with the simulator): long and short, both legs, a Wednesday triple, a rate change mid-week, sign checks;
  - idempotent rescans, no accrual without a position, UNRESOLVED then TRUE-UP with exact reference amounts (also after the position closed);
  - reconciliation exact and deferred (no false HALT), parity with rate changes, legacy rollback;
  - ETF T-bill states, preflight DEGRADED-only, events without any download, the W005 grace;
  - the v0.4 hash and threshold pin.
- **Replay proof on copies:**
  - Paper books: values byte-identical, trades as before, the copies of `paper/` untouched.
  - Forward ledger: independent recomputation equals the stored ledger for both rules.
  - Signal and gate code (`rules.py`, `gate.py`, `scanner.py`) and the v0.2/v0.3 documents: byte-unchanged.
- **Live:** the 22:02 EST scan on the new code was READY. Financing rates OK: DTB3 VALID (10-29, age 1), JPY VALID (09-01, age 61). Reconciled; empty error log.

### F. Integrity confirmations

- F001 and F002 rules, signals, entries, exits, stops, targets, sizing, risk limits, blackouts, guards and cost values: unchanged.
- Pre-registration v0.2 and v0.3 hashes: unchanged and pinned. v0.4 frozen (`d85b8fd`, sha256 `41e2e561…`), recorded in config, the research memory and the forward registry, before any financing accrued.
- Historical N = 142; forward N = 2.
- Holdout untouched. No historical backtest.
- No existing record edited.
- No live trading, order endpoint, account, credential or install.
- No MontyFinance component imported.

### G. Status

| Item | Status |
|---|---|
| FIX VERIFIED (defects reproduced; fix proven by tests and the reference) | **Yes** |
| FIX IMPLEMENTED | **Yes** |
| FIX TESTED (398 pass) | **Yes** |
| ACTIVE IN THE RUNNING SCANNER | **Yes, since 21:48 EST 2026-11-01**; first accrual under it: 2026-11-02 17:00 EST |
| HISTORICAL CORRECTIONS PENDING | **None** (no financing had accrued) |
| BROKER FINANCING | **Still estimated** (proxy model; no verified broker charge) |

### H. Decisions for you

1. **The entry-day parity defect:** approve the fix (replay from the entry fill's mid), or accept the false-HALT risk with a manual `resume` if it happens.
2. **Later proposals:** the BoJ daily call rate as the JPY source (v0.5), and a compliant source for event reactions.

### Entry-day parity fix (owner-approved 2026-11-01; live from 22:25 EST)

- **Fix:** `v2_replay` now prices the day a position opens or closes at that fill's mid, and revalues an open position at the ledger's current mark. Tolerance unchanged ($2 per $10,000).
- **Regression test:** a F002-like 0.074x entry, then a 50-pip move before the next 19:00 EST. It **failed before** (ledger +$2.34 vs v2 −$0.11, gap $2.45, HALT) and **passes after**. Exit days were checked too: a $0.0000 gap at 0.074x and $0.0022 at 0.5x.
- **Replay proof on a copy of the live registry:** F002's gap is $0.9437 with the old replay and $0.0002 with the new one at the same mark. The exact recomputation is unchanged.
- **Live:** the 22:32 EST scan is clean, and F002 shows ledger +$0.8587 vs v2 +$0.8585 (gap $0.0002). **No false HALT occurred before the fix**: there are 0 risk_state records.
- **Tests:** 399 pass.
- **Deferred proposals (not applied):** the BoJ daily call rate as the JPY source (v0.5), and a compliant source for event reactions.

## Next round, item 1: dead-man switch proposal (2026-11-01; nothing wired in)

**Problem:** when the Mac sleeps, dies or is off, nothing runs and nothing can alert. The gap is only recorded at the next wake, as on 10-31 13:52–14:32. An external service that expects a regular ping and alerts when it stops covers that.

**Design (both options):**
- After each successful run, the runner sends one HTTPS GET to a secret ping URL: no body, timeout 10 s, never blocking or failing the run.
- After a RUN ERROR it sends the `/fail` variant where the service supports one.
- The URL (it contains the secret) lives only in the Keychain (`trading-research-deadman-url`, plus `-weekday` if two checks are used). It is never printed, logged or stored in records; only "ping OK/failed" with a timestamp goes into the runner state.
- **What leaves the Mac:** the fact and time of a run, the Mac's public IP address and the HTTP client's user-agent string. No market data, no records, no credentials.

**Your timing (45 min while FX is open, longer when closed).** The runner fires every 15 min around the clock, so it pings every 15 min regardless of FX hours. Two checks give your split:

| Check | Schedule | Alerts after | Covers |
|---|---|---|---|
| A, weekday | cron `*/15 * * * 1-5`, time zone America/New_York, grace 30 min | **45 min** of silence, Mon–Fri | The FX week (Sunday evening excepted) |
| B, always | simple period 15 min, grace 6 h | **6 h 15 min** of silence, any day | Weekends and Sunday evening (configurable) |

**Options compared** (vendor pages read 2026-11-01):

| | **healthchecks.io (recommended)** | **Cronitor** |
|---|---|---|
| Free tier | Hobbyist $0: **20 checks**, 100 log entries per check | Hacker $0: **5 monitors**, 1 user, 5-minute fastest frequency |
| Heartbeat type | Simple period + grace, or cron/OnCalendar with a time zone; `/start`, `/fail`, `/<exit code>` signals | Cron/heartbeat monitors included on every plan |
| Alert to your phone | **Official Pushover integration, priorities silent to Emergency**, plus email. ntfy: no official integration found; possible through a generic webhook (unverified) | Email, Slack, Discord, Teams, **webhooks** (ntfy via webhook possible). **No Pushover integration listed**; SMS not on the free plan |
| Rate limit / body | ≤ 5 pings a minute; stores the body up to 100 kB (we send none); GET, HEAD or POST | n/a for our once-per-15-min ping |
| Operator, hosting, privacy | SIA Monkey See Monkey Do (Riga, Latvia). Hosting: Hetzner; encrypted backups on AWS. Logs IP, user agent and timestamps; backups kept up to 2 months; inactive accounts closed after about 13 months. Open source (could later be self-hosted on a *different* machine) | US company; one dashboard user on the free plan; retention not stated for the free plan |
| Cost | $0 | $0 |

**Recommendation:** healthchecks.io.
- It has a native Pushover integration, so a missed-run alert arrives through the same channel as everything else, and can use Emergency priority (repeats until acknowledged).
- Its free tier comfortably covers 2 checks.
- It's open source, with an EU operator.
- Downside: one more third party learns when the Mac runs and its IP address.

**Your one-time setup (after you approve; credentials never go through me):**
1. Create a free account at healthchecks.io.
2. Create check **A**: Schedule = Cron, `*/15 * * * 1-5`, Time zone `America/New_York`, Grace 30 minutes.
3. Create check **B**: Period 15 minutes, Grace 6 hours.
4. Integrations → Pushover → subscribe. Use priority Emergency (or High) for "down" and normal for "up". Optionally add email.
5. Store each ping URL in your own Terminal (it prompts for the value, so nothing lands in shell history):
   - `security add-generic-password -a "$USER" -s trading-research-deadman-url -w` (check B)
   - `security add-generic-password -a "$USER" -s trading-research-deadman-url-weekday -w` (check A)
6. Tell me "dead-man set".

I then wire the ping into the runner between runs, with tests (no network in tests) and a real check that both checks turn "Up".
