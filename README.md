# Can a $100 account reach $1,000 with simple ETF strategies?

**A pre-registered backtest study of 92 end-of-day strategies on gold, S&P 500, Nasdaq-100 and long Treasury ETFs and their 2x/3x leveraged versions (2004–2023).**

**Result: 0 of 92 strategies survived.** Some beat a simple equal-weight portfolio out of sample (2019–2023), but none by enough to rule out luck from testing 92 variants: the best Deflated Sharpe probability was 0.73, against 0.95 required. Nothing tested beat a low-cost diversified index portfolio once overfitting was accounted for. For a $100 account, saving $100 a month reaches $1,000 in 9 months; no strategy here was a faster or more reliable route.

**Read the full write-up: [`reports/FINAL_REPORT.md`](reports/FINAL_REPORT.md)**

![Near-miss strategies vs benchmarks](reports/final_equity_curves.png)

## Why this project is set up the way it is
The goal was to answer the question honestly, not to produce a good-looking backtest. That meant:

| Practice | How it was applied |
|---|---|
| Pre-registration | The strategy list and parameter grids were frozen in `research_log.csv` (V001–V092) before any backtest ran |
| Clean data splits | In-sample 2006–2018 for tuning, validation 2019–2023 for selection, holdout 2024+ never opened or downloaded |
| Overfitting control | Walk-forward analysis, bootstrap confidence intervals, and the Deflated Sharpe Ratio with N = 92 |
| Mechanical decisions | 7 kill criteria agreed before results were seen; applied by script, none changed afterwards |
| Full logging | Every run, including every failure, is a row in `research_log.csv` (764 rows) |
| Tested code | 57 unit tests covering no lookahead, cost arithmetic, cash interest, adjusted prices, the risk-mode switch, the synthetic-leverage formula, and the Monte Carlo |
| Honest reporting | Errors I made along the way are recorded in `PROGRESS.md` (e.g. a sanity-check claim corrected before review) |

## Repository map
| Path | Contents |
|---|---|
| [`reports/FINAL_REPORT.md`](reports/FINAL_REPORT.md) | Verdict, method, results, limitations, next steps |
| [`reports/kill_table.md`](reports/kill_table.md) | Pass/fail and reasons for all 92 trials |
| [`reports/phase5_validation.md`](reports/phase5_validation.md) | Full out-of-sample metrics, walk-forward, stress tests, heatmaps |
| [`reports/data_quality.md`](reports/data_quality.md) | Data validation and synthetic leveraged series |
| [`reports/INFORMATIONAL_phase7a_monte_carlo.md`](reports/INFORMATIONAL_phase7a_monte_carlo.md) | Odds of $100 → $1,000 (not validated, failed DSR) |
| [`research/LITERATURE_REVIEW.md`](research/LITERATURE_REVIEW.md), [`research/sources.csv`](research/sources.csv) | 49 sources that shaped the strategy list |
| [`AUDIT.md`](AUDIT.md) | Security audit of a third-party trading repo (only one function reused, with MIT attribution) |
| `config.yaml` | Every parameter: instruments, dates, costs, taxes, risk modes, seed, frozen strategy list |
| `src/` | `data` (download, validation, synthetic leverage), `engine` (backtester), `strategies`, `metrics`, `validate` (walk-forward, bootstrap, DSR, Monte Carlo), `risk` |
| `tools/` | One runner per phase and the report generators |
| `tests/` | Unit tests (`pytest`) |
| `PROGRESS.md` | Phase-by-phase decision log |

## Reproduce
Python 3.10+ (built on 3.14.8).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

To rebuild from scratch (downloads stop at 2023-12-31 while the holdout is locked):

```bash
.venv/bin/python -c "from src.data import download_all, build_clean; download_all(); build_clean()"
```

Then run in order: `tools/sanity_in_sample.py`, `tools/run_in_sample.py`, `tools/run_phase5.py`, `tools/make_phase5_report.py`, `tools/run_phase6.py`, `tools/run_info_phase7a.py`, `tools/make_final_report.py`. The runners append to `research_log.csv`; the report generators don't.

`requirements.txt` pins the seven packages used; `requirements-lock.txt` pins all transitive dependencies. Downloaded data (`data/`) and intermediate results (`results/`) are not tracked. Download dates and SHA-256 hashes are in `data/raw/download_meta.json`.

## Scope and rules
- End-of-day signals only; trades fill at the next open; long-only; leverage only through the listed ETFs.
- No orders were ever placed and no brokerage was connected.
- Limitations: single data source (Yahoo Finance); synthetic leveraged history before 2008–2010; a 5-year validation window; and a 2019–2023 regime that favored US tech and punished long bonds. See section 5 of the final report.

## Credits
- **day-trader-skill** by Jake Schincariol (MIT License), https://github.com/Jakeschincariol/day-trader-skill. This project audited that repository (see [`AUDIT.md`](AUDIT.md)) and reused exactly one function: the Wilder RSI from `trader-scanner/scan.py` (commit `3d0f4ef`). It is used in `src/strategies.py:wilder_rsi`, with one change (a flat series returns 50). The original copyright and permission notice are in [`licenses/day-trader-skill-MIT.txt`](licenses/day-trader-skill-MIT.txt). Nothing else from that repository is installed, imported or redistributed.
- The research behind the strategy list is credited source by source in [`research/sources.csv`](research/sources.csv).

## License
MIT. See [`LICENSE`](LICENSE). Tax rates in `config.yaml` are example defaults (12% federal, 2.75% Ohio); change them for your situation.

Not financial or tax advice.
