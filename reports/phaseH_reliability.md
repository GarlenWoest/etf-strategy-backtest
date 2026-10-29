# Phase H: risk-accounting consistency, operational reliability and backups (2026-10-28)

_216 tests pass (+6 this phase). Changed: `tools/heartbeat.py` (run states, step and notification-delivery records), `tools/backup_private.py` (event-page cache excluded); tests in `tests/test_heartbeat.py`, `test_backup_private.py`, `test_paper_books.py`. The scheduled-task prompt changes are **drafted, not saved** (section 3)._

## 1. Risk-accounting consistency

| Item | Finding | Status |
|---|---|---|
| FX ledgers, hard 1x (`config.yaml` `max_gross_notional_x: 1.0`) | Engine v2 enforces it at every close; trims return to 0.95x; every rebalance is costed (24 randomized tests). v1 (frozen) never exceeded 1.00x either | Consistent |
| v2 band 0.10 with reset 0.95 | After a trim to 0.95x, a decision target of 1.0x is inside the band, so no re-size follows; exposure drifts between about 0.9x and 1.00x | Consistent (documented) |
| Paper costs | 0.07% one-way (unleveraged), 0.10% (leveraged), the same as Study 1; applied to the open price | Consistent; **unverified as real costs** |
| Paper cash and margin | Buys are capped at cash; long only; no margin | Consistent |
| **Leverage in paper books** | No margin, but leveraged ETFs give economic exposure above 1x. Book A's V074 sleeve holds 25% UPRO + 25% TQQQ (3x funds), about 1.5x of the sleeve and about 1.0x of Book A overall. Book B's rules allow up to 100% in a 3x ETF (**up to about 3x**). | **Decision for you:** does the hard 1x rule apply to paper books' economic exposure? |
| **Book B stops** | Checked once a day at the close, **only after the 5-trading-day minimum hold**, then filled at the **next open's price**, not the stop price (gap risk). Now pinned by a test: a close below a 348 stop on 10-28 sold at the 11-02 open of 338, less costs. | **Decision for you:** should a stop override the minimum hold? |
| Missing data, late or missed runs | A missing open defers the order with an alert; a missing close values at the last close and skips that day's exit check; no bar for a day gives an alert; catch-up fills are flagged late. Updates are idempotent (days ≤ `last_update` are skipped) | Consistent (P1/P2 fixes, 10-26) |
| Three kinds of activity | Historical simulation (engines, frozen studies) / paper decisions (fictional books, fills at daily opens) / **no execution capability** (no broker, no orders) | Kept separate |

## 2. Operational reliability: run states and notification delivery

**Run states, all recorded in `live/heartbeat.json`:**

| State | Meaning |
|---|---|
| started | Written when the run begins |
| completed | Finished ok, with no failed step |
| partial | Some steps failed, or an error was reported after some steps succeeded |
| failed | No step succeeded, or the run never finished |
| missed | Derived: an expected NYSE trading day with no completed or partial run |
| scheduled | Derived: the next Mon–Fri 16:45 ET run, shown in the status line |

- **Step results:** recorded with `heartbeat.py step`: watchlist, paper, snapshot, events, bookb, brief, backup.
- **Notification delivery:** each push notification is recorded with `heartbeat.py notify`: delivered yes / no / unknown, plus the tool's reason.
- **The Sunday status line** now reports partial runs, the notification count, any not confirmed delivered, and the next scheduled run. It ends with **"ALERT: notifications NOT DELIVERED: …"** whenever one failed.
- **Compatibility:** old records still work, and `heartbeat.py runs` prints recent runs with their states.
- **Known gap, recorded and not back-filled:** the four undelivered notifications of 10-26 predate this feature (memory ledger, 10-28).

**Idempotent and recoverable:** paper updates, the snapshot (deduplicated by key), the event store (merge plus change log) and the backup (commits only on change) can all be re-run safely. A retried run gets a new run id, so nothing is overwritten.

**Reliable scheduling.** Both tasks are Claude-app tasks: they run only while the app is open and the Mac is awake; missed runs catch up at the next launch, and the heartbeat records the gap.

| Option | Runs when the Mac is asleep or off | Claude usage | Cost | Approval needed |
|---|---|---|---|---|
| Current Claude-app tasks | No | Yes | $0 | — |
| macOS LaunchAgent for the plain-Python steps (snapshot, events, paper update) | No (wakes with the Mac) | None | $0 | Writes `~/Library/LaunchAgents` (outside the project) |
| GitHub Actions on the private backup repo | **Yes** | None | Free tier minutes for private repos (limit to verify) | External hosting; private data would run on GitHub |
| Small cloud VM | Yes | None | Paid | External hosting |

