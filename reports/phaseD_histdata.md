# Phase D: completing the HistData USD/JPY data pilot without TrueFX (2026-10-28)

_Data quality only: no hypothesis, no strategy, no 2024+ data. The original 2019 pilot report and its verdicts are unchanged (`reports/data_quality/histdata_usdjpy_2019_pilot.md`). Per-year detail: `reports/data_quality/histdata_usdjpy_2018_phaseD.md` and `..._2019_phaseD.md`. The 2018 test was fixed and committed (70a26ba) before any 2018 data was read. Code: `src/histdata.py` (7 tests) and `tools/histdata_checks.py`. 2018 files: 12 zips, 95,572,014 bytes (sizes read from the response headers before download), SHA-256 manifest. Cross-vendor checks (TrueFX): **BLOCKED**._

## 1. The separate-year time-zone test: FAIL

**Pre-fixed rule** (config, approved 10-28): the first move of 3 pips or more lands 0–5 s after 08:30:00 New York on the BLS payroll dates, in at least 11 of 12 releases.

| Year | Reading C (UTC−5, +1 h in EU summer) | Reading B (New York local time) | Reading A (FAQ, fixed UTC−5) |
|---|---|---|---|
| **2018 (separate year, pre-fixed test)** | **9 of 12: FAIL** | 10 of 12 (below 11; reported only) | 3 of 12 |
| 2019 (the year C came from: exploratory) | 11 of 12 | 10 of 12 | 5 of 12 |

**Supporting evidence** (C / B / A):

| Measure | 2018 | 2019 |
|---|---|---|
| Fed noon-rate gap, median / max (pips) | C 0.65 / 31.15; **B 0.60 / 7.65**; A 2.90 / 38.85 | **C 0.50 / 2.70**; B 0.50 / 17.50; A 1.60 / 70.10 |
| Weekend-window ticks | C 4,843; **B 0**; A 49,378 | **C 0**; B 1,455; A 50,878 |

**Exploratory clock check** (not a test). On days when the US and Europe are on different DST settings, the file-time hour of the 17:00 New York rollover spread spike:
- **2018:** 17:xx on 12 of 12 days, meaning the file uses New York time.
- **2019:** 16:xx on 16 of 16 days, as reading C predicts.

**Conclusion:** HistData's timestamp convention **changed between November 2018 and March 2019**. From 4 Nov 2018 to 10 Mar 2019 the US and Europe were both on winter time, so readings B and C give identical UTC and the exact switch date cannot be seen (nor can it matter). The FAQ's fixed UTC−5 is wrong in both years.

**Consequences:**
- No single conversion is valid across years. Every year must be tested before use, and readings must not be chosen after the fact.
- Per the pre-fixed specification, reading B for 2018 is a finding to test on a third year, **not** an adopted convention.

The two 2018 misses under B:
- **2018-03-09:** the first 3-pip move came 5.8 s *before* 08:30:00, the same under every reading (a winter date). It's either a pre-release move or a clock about 6 s early that day. Unexplained.
- **2018-10-05:** no 3-pip move at all.

## 2. The out-of-order row: a duplicated hour (vendor defect)

- **What it is:** the 2019-10-27 "step back of 3,600 s" is the **whole 19:00–19:59 file-time hour repeated**: 2,360 rows, identical row for row.
- **When:** the Sunday the EU left summer time. That day the data starts at 16:00 file time; the previous Sunday it started at 17:00, as reading C predicts.
- **Rest of the files:** no other duplicates in 2019, none in 2018, and no out-of-order rows in 2018.
- **New cleaning rule:** exact duplicate rows (same timestamp, bid and ask) are dropped (2019: 2,360 of 20,846,156, 0.011%). The 2019 pilot numbers included them, an effect too small to change any verdict.

## 3. Stale prices

Measured inside continuous London/New York business-hour blocks, never across closed hours or weekends. My first version did span the closures and over-counted badly; it was fixed before this report.

| | 2018 | 2019 |
|---|---|---|
| Business-hour minutes | 212,220 | 211,920 |
| Runs of ≥ 3 minutes without a mid change | 1 (5 min) | 10 (90 min, 0.042%) |
| Of which, no tick at all | 0 | 5 (longest: 60 min on 2019-12-31 from 10:00 NY) |

Very few stale stretches. Whether they reflect the market or the vendor is **BLOCKED** on TrueFX.

