# HistData USD/JPY 2019: Phase D data-quality checks

_Run 2026-10-28T21:18:39+00:00. Data quality only (no hypothesis, no strategy). 20843796 ticks after removing exact duplicates. Aggregates and timestamps only; no vendor quotes. Cross-vendor confirmation (TrueFX): **BLOCKED** (files not present)._

## 1. Time-zone test (rule fixed before the data were read)

**Primary rule:** first ≥ 3-pip move 0–5 s after 08:30:00 New York on the 2019 payroll days; ≥ 11 required. **Reading C: 11 of 12 → PASS.**

| Reading | First jump 0–5 s after 08:30 (of 12) | Legacy minute rule (peak minute 08:30) | Noon-anchor median / max (pips, 249 days) | Weekend-window ticks | Rollover spike at 17:00 NY (Mon–Thu) |
|---|---|---|---|---|---|
| A: fixed UTC−5 (FAQ) | 5 | 4 of 12 | 1.60 / 70.10 | 50878 | 35% |
| B: New York local time | 10 | 8 of 12 | 0.50 / 17.50 | 1455 | 76% |
| C: UTC−5, +1 h during EU summer time | 11 | 9 of 12 | 0.50 / 2.70 | 0 | 83% |

| Release | US clock | EU clock | First jump, reading C (s after 08:30:00) | reading A | reading B |
|---|---|---|---|---|---|
| 2019-01-04 | EST | winter | 1.5 | 1.5 | 1.5 |
| 2019-02-01 | EST | winter | 1.0 | 1.0 | 1.0 |
| 2019-03-08 | EST | winter | 1.2 | 1.2 | 1.2 |
| 2019-04-05 | EDT | summer | 0.6 | none | 0.6 |
| 2019-05-03 | EDT | summer | 1.8 | none | 1.8 |
| 2019-06-07 | EDT | summer | 1.5 | none | 1.5 |
| 2019-07-05 | EDT | summer | 1.5 | none | 1.5 |
| 2019-08-02 | EDT | summer | none | none | none |
| 2019-09-06 | EDT | summer | 1.7 | none | 1.7 |
| 2019-10-04 | EDT | summer | 1.5 | none | 1.5 |
| 2019-11-01 | EDT | winter | 1.8 | 1.8 | none |
| 2019-12-06 | EST | winter | 1.8 | 1.8 | 1.8 |

## 2. Out-of-order and duplicate rows (file exactly as delivered)

- Exact duplicate rows (same timestamp, bid and ask): 2360 of 20846156 (0.0113%). They are removed before every other check (cleaning rule).
- Row 18201312: file time 2019-10-27 19:00:00.048 follows 2019-10-27 19:59:59.888 (step back 3600 s). Neighbouring file times: Sun 19:59:59, Sun 19:59:59, Sun 19:59:59, Sun 19:00:00, Sun 19:00:00, Sun 19:00:00.

## 3. Stale quotes (inside continuous London/NY business-hour blocks, reading C)

- Business-hour minutes: 211920. Runs of ≥ 3 minutes without a mid change: 10 (90 minutes, 0.042% of business-hour minutes); of these, runs with no tick at all: 5.
- Run length (minutes): median 3, 90th percentile 10, longest 60.
- By New York hour of start (count): {6: 1, 7: 1, 8: 1, 10: 1, 11: 1, 15: 1, 16: 4}.
- Longest (start NY, minutes, ticks during the run): [('2019-12-31 10:00', 60, 0), ('2019-01-25 11:48', 5, 0), ('2019-12-24 07:45', 4, 4), ('2019-02-21 16:20', 3, 4), ('2019-02-26 16:25', 3, 0)].

## 4. Large one-minute moves (reading C)