Nothing has been enabled.

## 3. Drafted task changes (not saved; diffs shown in chat)

- **Weekday task:**
  - record each step;
  - record each notification's delivery;
  - move "finish" to the end, so notifications are recorded on the same run.
- **Sunday task:**
  - record the bookb, brief and backup steps and each notification's delivery;
  - put a bold **ALERT** line under the brief's title when the status line contains one;
  - finish last.

## 4. Backups

- **Public repository** (`origin` = GarlenWoest/etf-strategy-backtest, main = `92234a2`): 29 local commits are unpushed (as of this report).
  - Tracked files: code, reports and our own logs; no `data/`, `paper/`, `live/`, `briefs/`, `results/`, `tmp/`.
  - Verified absent from history: the BLS contact address (0 objects) and the HistData quotes (0 objects).
  - **Still in history:** a few raw Yahoo prices in `reports/infrastructure_audit.md` (watchlist fills and signal closes, today's fill opens, Book B's fill). Decision for you before pushing.
- **Private backup** (`.backup.git` → GarlenWoest/trading-research-paper-log):
  - Allowlist: `paper/`, `live/`, `briefs/`, enforced before every commit. `live/events/cache/` is now excluded (re-fetchable official pages).
  - Two local snapshots exist.
  - **Push still failing:** the repository and token don't exist yet. The steps below are yours.

### Your steps for the private backup (credentials stay with you; never paste them into Claude)

1. **Create the repository** on github.com: **New repository** → owner **GarlenWoest**, name **`trading-research-paper-log`**, **Private**. Do **not** add a README, .gitignore or licence. Click **Create repository**.
2. **Create a fine-grained token:** github.com → your avatar → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
   - Name: `trading-research-paper-log backup`; expiration: your choice (e.g. 90 days). Note the date.
   - **Repository access → Only select repositories → `trading-research-paper-log`**.
   - **Permissions → Repository permissions → Contents: Read and write.** Metadata becomes read-only automatically. Nothing else.
   - **Generate token** and copy it (shown once).
3. **First push from your own Terminal** (not this chat). This stores the token in the macOS Keychain for this repository's path only, because the backup is configured with `credential.useHttpPath=true`:
   - `cd /Users/garlenwoest/Trading/trading-research`
   - `git --git-dir=.backup.git --work-tree=. push origin main`
   - When asked: **Username** `GarlenWoest`; **Password**: paste the token.
4. **Check:** `.venv/bin/python -I tools/backup_private.py run` should print **`BACKUP OK: …`**. Then tell me, and I'll confirm the status read-only.
5. **Before the token expires:** generate a new one, delete the old Keychain item (Keychain Access → search "github.com" → the item for this repository), then repeat step 3.

## 5. Restore test of the private backup (2026-10-28, 19:20 ET; read only)

The backup was cloned twice into a git-ignored scratch folder (`tmp/restore_test/`, deleted afterwards): once from GitHub, using your Keychain credential (never seen by Claude), and once from the local `.backup.git`. The originals were not touched, and nothing was pushed.

| Check | Result |
|---|---|
| GitHub clone head = local clone head = `.backup.git` HEAD | All `8d11673` (snapshot of 10-28 18:31 ET) |
| Git object integrity (`git fsck --full --strict` on the GitHub clone) | Clean |
| Files restored | 16, all under `paper/`, `live/` or `briefs/`; 0 outside the allowlist; 0 event-cache files |
| Completeness | Every current file in `paper/`, `live/` and `briefs/` (cache excluded) is in the backup; none missing |
| Accuracy | All 16 restored files are byte-identical (SHA-256) to the GitHub clone, the local clone and the originals. No original has changed since the snapshot |
| Book B journal | The entry fingerprint, recomputed from the restored journal, matches the restored `journal_hashes.csv` |
| Parsing | Every restored JSON and JSONL file parses |
| Access | Unauthenticated GitHub API and web requests: 404 |

**Not tested:** restoring into the live folders, which would overwrite the originals. A real restore would copy these files back after the app is closed.

## 6. Crash safety and persistence (master prompt step 2, 2026-10-29)

### What changed (monitoring scripts only; no paper-book trading rule changed)

