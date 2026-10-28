# HistData USD/JPY 2018: Phase D data-quality checks

_Run 2026-10-28T21:16:52+00:00. Data quality only (no hypothesis, no strategy). 18876220 ticks after removing exact duplicates. Aggregates and timestamps only; no vendor quotes. Cross-vendor confirmation (TrueFX): **BLOCKED** (files not present)._

## 1. Time-zone test (rule fixed before the data were read)

**Primary rule:** first ≥ 3-pip move 0–5 s after 08:30:00 New York on the 2018 payroll days; ≥ 11 required. **Reading C: 9 of 12 → FAIL.**

| Reading | First jump 0–5 s after 08:30 (of 12) | Legacy minute rule (peak minute 08:30) | Noon-anchor median / max (pips, 249 days) | Weekend-window ticks | Rollover spike at 17:00 NY (Mon–Thu) |
|---|---|---|---|---|---|
| A: fixed UTC−5 (FAQ) | 3 | 4 of 12 | 2.90 / 38.85 | 49378 | 28% |
| B: New York local time | 10 | 10 of 12 | 0.60 / 7.65 | 0 | 81% |
| C: UTC−5, +1 h during EU summer time | 9 | 9 of 12 | 0.65 / 31.15 | 4843 | 76% |

| Release | US clock | EU clock | First jump, reading C (s after 08:30:00) | reading A | reading B |
|---|---|---|---|---|---|
| 2018-01-05 | EST | winter | 1.7 | 1.7 | 1.7 |
| 2018-02-02 | EST | winter | 3.1 | 3.1 | 3.1 |
| 2018-03-09 | EST | winter | -5.8 | -5.8 | -5.8 |
| 2018-04-06 | EDT | summer | 1.7 | none | 1.7 |
| 2018-05-04 | EDT | summer | 2.0 | none | 2.0 |
| 2018-06-01 | EDT | summer | 2.1 | none | 2.1 |
| 2018-07-06 | EDT | summer | 1.7 | none | 1.7 |
| 2018-08-03 | EDT | summer | 1.3 | none | 1.3 |
| 2018-09-07 | EDT | summer | 1.7 | none | 1.7 |
| 2018-10-05 | EDT | summer | none | none | none |
| 2018-11-02 | EDT | winter | none | none | 2.3 |
| 2018-12-07 | EST | winter | 1.7 | 1.7 | 1.7 |

## 2. Out-of-order and duplicate rows (file exactly as delivered)

- Exact duplicate rows (same timestamp, bid and ask): 0 of 18876220 (0.0000%). They are removed before every other check (cleaning rule).
- none

## 3. Stale quotes (inside continuous London/NY business-hour blocks, reading C)

- Business-hour minutes: 212220. Runs of ≥ 3 minutes without a mid change: 1 (5 minutes, 0.002% of business-hour minutes); of these, runs with no tick at all: 0.
- Run length (minutes): median 5, 90th percentile 5, longest 5.
- By New York hour of start (count): {16: 1}.
- Longest (start NY, minutes, ticks during the run): [('2018-03-29 16:33', 5, 1)].

## 4. Large one-minute moves (reading C)

- One-minute mid changes analysed (consecutive minutes with ticks only; no change is measured across a gap or weekend): 370181.
- Moves > 10 robust σ (σ = 1.4826 × median absolute change, per NY hour): 438 (median absolute one-minute move 0.60 pips; hours with a median of 0: 0). FX one-minute moves are fat-tailed, so this count is a screen, not evidence of bad data.
- Moves ≥ 10 pips: 192; ≥ 20 pips: 15. Of the ≥ 10-pip moves, 10 were undone by ≥ 80% within two minutes (spike-and-revert: candidate bad ticks or genuine flash moves; only a second vendor can tell).
- Largest (NY time, pips, spike-and-revert): [('2018-06-25 15:37', 49.0, False), ('2018-01-26 14:22', 39.5, False), ('2018-02-09 08:45', 30.2, False), ('2018-03-21 15:01', 28.7, False), ('2018-07-31 00:05', 26.7, False), ('2018-01-25 14:03', 25.7, False), ('2018-02-02 08:30', 25.4, False), ('2018-02-05 15:12', 24.8, False)].

## 5. Weekday and weekend continuity (reading C)

- Weeks: 53. First tick of the week (New York, most common): {'Sun 17:00': 49, 'Sun 18:00': 3, 'Mon 17:00': 1}. Last tick: {'Fri 16:59': 49, 'Fri 17:59': 3, 'Mon 16:59': 1}.
- Median ticks per weekday: 64650; by weekday: {'Fri': 55004, 'Mon': 57806, 'Sun': 14654, 'Thu': 69737, 'Tue': 68548, 'Wed': 70676}.
- Weekdays with < 25% of the median tick count: [('2018-01-01', 14006)].

## 6. Bid/ask spreads (vendor indicative quotes; NOT executable costs)

| Window | Ticks | Median (pips) | 90th pct | 99th pct |
|---|---|---|---|---|
| all ticks | 18876220 | 0.50 | 0.80 | 3.70 |
| London/NY business hours | 12324482 | 0.50 | 0.70 | 1.10 |
| Tokyo business hours | 6041432 | 0.50 | 0.70 | 0.90 |
| rollover 16:55-17:10 NY | 119601 | 2.50 | 5.70 | 7.00 |
| after NY close 17:10-19:00 NY | 1235930 | 1.60 | 3.90 | 7.00 |
| payroll 08:29-08:32 NY | 6007 | 1.00 | 1.90 | 3.30 |
| other Fridays 08:29-08:32 NY | 10949 | 0.60 | 1.10 | 2.10 |

Median spread by New York hour (pips): 00: 0.50, 01: 0.50, 02: 0.50, 03: 0.50, 04: 0.50, 05: 0.50, 06: 0.50, 07: 0.50, 08: 0.50, 09: 0.50, 10: 0.50, 11: 0.50, 12: 0.50, 13: 0.50, 14: 0.60, 15: 0.60, 16: 0.70, 17: 2.50, 18: 0.90, 19: 0.60, 20: 0.50, 21: 0.50, 22: 0.50, 23: 0.50.

## 8. EXPLORATORY: which clock does the file use? (not a pre-registered test)

On Monday–Thursday days when New York and London are on different DST settings, the file-time minute of the widest daily spread (the 17:00 New York rollover) is **17:xx if the file uses New York time** and **16:xx under reading C**.

- 12 such days: 2018-03-12 → 17:05, 2018-03-13 → 17:08, 2018-03-14 → 17:00, 2018-03-15 → 17:00, 2018-03-19 → 17:00, 2018-03-20 → 17:00, 2018-03-21 → 17:00, 2018-03-22 → 17:00, 2018-10-29 → 17:00, 2018-10-30 → 17:00, 2018-10-31 → 17:04, 2018-11-01 → 17:00.

## 7. Reproducibility

- Tick-level fingerprint of the transformed series (reading C, SHA-256): `24f85da20098cfa46e741bf41a1047ff590817bc6b67972c18a6d788f21d6f1a`.
- Recomputed from the raw rows in the same run: identical.
- Raw files: SHA-256 manifest in `data/raw/histdata/usdjpy_tick_2018/manifest.json`.

## Not checked here (BLOCKED)

- Q4 cross-vendor agreement and confirmation or rejection of the large moves and stale runs need TrueFX files.
