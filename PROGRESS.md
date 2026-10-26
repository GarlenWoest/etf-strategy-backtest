# PROGRESS

_Last updated: 2026-10-26 (research-quality phase, Priority 1 of 7 done; research pause for strategies still active)_

## Current phase
### Research-quality phase (user instruction 2026-10-26)
Goal: fix the research infrastructure before any new hypothesis. There are 7 priorities.
- **Execution limits for this session:** Priority 1 and 2 only. Stop after each with a one-page update, wait for approval, commit locally, don't push.
- **Priority 2:** research only. It produces a vendor table per source (cost, license, history, granularity, bid/ask, timestamp zone, known issues, login) and recommends the cheapest option that passes the quality tests.
- **Still in force:**
  - holdout locked;
  - research paused for strategies;
  - no installs or downloads of large datasets or paid services without approval.

**Priority 1, infrastructure audit and FX engine fixes: DONE, awaiting approval.** Report: `reports/infrastructure_audit.md`.
- **Engine v2:**
  - `src/fx_engine_v2.py` holds currency balances and is for future experiments only; v1 is unchanged and remains the engine of record for V135–V142.
  - It fixes the D1 sizing ratchet, D2 K4 counting, D3 v1's implicit daily re-sizing of the yen leg, and two negligible issues (D4, D5).
  - 14 tests.
  - Comparison (diagnostic, N unchanged): `reports/specialists/fx_engine_v2_comparison.md`. No verdict changes; best DSR 0.39 vs 0.37; always-long holds 0.99x vs v1's 0.52x average.
  - Runner: `tools/compare_fx_engines.py` (adds 9 DIAGNOSTIC rows to research_log.csv).
- **Clock, checked against data:**
  - Japan exact (JGB gaps 1990–2023); UK exact (gov.uk 2019–2028); NYSE exact apart from 4 unscheduled closures.
  - **Error fixed:** the H.10 calendar is the Fed Board's (Saturday holidays observed on Friday from 2010), so `us_board_holidays` was added.
  - DEXJPUS has 3 stale 2007 holiday rows (data incident).
- **Costs and rollover:** unverified assumptions (evidence class D). Yahoo bid/ask snapshots are unusable.
- **Paper records:** journal intact; watchlist fills match Yahoo opens.
- **Five weaknesses found in `paper_books.py`, not fixed:**
  - P1: a silent no-op if there's no bar for today;
  - P2: one missing price fails the whole update;
  - P3–P5: documented only.
  - P1 and P2 need your approval.
- **Decided 2026-10-26 (user):**
  - engine v2 defaults are band 0.10 and cap_tolerance 0.05, fixed before any new pre-registration (`config.yaml specialists.engine_v2`);
  - the paper-script fixes P1 and P2 are implemented with tests.
- **Tests:** 146 pass. The memory ledger has 44 records, chain intact.
- **Today's scheduled run executed and was verified:**
  - 16:49:01–16:49:15 ET, status ok;
  - all 4 opening orders filled, and the fill prices match a fresh Yahoo download;
  - first values: A $100.41, B $100.02, SPY $100.34, 70/30 $100.26 (one day, meaningless).

**Research paused after 0/142; paper books and monitoring running.** (User decision 2026-10-26.) No new hypotheses for gold, GBP/USD or USD/JPY until the user decides; `config.yaml specialists.research_paused: true`.

- **USD/JPY sizing diagnostic (DIAGNOSTIC, SIZING BUG CHECK; not trials, no N increase):** resetting positions to 1x at each weekly decision changes no kill verdict; all 8 trials stay killed (best DSR 0.39 re-sized vs 0.37 frozen). Counting only true direction changes for K4 changes no verdict either. Report: `reports/specialists/usdjpy/study1_diagnostic_sizing.md`.
- **Monitoring status 2026-10-26:**
  - The Sunday 10-25 brief ran, 18:35–20:42 ET.
  - Book B journal entry #1: BUY GLD 25%, fill planned at the 10-26 open; the journal check is intact.
  - The private backup failed, because the repo and token don't exist yet.
  - The paper books process the 10-26 open in today's 16:45 ET weekday run.

- **Monitoring fixes (2026-10-26, approved):**
  - The heartbeat has a monitoring start date (2026-10-23, the first scheduled weekday run): earlier days are never reported as missed.
  - `paper_books.py update` refuses to run 09:30–16:15 ET on NYSE trading days, logs the reason to `paper/update_refusals.csv`, and changes nothing. The next run after 16:15 catches up.

### USD/JPY study 1 (2026-10-26)
**0 of 8 survive. Best Deflated Sharpe 0.37 at N = 142 (V142). Always-long validation Sharpe 0.24.** Report: `reports/specialists/usdjpy/study1_kill_table.md`. Results, rejections and one error (sizing ratchet, not corrected) are in `research/memory/research.jsonl`. Stopped, per instruction.

