# PROGRESS

_Last updated: 2026-10-22 (Phase 9 research complete; waiting for your pick)_

## Current phase
**Phase 9 (commodities research), steps a–d complete. Stopped for your choice of ideas.** Nothing pre-registered, nothing backtested, no instrument switched.

- 9a/9b: 153 sources found, 114 kept (95 strategy evidence + 19 instrument/tax facts), 39 rejected. See `research/sources_commodities.csv`.
- 9c: daily data for GLD, IAU, GLDM, SLV, USO, CPER, UGL, AGQ, UCO, DGP and SPY, plus front-month futures, GVZ/OVX and FRED macro series, all through 2023-12-29. 0 holdout rows. Report: `reports/data_quality_commodities.md`. Your decision needed: CPER is unusable before 2017.
- 9d: `research/IDEA_POOL_COMMODITIES.md` has 14 ranked ideas, 6 ideas flagged as needing non-free data, and the $100 instrument feasibility table.
- Next, after you pick: pre-register with cumulative N = 92 + new trials, run Phases 4–6 unchanged, then Phase 10 signal-only alerts.

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
6. Several unit-test expectations I wrote were wrong (hand arithmetic, fill timing). In each case the code was verified against a hand calculation before the test was corrected.

## If the project is ever resumed
- Any new strategy must be separately pre-registered before touching the holdout.
- The pending Phase 7B design (2% per-trade rule) applies only if something survives.
- See section 6 of `reports/FINAL_REPORT.md` for what a future study should do differently.

## Notes
- `data/` and `results/` are not committed. Hashes are in `data/raw/download_meta.json` and `data/clean/build_meta.json`.
- 57 tests pass. `research_log.csv` has 764 rows.
