# Phase D: 2018 time-zone test, fixed before analysis (2026-10-28)

_Written and committed after downloading the 2018 HistData USD/JPY tick files (12 monthly zips, 95,572,014 bytes, sizes read from the response headers first) and **before any 2018 data was read or analysed**. The 2019 pilot results and verdicts are unchanged._

## Hypothesis under test (derived from 2019, so 2018 is the first separate test)

HistData file time = **UTC−5 in EU winter and UTC−4 during EU summer time** (reading C; implemented as `file + 7 h` read as Europe/Helsinki wall time). In 2018 the EU summer period is 25 March – 28 October; the US summer period is 11 March – 4 November.

## Primary rule (user-approved 2026-10-28, `config.yaml specialists.data_quality.q2_timezone_rule`)

- **Event:** BLS Employment Situation releases at 08:30:00 New York.
- **2018 release dates** (BLS archive links, bls.gov/bls/news-release/empsit.htm): 01-05, 02-02, 03-09, 04-06, 05-04, 06-01, 07-06, 08-03, 09-07, 10-05, 11-02, 12-07.
- **Jump:** the first tick-to-tick mid move ≥ 3 pips (0.03 yen).
- **Window:** 0–5 seconds after 08:30:00 New York.
- **PASS** if this holds for **≥ 11 of the 12 releases** under reading C. A release with no jump in the window counts as a miss.

## Supporting checks (reported; they do not change the primary verdict)

- **H.10 noon anchor:** median absolute difference between the HistData mid at 12:00 New York and the Fed H.10 noon rate ≤ 3 pips (the Q3 rule).
- **Weekend window:** under reading C, ticks inside Friday 17:00 – Sunday 17:00 New York are < 0.01% of all ticks (the Q7 rule).
- **Other readings:** A (FAQ, fixed UTC−5) and B (New York local time) are reported for comparison, **not** chosen after the fact. If C fails and another reading passes, that is reported as a finding to be tested on a third year, not adopted.
- **Discriminating releases:** 2018-11-02 (US summer, EU winter) separates B from C; April–October releases separate A from C.

## Not changed

- The pre-set minute rule and the 2019 FAIL stay on record.
- The TrueFX cross-vendor tests (Q4, and confirmation of the Q8 outliers) stay **BLOCKED** until the files exist.
- No 2024+ data.