### USD/JPY specialist pre-registration (2026-10-23)
8 trials frozen (V135–V142, cumulative N = 142) in commit 2aae894.
- See `research/USDJPY_PREREGISTRATION.md` (trial list), `research/EXPANSION_PLAN.md` section 15 (decisions and progress), `reports/specialists/usdjpy/data_quality.md`.
- New modules: `src/clock.py`, `src/memory.py`, `src/library.py`, `src/fx_engine.py`, `src/specialists/`. The existing engine, studies, tasks and paper books are unchanged.
- **Rule 1 amendment (user, 2026-10-23):** a read-only FRED/ALFRED API key is allowed, read only from the env var `FRED_API_KEY`, never printed, logged or committed. Not used yet: none of the frozen hypotheses needs revised macro data.
- 122 tests pass.

### Expansion planning (2026-10-23)
**Phase 0 audit, gap analysis and plan written to `research/EXPANSION_PLAN.md`.**
- Scope: gold, USD/JPY and GBP/USD specialists as a modular extension; existing studies, holdout, tasks and paper books untouched.
- Baseline verified: 90 tests pass; research log 1,045 rows with 134 unique pre-registered trials; next trial ID V135 (cumulative N continues from 134).
- Recommendation: activate USD/JPY first; gold and GBP/USD in monitoring mode.
- Open decisions are listed in section 13 of the plan: first specialist, ledger sizes ($100 GLD; $10k FX at ≤1x notional), FX study splits, login-gated data sources, dependencies, publication, housekeeping.

### Project status before the expansion
**Project closed (2026-10-23).** Three pre-registered studies, 134 cumulative trials, 0 validated. `reports/FINAL_REPORT.md` (via `tools/make_final_report.py`) and `README.md` cover all three studies and the GitHub survey. The holdout (2024 onward) was never opened. Not pushed: the user will push.

### After closing: monitoring tools (outside the research; exempt from rule 2 for their own folders only)
- **Weekly market brief:** Sundays 6 PM ET → `briefs/` (git-ignored). Informational only.
- **Watchlist alerts:** weekdays 4:45 PM ET → `live/` (git-ignored). V122 (VTI/IEF/DBC/GLD stand-ins) and V074, both labelled NOT VALIDATED, FAILED TESTING; signals only.
- **Paper trading test (PAPER, FICTIONAL MONEY):** `paper/` (git-ignored). Four $100 books from 2026-10-26: A rules (V122 + V074), B discretionary (one journalled decision per week, fingerprinted, 5-day hold), SPY and 70/30 SPY/GLD benchmarks. 2-week checkpoint report, and no conclusion before 3 months.
- **Fixes (2026-10-23):**
  - late Sunday runs: Book B entries are dated to the Sunday, marked LATE, and filled at the first open after writing; weeks with no decision are recorded MISSED;
  - heartbeat in `live/heartbeat.json`: Sunday status line, plus a gap alert after more than 3 trading days without a run;
  - private backup of paper/, live/ and briefs/ via `.backup.git` (allowlist-checked). The user creates the private repo and token.
- None of these place orders or connect a broker, and nothing from them enters `data/`, `research_log.csv` or any study.

### Study 3 (long-history validation, 1927–2018)
- Data: Ken French (stocks, T-bills), AQR (commodities; TSMOM factor as reference), FRED (LTGOVTBD, GS10, TB3MS, CPI), Shiller (cross-checks only), World Bank Pink Sheet (gold, user decision: FRED deleted its gold series in 2022). xlrd 2.0.1 and openpyxl 3.1.5 installed with approval. Every file was truncated before 2024 on parsing and the originals deleted. Report: `reports/data_quality_longhist.md`.
- Pre-registered in commit 79d90a4: V119–V122 (P2 multi-asset trend, 6/8/10/12 months) and V123–V134 (S3 monthly TSMOM, 3/6/12 months × stocks/bonds/gold/commodities). Cumulative N = 134.
- Result: V119 and V122 pass the pre-registered era rule (3 of 4 eras) and DSR at 1x costs, but fail every pre-registered robustness check (2x/3x costs, one-month signal lag), their neighbours pass only 2 eras, and their full-span edge over equal weight is about zero. Report: `reports/study3_longhist.md`.
- GitHub survey of 20 most-starred trading-strategy repos: `reports/github_survey.md` (0 show clear OOS results, 0 show live results, 2 show costs).

### Study 2 (commodities)
**Commodity study: Phases 4–6 complete. 0 of 26 new trials survive. Stopped, per your instruction.** Holdout still locked; nothing goes to Phase 7 or Phase 10 alerts.

