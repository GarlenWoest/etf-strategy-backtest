# Phase A: audit of the current project (2026-10-28)

_Every claim from SUMMARY.pdf (2026-10-28) was checked against the code, tests, logs, the app's own run history and the stored data. Read only, apart from one report fix (section 6)._

## 1. Headline claims vs evidence

| Claim in the summary | Evidence checked | Verdict |
|---|---|---|
| 146 tests pass | `pytest tests`: 146 passed, 3 warnings (pandas deprecations) | **Verified** |
| 142 trials | `research_log.csv`: 142 PRE-REGISTERED rows, 142 unique IDs V001–V142 | **Verified** |
| "0 validated" | 140 trials have a KILLED row. **V119 and V122 (Study 3) are logged PASS:** they met Study 3's pre-registered pass rule (≥ 3 of 4 eras, Deflated Sharpe ≥ 0.95). The robustness checks they failed (2x/3x costs, one-month lag) were pre-registered as "robustness_not_trials", reported but not kill rules. | **Imprecise.** Correct wording: 140 killed by pre-registered criteria; 2 passed the pre-registered rule but failed every pre-registered robustness check and were judged not validated (a documented judgment, `reports/study3_longhist.md`). No record was changed. |
| 229 sources, 185 kept | `library.csv`: 229 rows; keep 185, reject 40, duplicate 4 | **Verified count.** But `research_status` says "read" for 220 rows ("read (see …)" 202, "read" 5, abstract 10, full text 1, summary 1) without saying how deeply. **Depth of reading is unverified** (Phase F). |
| 49 memory records, chain intact | `Ledger.verify()` → intact; 49 lines | **Verified** |
| FX engine v2 repairs 3 defects | `src/fx_engine_v2.py`; 15 tests in `tests/test_fx_engine_v2.py` pass; v1 unchanged and still reproduces the official Sharpes (assertion in `tools/compare_fx_engines.py`) | **Verified** |
| Market clock audited | `tests/test_clock.py` passes incl. the Board-calendar test; the data cross-checks were rerun in Priority 1 | **Verified** |
| HistData 2019 pilot | 12 zips, 2019 only, SHA-256 manifest; report regenerable by `tools/pilot_histdata.py` | **Verified;** status "not passed" is correct |
| TrueFX files pending | `data/raw/truefx/` doesn't exist; a full-disk search found no TrueFX or `USDJPY-2019*` files | **Verified: cross-vendor check blocked** |
| Paper books running | App run history: weekday task succeeded 10-23, 10-26, 10-27 (plus a 10-22 setup run); Sunday task 10-25 (plus 10-22). Heartbeat matches. `paper/values.csv` has 10-26 and 10-27 | **Verified** |
| Holdout locked | `config.yaml` holdout_locked true (both places); **all 90 CSV files under data/ end before 2024**; HistData files are 2019 only | **Verified** |
| 15 unpushed commits | Now **16** (493f30d added the summary figures after the summary was written) | **Outdated by one** |

## 2. New findings

1. **Notifications can fail silently.** In the 10-26 weekday run the session called PushNotification four times (the four paper-trade notices). Its own summary says the tool "didn't send any of them because this terminal is active". The run is still recorded as succeeded and ok in the heartbeat. **Nothing in the project records notification delivery** (fix in Phase H).
2. **The 0.05 cap tolerance contradicts the stated 1x maximum.** `config.yaml` ledgers still say `max_gross_notional_x: 1.0` and the user's rule was "max 1x leverage". Diagnostic on the 9 frozen USD/JPY target series, 1991–2023 (scratch copy of v2; `src/` unchanged; not trials):

| Design | Re-sizes + trims | Total costs | Max exposure | Closes above 1.00x |
|---|---|---|---|---|
| Strict cap (band 0, tolerance 0) | 35,846 | $5,302 | 1.0000x | 0 |
| **Approved** (band 0.10; trim above 1.05x back to 1.00x) | 983 | $4,749 | 1.0499x | **26,086** |
| **Proposal** (band 0.10; hard cap 1.00x, trim back to 0.95x) | 2,723 | $4,972 | 1.0000x | 0 |

   - The proposal keeps a true hard maximum and needs about 1/13 of the strict design's trades. It is a **proposal only**: the approved default is unchanged (decision for you).
   - Daily data can't see intraday excursions above 1x under any design.
3. **The pilot report printed five raw HistData quotes** (12:00 NY mids), against our own "aggregates only" rule. Fixed (section 6). The quotes remain in local commit `aaabc98`, which is not pushed (decision for you before any push).
4. **Library "read" labels overstate what's known.** Most rows point to a review document rather than recording what was read (title, abstract, full text, methods reproduced). This is to be audited in Phase F; until then, no source should be treated as "understood".
5. **Nothing in the project observes the market in real time.** The only current-market inputs are:
   - Yahoo daily bars, pulled once a weekday at 16:45 ET for the watchlist and paper books;
   - a once-a-week web search for the Sunday brief.

   There are no FX quotes, no timestamps or freshness checks, and no event calendar. This is the gap Phase B addresses.

## 3. Repository and backup integrity

- **Public repo** (`origin`, etf-strategy-backtest): GitHub `main` at `92234a2`; 16 local commits ahead, unpushed.
  - 120 tracked files. No tracked file under `data/` (except `.gitkeep`), `paper/`, `live/`, `briefs/`, `results/`, `tmp/` or `vendor/`.
  - Tracked CSVs are our own logs and source lists only.
