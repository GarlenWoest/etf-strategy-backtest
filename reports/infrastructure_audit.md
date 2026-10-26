# Infrastructure audit (Priority 1)

_Written 2026-10-26, from 12:15 ET. It covers the FX engine, the market clock, rollover, transaction costs, the paper-trading records and the scheduled runs. Frozen experiments and their reported results are unchanged; every correction is for future use._

## 1. Scheduled runs: did they execute?

| Run | Due (ET) | Evidence | Status |
|---|---|---|---|
| Weekday watchlist + paper | Fri 10-23 16:45 | heartbeat 16:55–17:01, ok; `live/paper_log.csv` written 16:58 | ran |
| Sunday brief + Book B | Sun 10-25 18:00 | heartbeat 18:35–20:42, ok, note "backup failed"; journal entry #1 at 20:25 | ran (backup push failed: no credentials, as expected) |
| Weekday watchlist + paper | **Mon 10-26 16:45** (app: 16:48) | see section 8, added after the run | **not yet due when this audit started** |

The app's cron runs on the Mac's local zone, which is America/New_York (`/etc/localtime`), so the 16:45 ET timing holds through the US DST change on 2026-11-01.

## 2. FX engine v1 (`src/fx_engine.py`): defects found

v1 stays the engine of record for the frozen USD/JPY study 1. The corrections are in `src/fx_engine_v2.py`, which has 14 unit tests. The comparison is in `reports/specialists/fx_engine_v2_comparison.md`.

| # | Defect in v1 | Effect | v2 correction |
|---|---|---|---|
| D1 | **Sizing ratchet:** notional is set at entry and only shrinks when it exceeds the cap. It never grows back. | Always-long averaged 0.52x of equity (0.32x at end-2023); carry trials 0.67–0.77x | Re-size to the target at every decision (optional `band`); cap checked at every close |
| D2 | **K4 counting:** the frozen K4 count included cap trims. | V135: 94 counted vs 13 real | Every trade is labelled (open / close / reverse / resize / cap_trim); `position_changes()` counts only the first three |
| D3 | **Implicit daily re-sizing:** v1 books N x (1 − S[i−1]/S[i]) on a constant USD notional, so the yen leg is re-sized every day at no cost. | Multi-day P&L differs from a real position (a +30% move: v1 overstates the gain; unit test) | Holds currency balances and marks them to market; equals the broker formula N x (1 − S0/S_t) exactly |
| D4 | Entry cost is charged on pre-cost equity. | About 0.02% of one trade; negligible | Exposure equals the target after costs, exactly |
| D5 | Yen interest is valued at the entry rate. | About 0.002 USD per day per $10k; negligible | Interest accrues in yen and is valued at the current rate |

**Comparison on the frozen targets (diagnostic, not trials, N unchanged):**
- No kill verdict changes: all 8 trials are killed under both engines.
- Best Deflated Sharpe: 0.37 (v1) and 0.39 (v2), against a bar of 0.95.
- Always-long validation Sharpe: 0.24 under both.

**New issue found in v2:** a strict 1x cap at every close produces thousands of tiny trims, e.g. 2,338 for always-long over 1991–2023. A new `cap_tolerance` parameter (default 0, strict) trims only above (1 + tolerance) x max. Its value and `band` must be fixed in any future pre-registration (decision for you).

## 3. Market clock (`src/clock.py`): checked against real data

| Calendar | Checked against | Result |
|---|---|---|
| Japan bank holidays | Every weekday without a MoF JGB yield, 1990–2023 | **Exact match** (0 differences either way) |
| UK (England and Wales) | gov.uk bank-holidays.json, 2019–2028 (83 dates) | **Exact match** |
| NYSE | Every weekday without a SPY bar, 2004–2023 | Exact except 4 unscheduled closures: 2004-06-11, 2007-01-02, 2012-10-29/30, 2018-12-05 |
| US Fed (H.10/H.15) | Every weekday without a DEXJPUS rate, 1990–2023 | **Error found:** `us_fed_holidays` was documented as the H.10 calendar but follows the Reserve *Banks*. The *Board*, which publishes H.10, closes on the Friday before a Saturday holiday (from 2010). Added `us_board_holidays` plus a test. It matches every gap except 10 ad-hoc closures (2001-09-11, 2014-12-26, 2017-01-20, 2018-12-05, 2018-12-24, 2019-01-14, 2019-02-20, 2020-11-27, 2020-12-24, 2021-01-20). |

- **Effect on the frozen study:** none. The study uses the DEXJPUS dates as its calendar, not the rule-based one.
- **Data incident:** DEXJPUS has rates on three 2007 Fed holidays (09-03, 10-08, 11-22). Each repeats the previous day's value, so they are stale entries. Over 1990–2023 there are 77 days with no change in the rate; that is about what chance predicts for a rate quoted to two decimals.
- **Not modelled:**
  - early closes (NYSE 13:00 days);
  - holidays inside `fx_market_open` (Christmas and New Year liquidity);
  - value-date holidays in `rollover_days` (only the Wednesday triple roll is modelled).

  These matter only for intraday work (Priority 3).