- Pre-registered (commit a696506) before any backtest: V093–V118 = I01 (6), I03 (6), I04 (6), I05 (4), I06 (4). Cumulative N for the DSR = 92 + 26 = 118.
- Universe GLD/SLV/USO (copper dropped, option c); 2x versions UGL/AGQ/UCO; AGQ/UCO synthetic before Dec 2008, calibrated on in-sample overlap only.
- Benchmarks (not trials): buy-and-hold of each, SPY, equal weight GLD/SLV/USO (K1's equal weight), 70/30 SPY/GLD.
- Best DSR at N = 118: 0.430 (V108, I04 dual momentum 6-month, leveraged; uses oil). Best validation Sharpe 0.63, vs 0.82 for 70/30 SPY/GLD.
- Reports: `reports/commodities_phase4_in_sample.md`, `reports/commodities_phase5_validation.md`, `reports/commodities_kill_table.md`. Runner: `tools/run_commodities.py`.

### Commodity study research (Phase 9)
- 153 sources found, 114 kept: `research/sources_commodities.csv`, `research/IDEA_POOL_COMMODITIES.md`, `reports/data_quality_commodities.md`.

### Earlier ETF study (closed)
Final report: `reports/FINAL_REPORT.md`.

The holdout (2024-01-01 onward) is **locked by your decision (option a)**. It has never been opened or downloaded. The broker check and paper script were skipped at your request.

## Summary of phases
| Phase | Outcome |
|---|---|
| 0 Audit | day-trader-skill repo: SAFE WITH CAVEATS; only the Wilder RSI reused (MIT notice in `licenses/`) |
| 0.5 Research | 49 sources; P1–P3 added; strategy list frozen at 92 trials |
| 1 Structure | venv, config, skeleton, tests |
| 2 Data | Yahoo only (Stooq cross-check impossible; option C); synthetic leveraged series with in-sample drag calibration; 2 suspect stale-price stretches unresolved |
| 3 Engine | Matches a direct calculation on all 9 benchmarks; hand-checked trade |
| 4 Strategies | 92 variants implemented and run in-sample |
| 5 Validation | 13 of 92 beat equal weight out of sample; 1 of 30 walk-forward groups; best DSR 0.727 |
| 6 Kill table | **0 of 92 survive**; 5 P2 trials fail only the DSR |
| 7A (informational) | Monte Carlo on V073, V074, equal weight, SPY, UPRO; labeled "not validated, failed DSR" |
| Final | `reports/FINAL_REPORT.md`, `reports/final_equity_curves.png`, `reports/final_kill_matrix.png`, README |

## Corrections made during the project (kept for the record)
1. **Phase 3:** the first sanity report claimed the equal-weight row matched at 2 decimals when it was 0.02 pp off. The cause was the $1 minimum order. Fixed: the report now computes its verdict and shows the effect separately.
2. **Phase 5:** the P1 heatmap and table labels showed the wrong parameter. Fixed in the report script without re-running or duplicating log rows.
3. **Phase 5 report:** it said rotation groups had "no choice to make" in walk-forward. False; fixed (no numbers changed).
4. **Informational Monte Carlo:** the plain-English lines first misused the median time as a horizon. Rewritten with 3- and 10-year horizons.
5. **Phase 2 data report and an earlier PROGRESS note:** they said the calibrated synthetic series were "0.7–1.5 pp a year too optimistic" in 2019–2023. That was wrong for TMF, which was 0.7 pp too pessimistic. Both reports now generate this sentence from the data.
7. **Commodity pre-registration:** I first wrote the EWMAC(16,64) forecast scalar as 1.95; Carver's published value is 3.75 (1.95 is close to the 64/256 rule's). Corrected before the freeze commit and before any backtest; the published value was used, not one fitted to data.
8. **Commodity Phase 5 report:** the parameter column first showed "fast=20" for I05 instead of the slow window; fixed with a report-only rebuild (no rerun, no duplicate log rows).
9. **Study 3 data check:** the first bond cross-check against Shiller showed correlation 0.31. Cause: Shiller dates each monthly bond return by its start month. Aligned, the series match at 1.000; documented in the validation script.
10. **Study 3 report:** the first version said "1 of 16" trials pass the DSR; the correct count is 4 (V119–V122). Fixed with a report-only rebuild (no duplicate log rows).
11. **Rule 7 slip during the close-out:** a shell command briefly wrote an empty scratch file to /tmp (outside the project). It was deleted immediately; nothing else was written outside trading-research/.
12. **USD/JPY study 1 sizing rule (my design error):** the frozen rule shrinks a position when it exceeds the 1x cap but never grows it back, so long-held positions (always-long, V135) drifted to about 0.3–0.4x exposure. Found after the run; disclosed in the report and memory ledger; not corrected, per the pre-registration.
13. **USD/JPY walk-forward:** the shared walk-forward helper raises an error when both grid values never traded in a training window; the runner uses a local copy that treats an undefined Sharpe as 0 (ties to the first column, as before). Found before anything was logged.
14. **USD/JPY K4 counting:** the frozen run counted cap trims as position changes. The diagnostic shows no verdict changed; recorded in the memory ledger.
6. Several unit-test expectations I wrote were wrong (hand arithmetic, fill timing). In each case the code was verified against a hand calculation before the test was corrected.

## If the project is ever resumed
- Any new strategy must be separately pre-registered before touching the holdout.
- The pending Phase 7B design (2% per-trade rule) applies only if something survives.
- See section 6 of `reports/FINAL_REPORT.md` for what a future study should do differently.

## Notes
- `data/` and `results/` are not committed. Hashes are in `data/raw/download_meta.json` and `data/clean/build_meta.json`.
- 122 tests pass (`pytest tests`). `research_log.csv` rows: see `wc -l`; commodity rows are phases 9-freeze, 9-4-in-sample, 9-5-*, 9-6-kill.