## 4. Large one-minute moves

Measured only between consecutive minutes that both have ticks; never across gaps or weekends (also fixed before this report).

| | 2018 | 2019 |
|---|---|---|
| Minutes analysed | 370,181 | 371,917 |
| Moves ≥ 10 pips / ≥ 20 pips | 192 / 15 | 247 / 53 |
| ≥ 10-pip moves undone ≥ 80% within 2 min (candidate bad ticks or flash moves) | 10 | 9 |
| Largest | 49.0 pips (2018-06-25 15:37 NY) | 119.9 pips (2019-01-02 17:37 NY), part of a cluster 17:35–17:44 NY |

- **"> 10 robust σ" counts** (438 in 2018, 905 in 2019) are a screen only: one-minute FX moves are fat-tailed.
- **The 2019-01-02 cluster** was not checked against any independent record here.
- Confirming or rejecting each large move is **BLOCKED** on TrueFX.

## 5. Weekday and weekend continuity (reading C)

- **Weeks:** 53 in each year.
- **First tick of the week:** Sunday 17:00 New York in 49 weeks in both years.
- **Last tick:** Friday 16:59 in 49 (2018) and 52 (2019) weeks.
- **2018 exceptions:** the 3 weeks at 18:00/17:59 are the EU-winter/US-summer weeks, where reading C is wrong for 2018 (consistent with section 1).
- **Low-volume days:** only New Year's Day 2018 and Christmas Day 2019 fall below 25% of the median weekday tick count.
- **Bid/ask sanity:** no inverted or zero spreads in either year (2018: 0 of 18,876,220; 2019: 0, pilot Q5).

## 6. Spreads (vendor indicative quotes; **not** executable costs)

| Window (median / 99th percentile, pips) | 2018 | 2019 |
|---|---|---|
| London/NY business hours | 0.50 / 1.10 | 0.20 / 0.60 |
| Tokyo business hours | 0.50 / 0.90 | 0.30 / 0.50 |
| Rollover 16:55–17:10 NY | 2.50 / 7.00 | 1.60 / 7.40 |
| Payroll minutes 08:29–08:32 NY | 1.00 / 3.30 | 0.50 / 2.20 |
| Same minutes, other Fridays | 0.60 / 2.10 | 0.30 / 1.30 |

- **Patterns in both years:** the spread widens about 3–5x at the 17:00 New York rollover and roughly doubles around payrolls.
- **Change between years:** the typical spread halved from 2018 to 2019 *at the same time as* the clock convention changed. That suggests the underlying feed may have changed. This is an observation, not a conclusion; HistData doesn't disclose its source.
- **Costs:** these vendor spreads don't verify our cost assumption (USD/JPY 0.015% one-way, about 1.6 pips): they're indicative, not executable.

## 7. Reproducibility

- **2018:** tick-level SHA-256 of the transformed series is `24f85da2…21d6f1a`, identical in two separate runs and when recomputed within a run.
- **2019:** after duplicate removal, `0e9f7cd7…f6cec9d`; consistent within the run.
- **Raw files:** hashed in manifests.
- **Cleaning rules are code:** `src/histdata.py` (duplicate removal, the readings), tested.

## 8. Status of the quality tests

| Test | 2018 | 2019 |
|---|---|---|
| Q1 licence | Conditional (unchanged) | Conditional |
| Q2 time zone (per-second rule) | **FAIL** (C 9/12; B 10/12) | 11/12 under C (exploratory: the rule was designed after seeing 2019); the pre-set minute rule stays FAIL |
| Q3 noon anchor | Pass under B and C (medians 0.60 / 0.65) | Pass (0.50) |
| Q4 cross-vendor | **BLOCKED** (no TrueFX files) | **BLOCKED** |
| Q5 bid/ask sanity | Pass | Pass |
| Q6 coverage | Few stale runs (1); not re-measured as a coverage share | Pass (pilot, 99.90%) |
| Q7 weekends | Fails under C (4,843 ticks); 0 under B | Pass under C |
| Q8 stale and outliers | Described; confirmation **BLOCKED** | Described; confirmation **BLOCKED** |
| Q9 reproducibility | Pass | Pass |

**Overall: the HistData data has not passed, and can't pass without TrueFX (Q4 and Q8).** Its timestamps need a per-year test before any use. Priority 3 stays on hold.