- One-minute mid changes analysed (consecutive minutes with ticks only; no change is measured across a gap or weekend): 371917.
- Moves > 10 robust σ (σ = 1.4826 × median absolute change, per NY hour): 905 (median absolute one-minute move 0.45 pips; hours with a median of 0: 0). FX one-minute moves are fat-tailed, so this count is a screen, not evidence of bad data.
- Moves ≥ 10 pips: 247; ≥ 20 pips: 53. Of the ≥ 10-pip moves, 9 were undone by ≥ 80% within two minutes (spike-and-revert: candidate bad ticks or genuine flash moves; only a second vendor can tell).
- Largest (NY time, pips, spike-and-revert): [('2019-01-02 17:37', 119.9, False), ('2019-01-02 17:35', 96.8, False), ('2019-01-02 17:36', 54.5, False), ('2019-08-15 02:38', 46.2, False), ('2019-01-02 17:41', 44.6, False), ('2019-01-03 10:00', 44.5, False), ('2019-01-02 17:44', 40.6, False), ('2019-10-03 10:00', 40.4, False)].

## 5. Weekday and weekend continuity (reading C)

- Weeks: 53. First tick of the week (New York, most common): {'Sun 17:00': 49, 'Tue 17:00': 1, 'Sun 18:00': 1, 'Sun 17:03': 1}. Last tick: {'Fri 16:59': 52, 'Tue 16:59': 1}.
- Median ticks per weekday: 71737; by weekday: {'Fri': 58758, 'Mon': 67915, 'Sun': 18359, 'Thu': 87671, 'Tue': 71057, 'Wed': 80778}.
- Weekdays with < 25% of the median tick count: [('2019-12-25', 12961)].

## 6. Bid/ask spreads (vendor indicative quotes; NOT executable costs)

| Window | Ticks | Median (pips) | 90th pct | 99th pct |
|---|---|---|---|---|
| all ticks | 20843796 | 0.30 | 0.50 | 2.50 |
| London/NY business hours | 13078198 | 0.20 | 0.40 | 0.60 |
| Tokyo business hours | 6823073 | 0.30 | 0.40 | 0.50 |
| rollover 16:55-17:10 NY | 155385 | 1.60 | 3.80 | 7.40 |
| after NY close 17:10-19:00 NY | 1519608 | 0.80 | 2.60 | 5.60 |
| payroll 08:29-08:32 NY | 13744 | 0.50 | 1.20 | 2.20 |
| other Fridays 08:29-08:32 NY | 14285 | 0.30 | 0.70 | 1.30 |

Median spread by New York hour (pips): 00: 0.30, 01: 0.30, 02: 0.30, 03: 0.20, 04: 0.20, 05: 0.20, 06: 0.20, 07: 0.20, 08: 0.20, 09: 0.20, 10: 0.20, 11: 0.20, 12: 0.30, 13: 0.30, 14: 0.30, 15: 0.30, 16: 0.40, 17: 1.40, 18: 0.40, 19: 0.30, 20: 0.30, 21: 0.30, 22: 0.30, 23: 0.30.

## 8. EXPLORATORY: which clock does the file use? (not a pre-registered test)

On Monday–Thursday days when New York and London are on different DST settings, the file-time minute of the widest daily spread (the 17:00 New York rollover) is **17:xx if the file uses New York time** and **16:xx under reading C**.

- 16 such days: 2019-03-11 → 16:00, 2019-03-12 → 16:00, 2019-03-13 → 16:00, 2019-03-14 → 16:00, 2019-03-18 → 16:20, 2019-03-19 → 16:01, 2019-03-20 → 16:02, 2019-03-21 → 16:00, 2019-03-25 → 16:02, 2019-03-26 → 16:14, 2019-03-27 → 16:00, 2019-03-28 → 16:02, 2019-10-28 → 16:00, 2019-10-29 → 16:02, 2019-10-30 → 16:02, 2019-10-31 → 16:09.

## 7. Reproducibility

- Tick-level fingerprint of the transformed series (reading C, SHA-256): `0e9f7cd7719aed6e547e14f06d840cac8e68fa79cb7bc99ce5335699ef6cec9d`.
- Recomputed from the raw rows in the same run: identical.
- Raw files: SHA-256 manifest in `data/raw/histdata/usdjpy_tick_2019/manifest.json`.

## Not checked here (BLOCKED)

- Q4 cross-vendor agreement and confirmation or rejection of the large moves and stale runs need TrueFX files.
