# Data pilot: HistData USD/JPY ticks, 2019 (quality tests Q1–Q9)

_Run 2026-10-28T16:32:52Z. Data pilot only: no hypothesis, no strategy; nothing enters a study. 2019 only (holdout untouched)._

**Data:** 20846156 ticks in 12 monthly files (122 MB zipped, 896 MB unzipped), 2019-01-01 22:00 to 2019-12-31 21:59 UTC (reading C). Raw files are SHA-256-hashed in `data/raw/histdata/usdjpy_tick_2019/manifest.json`.

## Results

| Test | Verdict | Evidence |
|---|---|---|
| Q1 licence | CONDITIONAL | FAQ: "Use the data at your own will and risk"; storage isn't restricted; publication isn't addressed, so only aggregate statistics are ever published, never data |
| Q2 time zone, documented reading (A: fixed UTC−5) | FAIL | Payroll spike at 08:30 NY in 4 of 12 releases; rollover spike at 17:00 NY on 35% of 209 Mon–Thu days. **The FAQ's convention does not hold for 2019.** |
| Q2 time zone, reading supported by the data (C: UTC−5, +1 h during EU summer time) | FAIL by the pre-set rule | Largest one-minute move at 08:30 NY in 9 of 12 releases (rule ≥ 11). Second by second: the first ≥ 3-pip move lands 0–5 s after 08:30:00 in 11 of the 12 releases (1 had no ≥ 3-pip move in the window; range 0.6 to 1.8 s). Rollover spike at 17:00 NY on 83% of Mon–Thu days. The H.10 noon rate (Q3) and the weekend window (Q7) agree with this reading. It was found from this same year: confirm on another year and with TrueFX before adoption |
| Q3 daily anchor (H.10 noon rate) | PASS | 249 days; median absolute difference 0.50 pips (rule ≤ 3); 95th percentile 1.21; largest 2.70 (2019-01-03) |
| Q4 cross-vendor (TrueFX) | PENDING | TrueFX 2019 files not downloaded yet |
| Q5 bid/ask sanity | PASS | ask < bid: 0 ticks; ask = bid: 0; spreads > 20× the hourly median: 857 ticks (0.004%) |
| Q6 coverage | PASS | London/NY business hours: 99.90% of minutes have ≥ 1 tick (rule ≥ 99%); 1 gaps > 5 min. Tokyo business hours: 99.83% (reported only) |
| Q7 weekends and holidays | PASS | 0 ticks inside Fri 17:00 – Sun 17:00 NY (0.0000%; rule < 0.01%); under reading A there would be 50878. Holiday tick counts vs a median weekday of 71737: 2019-01-01 25143, 2019-07-04 37403, 2019-11-28 38423, 2019-12-25 12961 |
| Q8 stale and outliers | PENDING | 337 stale runs (> 2 min without a mid change in London/NY hours); 6984 one-minute moves > 10 robust σ, to be confirmed or rejected by TrueFX; 0.0% of rows repeat the previous timestamp |
| Q8b out-of-order rows | FINDING | 1 row(s) earlier than the row before (largest step back 3600 s, at file time 2019-10-27 19:00:00); sorted (stable) before every test |
| Q9 reproducibility | PASS | Raw zips immutable and hashed; data ends 2019-12-31; this script is the cleaning rule |

## Q2 detail: payroll releases (08:30 New York)

