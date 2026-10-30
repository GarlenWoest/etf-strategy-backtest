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

_(filled in below after the first live snapshot and restore test)_