| Change | Where | Why |
|---|---|---|
| `tools/atomic_io.py`: temp file + fsync + atomic rename; fsynced appends; torn-line repair; tolerant JSONL reader | new | One crash-safe writer for all monitoring files |
| Every state and report write is atomic | `paper_books.py`, `heartbeat.py`, `watchlist_signals.py`, `events.py`, `market_intel.py` | An interruption left a truncated `state.json`/`heartbeat.json`/`events.json` (Phase A finding 1) |
| **Paper update is crash-safe in place:** each processed day appends its trades and values, then saves the state, which records `committed_bytes` and `committed_sha256` of every append-only file. On the next run, bytes beyond the committed size are moved to `paper/recovery/`, logged in `paper/recovery_log.csv`, and that day is redone. An edit to committed content is never "repaired": the run stops with an error (and journal edits still raise the tamper alert) | `paper_books.py` | Phase A finding 2: a crash between the appends and the state save could duplicate rows and fills |
| **Inputs kept as first received:** `paper/inputs/<date>.json` (opens, closes, dividends, T-bill rate used that day) | `paper_books.py` | The replay proof showed Yahoo revised two 10-26 opens after the fills; without stored inputs, history can't be replayed exactly |
| **Explicit status lines:** `PAPER UPDATE OK: …` or `PAPER UPDATE ERROR: …` (never silent); `HEARTBEAT FINISH OK: run recorded as …` | `paper_books.py`, `heartbeat.py` | 10-29: a successful update printed nothing and was recorded as an ERROR (Phase A finding 3) |
| Backup excludes temp files (`**/.*.tmp`) | `backup_private.py` | A leftover temp file must never enter the backup |

**Two bugs found by the new tests and fixed before commit:**
- `init()` saved the state before writing the journal header, so the header was uncommitted.
- An empty file left after recovery made the CSV writer skip its header.

### Proof that the books are unchanged

1. **Golden equivalence (tracked test).** Old and new code, run on the same synthetic 3-week scenario (fills, a Book B planned exit, a dividend, a month-end rebalance), produce byte-identical `values.csv`, `trades.csv`, journal and fingerprints. The test pins their SHA-256 hashes.
2. **Real books (private test, skipped where `paper/` is absent).** Replayed from the start with journal entry #1 as written, on one price download:
   - **`values.csv` is reproduced byte for byte** through 10-29;
   - `trades.csv` matches exactly except one fill price that differs in the 4th decimal: the 10-26 VTI open was stored to 4 decimals, so its exact value can't be recovered.

   This needed the five 10-26 opens set back to the recorded values; Yahoo had since revised VTI and GLD by about 0.002–0.005.
3. **Old vs new code on that real download:** all four files byte-identical, state identical apart from the two new commit fields.
4. **End to end on a copy of the real books:** `PAPER UPDATE OK: no new trading day to process`; all four files unchanged; commit fields added. Watchlist, snapshot and event poll also ran cleanly, with no temp files left.

### Tests (235 pass; 18 new)

- **Interruption at every append** (both before the write and as a half-written line), then a restart: books identical to an uninterrupted run, with no lost day and no duplicate row or fill.
- **Crash between the rows and the state commit:** recovered, with the removed bytes kept and logged.
- **Duplicate run on the same day** changes nothing.
- **Edited committed ledger:** the run stops and touches nothing. **A file shorter than committed** is an error. **Journal edit:** the tamper alert still fires and nothing is truncated.
- **Atomic state write:** a failed rename keeps the old file and leaves no temp files.
- **Legacy state** without commit fields loads and runs.
- **Inputs** are kept for every processed day.
- `atomic_io`: replace, torn-line repair, mid-file corruption raises; a guard test that no monitoring script uses in-place writes; the backup excludes temp files.

### Persistence choice for the new USD/JPY system: SQLite (stdlib `sqlite3`, version 3.53.4 here; no install)

| | SQLite, WAL, `synchronous=FULL` | Atomic JSON/JSONL files |
|---|---|---|
| Multi-record commits (registry row + order + fill + position + notification together) | One transaction: all or nothing | Needs a hand-built commit protocol (as just done for the paper books) |
| Idempotency (client order ID, setup ID + transition, notification dedup key) | `UNIQUE` constraints reject duplicates (checked here) | Hand-coded checks, easy to get wrong under retries |
| Append-only enforcement | Triggers can block UPDATE/DELETE on registry tables (checked here); hash chain in columns | By convention only |
| Concurrent scanner and notifier processes | WAL: readers don't block the writer | Unsafe without locks |
| Human readability and diff | Binary; needs an export | Plain text |
| Backup | Must snapshot with the SQLite backup API (never copy a live WAL database) | Plain copy |

**Recommendation: SQLite for the new system's registry, orders, fills, positions, balances and notifications.**
- Append-only tables with triggers, with mutable "current" views derived from the append-only event rows.
- A hash chain over registry rows, verified at every start.
- A nightly JSONL export for audit.
- A backup-API snapshot taken before each private backup.

The existing paper books stay on their files, now crash-safe, and are not migrated.

### Still unverified
- A real power loss (only simulated crashes were tested).
- Concurrent runs of two monitoring scripts on the same file: they're sequential in today's tasks; the new system would need a lock.