| Release | US clock | EU clock | Peak minute NY, reading A | reading B | reading C | Size (pips, C) | First ≥ 3-pip move, C (s after 08:30:00) |
|---|---|---|---|---|---|---|---|
| 2019-01-04 | EST | winter | 08:30 | 08:30 | 08:30 | 20.0 | 1.5 |
| 2019-02-01 | EST | winter | 08:31 | 08:31 | 08:31 | 7.8 | 1.0 |
| 2019-03-08 | EST | winter | 08:30 | 08:30 | 08:30 | 27.4 | 1.2 |
| 2019-04-05 | EDT | summer | 09:29 | 08:29 | 08:29 | 5.9 | 0.6 |
| 2019-05-03 | EDT | summer | 09:30 | 08:30 | 08:30 | 7.2 | 1.8 |
| 2019-06-07 | EDT | summer | 09:30 | 08:30 | 08:30 | 27.2 | 1.5 |
| 2019-07-05 | EDT | summer | 09:30 | 08:30 | 08:30 | 21.1 | 1.5 |
| 2019-08-02 | EDT | summer | 09:57 | 08:57 | 08:57 | 13.6 | no ≥ 3-pip move |
| 2019-09-06 | EDT | summer | 09:30 | 08:30 | 08:30 | 11.8 | 1.7 |
| 2019-10-04 | EDT | summer | 09:30 | 08:30 | 08:30 | 12.7 | 1.5 |
| 2019-11-01 | EDT | winter | 08:30 | 07:30 | 08:30 | 24.0 | 1.8 |
| 2019-12-06 | EST | winter | 08:30 | 08:30 | 08:30 | 21.5 | 1.8 |

| Reading | Peak minute at 08:30 NY | First ≥ 3-pip move within 0–5 s of 08:30:00 (of 12) | Rollover spike at 17:00 NY (Mon–Thu days) | Ticks inside the weekend window |
|---|---|---|---|---|
| A: FAQ: fixed UTC−5 | 4 of 12 | 5 of 12 | 35% | 50878 |
| B: New York local time | 8 of 12 | 10 of 12 | 76% | 1455 |
| C: UTC−5, +1 h during EU summer time | 9 of 12 | 11 of 12 | 83% | 0 |

**Why the pre-set Q2 rule misses under reading C:** it asks which whole minute had the largest move. On 2019-02-01 the follow-through in 08:31 was larger than the first jump; on 2019-04-05 the minute bar 08:29 closed after a pre-release drift; on 2019-08-02 payrolls barely moved USD/JPY. The second-by-second measure is the better test of the clock. **Proposed rule for future years (set before they are run):** the first ≥ 3-pip move falls 0–5 s after 08:30:00 in ≥ 90% of releases that produce a ≥ 3-pip move under the reading being tested, and no more than one release has none.


The readings differ only in two windows: US summer with EU winter (10–31 March and 27 October – 3 November 2019), and EU summer (31 March – 27 October). A day-by-day look at the Monday–Thursday rollover spike in file time (diagnostic during the pilot) shows it at 16:00 file time exactly in the two short windows and at 17:00 otherwise, as reading C predicts; reading B would put it at 16:00 New York in those weeks. The 17% of days outside 17:00–17:14 NY under C are days whose widest spread fell elsewhere in 15:30–18:30.

## Q3 detail: largest differences from the H.10 noon rate

| Date | Difference, HistData mid 12:00 NY minus H.10 (pips) |
|---|---|
| 2019-01-03 | +2.70 |
| 2019-08-05 | +2.15 |
| 2019-02-07 | +2.15 |
| 2019-05-17 | -1.90 |
| 2019-04-23 | +1.80 |

## Q5–Q8 detail

- Median spread over the year: 0.30 pips; London/NY hours 0.20; Tokyo hours 0.30.
- Widest spreads (pips, NY time): 2019-01-02 17:45 35.0, 2019-01-02 17:45 35.0, 2019-01-02 17:41 34.9, 2019-01-02 17:43 34.9, 2019-01-02 17:43 34.9.
- Largest one-minute moves (pips, NY time): 2019-01-02 17:37 -119.9, 2019-01-02 17:35 -96.8, 2019-09-15 17:00 -55.3, 2019-01-02 17:36 -54.5, 2019-08-15 02:38 +46.2.
- Weekend-window ticks by NY day (top 5): none.
- Longest London/NY gap: 60 minutes.

## Notes

- HistData publishes its own gap report per file (STATUS_*.txt, kept with the raw files).
- Holiday counts are informational; FX trades on holidays, but thinly.
- Q8 stays PENDING until TrueFX confirms or rejects the large moves and the stale runs.