- **Private backup** (`.backup.git` → trading-research-paper-log): the allowlist is `paper/`, `live/`, `briefs/`, enforced before every commit.
  - Tracked there: 8 files, all inside the allowlist.
  - Two snapshots; the last push failed (no repository or credentials). **Still failing.**

## 4. Scheduled tasks

| Task | Schedule | Runs recorded by the app | Notes |
|---|---|---|---|
| watchlist-alerts | Weekdays 16:45 ET (+ up to 216 s jitter) | 4, all succeeded | Needs the Claude app open; a missed run catches up at the next launch |
| weekly-market-brief | Sundays 18:00 ET (+ up to 114 s jitter) | 2, all succeeded | Same dependency |

Each run is a Claude session, not a plain script. The heartbeat records "started" and "finished, ok or error", but not "partially completed" or notification delivery.

## 5. What was not checked

- Whether the Yahoo daily bars match an independent source (only re-queries of Yahoo itself).
- The content of individual library sources (Phase F).

## 6. Change made in Phase A

- `tools/pilot_histdata.py` and `reports/data_quality/histdata_usdjpy_2019_pilot.md`: the Q3 detail table now shows only the difference from the H.10 rate, not HistData's quotes. This was a report-only edit; no results changed.

## 7. Re-verification for the next development phase (2026-10-28, 19:15 ET)

_Read only. Nothing was changed apart from this section, PROGRESS.md and one memory-ledger record._

**Baseline figures (PROJECT_OVERVIEW, 10-28) vs the repository: all confirmed.**

| Figure | Evidence | Result |
|---|---|---|
| 142 trials, V001–V142 | `research_log.csv`: 142 PRE-REGISTERED IDs; 140 KILLED; PASS only V119, V122 | Confirmed |
| 1,125 log rows | 1,125 data rows | Confirmed |
| 217 tests | `pytest tests`: 217 passed (3 pandas deprecation warnings) | Confirmed |
| 83 memory records | `Ledger.verify()` intact; 83 lines | Confirmed (84 after this record) |
| Library 234 / 190 kept; L0 207, L1 16, L2 5, L3 6 | `research/library/audit.csv` | Confirmed |
| 133 events (63 / 25 / 45) | `live/events/events.json`, generated 21:20 UTC; BoE BLOCKED (403) | Confirmed |
| Engine v2 hard 1x | `config.yaml`: band 0.10, cap_tolerance 0.0, cap_reset 0.95; randomized hard-cap test passes | Confirmed |
| Holdout locked | `holdout_locked: true`; all 90 CSV files under `data/` end by 2023-12-31; HistData zips are 2018 and 2019 only | Confirmed |
| Separation | Tests present: `test_events.py::test_isolation_and_write_guard`, `test_market_intel.py` isolation tests, holdout tests in `test_config.py` and `test_data.py` | Confirmed |
| TrueFX files | `data/raw/truefx/` does not exist | Still blocked |

**Git.**
- One branch (`main`); working tree clean.
- GitHub main is `3c51573`, both by `ls-remote` and after a fresh fetch.
- Local main is **3 commits ahead, 0 behind**: `f3d1866` (backup status), `2a1d8f6` and `15b0b11` (overview). Nothing to reconcile; all three are safe to push when you choose.

**Scheduled tasks (the app's own records).**
- **watchlist-alerts:** weekdays 16:45 ET plus up to 216 s jitter. 5 runs, all "succeeded": a 10-22 setup run, then 10-23, 10-26, 10-27 and 10-28. Next run: **2026-10-29 16:48:36 ET**.
- **weekly-market-brief:** Sundays 18:00 ET plus up to 114 s. 2 runs, both "succeeded" (10-22 setup, 10-25). Next run: 11-01.
- **The 10-28 weekday run started at 17:05:00 ET,** about 16 minutes after its latest jittered start. The cause wasn't determined; the heartbeat doesn't count it as late, because its "late" threshold is 18:00.
- **That run used the old prompt and code.** The new prompts and the exposure code were committed at 18:11–18:15 ET. So it recorded no steps, ran no snapshot or event poll, and computed no exposure. Its transcript says the paper update "printed nothing", but the files show it did write the 10-28 values (17:05:14).
- **The first run with every new step is 10-29. It hasn't happened yet**, so Phase B cannot start.

**New findings (not fixed; for Phase B).**
1. **Writes aren't atomic.** `paper/state.json`, `live/heartbeat.json`, `live/state.json`, `live/events/events.json` and `live/intel/latest.json` are all written in place with `write_text`. An interruption mid-write can leave a truncated file, which the next run can't read.
2. **The paper update's write order isn't crash-safe.** Daily values are appended to `values.csv` inside the day loop, and `trades.csv` after it, but `state.json` (including `last_update`) is saved once at the end. A crash in between makes the next run reprocess those days, giving duplicate value rows and possibly repeated fills. This hasn't been observed, and no test covers it.
3. **Step results are self-reported.** The heartbeat's step records are written by the Claude session from what it saw. The scripts don't record their own outcome. `paper_books.py update` prints nothing on a normal successful update, so the record can't tell a real update from a silent no-op.
4. **Test coverage gaps.** Already covered: event idempotence, duplicate tick rows, missing prices and bars, the market-hours refusal, gap alerts, backup allowlist and failures, freshness statuses. **Not covered:** interrupted writes, a crash between writes, retry after failure, recovery after an app restart, and an end-to-end run on stale data.

**Already done; not repeated** (per your limits): the GitHub audit (Phase G: adopt nothing now), the library audit (Phase F), the event monitor, the hard 1x cap, the 10-26 notification diagnosis, and the Book B stop-rule decision.