## 7. Proactive notifications without Claude (master prompt step 6, 2026-10-29)

**Built:** `src/live_usdjpy/notify.py`, plus `notify` and `test-alert` in `tools/usdjpy_pipeline.py`. Plain Python; no Claude session involved, so it costs no Claude usage.
- **Outbox:** `notification` records in the forward registry; every attempt is an append-only `delivery` record.
- **Priorities:** HIGH, NORMAL and LOW. Quiet hours (22:00–07:00 ET) hold LOW and NORMAL. HIGH alerts and every RISK/SYSTEM ALERT are never held.
- **Retries:** backoff of 1, 5, 15 and 60 minutes; the fallback channel is used after 2 failed primary attempts, or at once if the primary rejects the message.
- **Duplicates:** a message is never resent on a channel that already accepted it. After a crash between sending and recording, NORMAL and LOW messages are not resent; HIGH alerts are.
- **Daily digest** (LOW, 18:00 ET) confirms the system is alive.
- **HIGH alerts** fire for a scan gap of more than 30 hours while the FX market is open, and for a digest not delivered by 20:00 ET.
- **Message format:** every alert lists all the required fields in ET; anything unknown reads UNKNOWN, and fields that don't apply read "not applicable". It's capped at 1,024 characters (Pushover's limit).

**Tests:** 12, all with fake channels; nothing was sent anywhere. Acceptance tests B, K and L pass. **Acceptance test H (real delivery after activation) is PENDING, not passed.**

### Channel comparison (official documentation, read 2026-10-29)

| | **Pushover** | **ntfy (ntfy.sh)** | Telegram bot | Email |
|---|---|---|---|---|
| Cost | $4.99 one-time per platform after a 30-day trial; 10,000 messages a month free | Free (no sign-up); paid tiers exist for reserved topics | Free | Free with an existing mailbox |
| Priorities and quiet hours | -2 to 2. Priority 1 bypasses the phone's quiet hours. **Priority 2 (emergency) repeats until acknowledged** (retry ≥ 30 s, expire ≤ 3 h) | 1–5 (5 = long vibration bursts and a pop-over) | Silent flag only | None |
| Delivery receipt | **Yes for emergency priority:** a receipt shows whether it was acknowledged | None stated | None for reads; the API only confirms acceptance (sendMessage section not reached on the page read: general knowledge, unverified) | None |
| Retry guidance | Official: 4xx means don't retry; 5xx or no reply: retry no sooner than 5 s; at most 2 concurrent connections | Not stated on the pages read | Not verified | n/a |
| Privacy | A token and user key, both private; messages pass through Pushover's servers | **"Everyone can read and write to any topic"** on ntfy.sh; the topic name is effectively the password; messages pass through ntfy.sh | Messages pass through Telegram; needs a bot token | Passes through mail providers |
| Reliability notes | A commercial service with documented quotas and error semantics | Best-effort public server; can be self-hosted later | A user must start a chat with the bot first | Spam filtering and delays; not suited to urgent alerts |

**Recommendation: Pushover as primary, ntfy as fallback.** Pushover's emergency priority with acknowledgement receipts is the only option here that can prove a HIGH alert was seen. ntfy is free, needs no account, and makes a good independent second path, as long as the topic name is long and random, because ntfy.sh topics are open.

### Your one-time setup (credentials stay with you; never paste them into Claude)

1. **Pushover (primary):**
   - install the Pushover app on your phone and create an account at pushover.net; your **User Key** is on the dashboard;
   - at pushover.net/apps/build, create an application named `trading-research` and copy its **API Token**;
   - in **your own Terminal**, run these two commands; each prompts for the value, so it never appears in shell history:
     - `security add-generic-password -a "$USER" -s trading-research-pushover-token -w`
     - `security add-generic-password -a "$USER" -s trading-research-pushover-user -w`
2. **ntfy (fallback):**
   - install the ntfy app;
   - in your Terminal, run `openssl rand -hex 16` and use the output, prefixed with `tr-`, as your topic name;
   - subscribe to that topic on ntfy.sh in the app;
   - store it: `security add-generic-password -a "$USER" -s trading-research-ntfy-topic -w`
3. **Tell me "channels set".** I'll then send exactly one labelled TEST message per channel (`tools/usdjpy_pipeline.py test-alert --channel pushover`, then `--channel ntfy`) and record the results.
   - The first time, macOS may ask whether `security` may read the item: choose **Always Allow**.
   - I never see the values.

**Known limits:**
- Nothing can alert while the notifier itself isn't running (laptop asleep, app closed). That's the scheduling question for step 9.
- Polling Pushover receipts for HIGH-alert acknowledgement isn't built yet.