## 4. Rollover (financing) assumptions

| Item | Used | Assessment |
|---|---|---|
| Formula | Interest differential on the position, act/360 USD, act/365 JPY, calendar days between data dates | Correct in total over time. Daily data can't place the Wednesday triple roll, which is irrelevant at weekly decisions. |
| USD rate | DTB3 (3-month bill, discount basis) | A proxy. A broker's tom-next price follows overnight rates (EFFR, later SOFR). |
| JPY rate | JGB 1-year (MoF) | A proxy, chosen because no free daily yen money-market series was found. Before about 1995 it may differ from the call rate by tens of basis points. |
| Markup | 0.75%/yr on open notional | Evidence class D only (one explainer, FX019). Real markups vary by broker and over time; not verified. |

## 5. Transaction-cost assumptions

| Market | Assumption | Evidence | Status |
|---|---|---|---|
| ETFs (Studies 1–3, paper books) | 0.07% one-way unleveraged (0.02% half-spread + 0.05% slippage); 0.10% leveraged | Study 1 config | **Unverified.** A Yahoo bid/ask snapshot today (12:21 ET) was unusable: SPY showed a negative spread and TQQQ 0.78%, so the quotes are stale. Yahoo quotes must not be used to measure costs. |
| USD/JPY | 0.015% one-way of notional (about 1.6 pips at 110) | Class D only (FX020 reviewer spreads, 0.35–1.5 pips) | **Unverified.** Plausibly conservative for liquid hours; unknown at the NY noon fix, in Tokyo lunch hours, at the 17:00 roll or around releases. Needs bid/ask data (Priority 2). |

## 6. Paper-trading records (before today's run)

- **`paper/state.json`:**
  - start date 2026-10-26;
  - `last_update` null;
  - 4 pending orders for today's open (Book A, SPY, MIX, Book B).
- **Book B journal:** 1 entry, fingerprint check **intact**.
- **`live/paper_log.csv`:**
  - all 4 watchlist fills (VTI, DBC, UPRO, TQQQ at the 10-01 open) match Yahoo's opens to the cent today;
  - the signal closes (VTI, DBC, SPY, QQQ) match too.
  - Caveat: this is the same vendor re-queried, not an independent check.
- **Weaknesses in `tools/paper_books.py`.** None is fixed yet; they are not changed before the first run without your approval:

| # | Issue | Consequence | Proposed fix |
|---|---|---|---|
| P1 | If Yahoo has no bar for today at 16:48, the update silently does nothing | The run reports "ok" with no values and no notification | Notify when a trading day after 16:15 ET has no bar |
| P2 | A missing open or close for one instrument raises an error | The whole update fails (the heartbeat would record it) | Skip that instrument's fill with a notification |
| P3 | Interest is ^IRX / 100 / 252 per trading day (a discount-basis bill yield) | Approximation; under $0.01 per month on $100 | Keep; document |
| P4 | An unscheduled NYSE closure isn't in the rule calendar | The fill moves to the next open and is flagged "late" | Keep; documented behaviour |
| P5 | Yahoo can revise past bars | Values are recorded once and never recomputed: good | none |

## 7. Tests

143 tests pass (128 before this audit):
- 14 new tests for engine v2;
- 1 new test for the Board calendar.

## 8. Today's scheduled run (10-26)

**The run executed:**
- heartbeat `weekday-20261026T164901`, 16:49:01–16:49:15 ET, status ok;
- the gap check was quiet;
- no update refusals were logged.

| Check | Result |
|---|---|
| Pending orders | All 4 filled at the 10-26 open; none left |
| Trades written | 8 rows in `paper/trades.csv` |
| Fill opens vs a fresh Yahoo download at 16:50 ET | All six match (DBC, VTI, TQQQ, UPRO, SPY, GLD) |
| Costs | Fill prices = open × (1 + 0.07%), or 0.10% for TQQQ/UPRO |
| First values, recomputed by hand from the shares, cash and fresh closes | Exact match for all five books (table below) |
| Book B | BUY GLD 25% filled at the 10-26 open, including costs; exit rule stored (stop 348, take profit 395, exit on or after 2026-12-04); journal intact |

**First values (PAPER, FICTIONAL MONEY), 10-26 close:**

| Book | Value |
|---|---|
| A (V122 + V074) | $100.41 |
| B | $100.02 |
| SPY | $100.34 |
| 70/30 SPY/GLD | $100.26 |

One day is statistically meaningless.

**Side finding:** Yahoo's quote snapshot at 12:21 ET showed TQQQ quotes roughly 7–10% away from the day's actual trading range, which confirms that Yahoo's `info` quotes are stale and unusable (section 5).
