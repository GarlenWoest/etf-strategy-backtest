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
