# PROGRESS

_Last updated: 2026-10-23 (commodity study Phases 4–6 complete; 0 of 26 survive)_

## Current phase
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
6. Several unit-test expectations I wrote were wrong (hand arithmetic, fill timing). In each case the code was verified against a hand calculation before the test was corrected.

## If the project is ever resumed
- Any new strategy must be separately pre-registered before touching the holdout.
- The pending Phase 7B design (2% per-trade rule) applies only if something survives.
- See section 6 of `reports/FINAL_REPORT.md` for what a future study should do differently.

## Notes
- `data/` and `results/` are not committed. Hashes are in `data/raw/download_meta.json` and `data/clean/build_meta.json`.
- 63 tests pass (`pytest tests`). `research_log.csv` rows: see `wc -l`; commodity rows are phases 9-freeze, 9-4-in-sample, 9-5-*, 9-6-kill.
