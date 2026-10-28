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

- **Public repository** (`origin` = GarlenWoest/etf-strategy-backtest, main = `92234a2`): 30 local commits are unpushed.
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
