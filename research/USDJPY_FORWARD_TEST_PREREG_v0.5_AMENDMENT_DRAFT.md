# Forward test, amendment v0.5: financing-rate sources (DRAFT: candidates only; not frozen, not built)

_Draft 2026-11-02 at the owner's request: one amendment, reviewed together. It would replace FRED as the source of the two v0.4 financing series (risk register RR-1). Until you approve and freeze a final text, v0.4 stays in force unchanged (FRED DTB3 and FRED IRSTCI01JPM156N, with the minimal cache from the 11-06 batch)._

**Tags:**
- **[L]** checked locally.
- **[V]** verified at a primary source (URL given).
- **[U]** unverified.

## Candidate 1: US leg from the U.S. Treasury's Daily Treasury Bill Rates

**Series:** Treasury's "Daily Treasury Bill Rates", **13 WEEKS BANK DISCOUNT** column (https://home.treasury.gov/resource-center/data-chart-center/interest-rates/, CSV by year).

**Comparison with what v0.4 uses** [L: `tools/compare_treasury_bills.py`, files in `research/DATA_REGISTER.csv`]:
- **v0.4 today:** DTB3 = the Board's H.15 "3-month Treasury bill, secondary market, discount basis" (Board series RIFSGFSM03_N.B). The Board file is identical to the FRED DTB3 copy on all 17,491 shared dates, 1954–2023.

| Treasury column | Shared dates with H.15 3-month, 2015–2023 | Identical (\|diff\| < 0.005 pp) | Mean diff | 95th pct \|diff\| | Max \|diff\| |
|---|---|---|---|---|---|
| 13 weeks **bank discount** | 2,251 | **2,251 (100%)** | 0.000 pp | 0.000 pp | 0.000 pp |
| 13 weeks **coupon equivalent** | 2,251 | 903 (40%) | +0.033 pp | 0.16 pp | 0.16 pp |

**Reading:**
- On every shared date 2015–2023, the bank-discount column **is the same number as DTB3**, so using it is a **source switch of the same series**.
- The coupon-equivalent column is a **different measure**: a bond-equivalent yield, higher by up to 0.16 pp at the rates of that period. Using it would be a **series change** and is **not proposed**.
- Not checked: dates before 2015, and whether this identity persists after 2023. A live overlap test is required (below).

**Proposed text:**
- The USD leg uses the U.S. Treasury Daily Treasury Bill Rates, 13-week bank-discount rate (the same rate as H.15 DTB3), dated by its business date, under the unchanged v0.4 age rules: valid ≤ 3 US business days, carried 4–5, UNRESOLVED > 5.
- **Switch condition:** a 10-business-day live overlap with identical values on every overlapping date. Otherwise FRED DTB3 remains.

**Terms:** U.S. government publication [U: Treasury site terms not read].

## Candidate 2: Japan leg from the OECD directly

**Today:** FRED IRSTCI01JPM156N, the FRED mirror of the OECD Main Economic Indicators series "Immediate rates: call money / interbank, Japan, monthly average".

**Candidate:** the same series from the OECD's own SDMX API (`https://sdmx.oecd.org/public/rest/data/{agency},{dataflow},{version}/{key}`). **The dataflow and key for the immediate (call/interbank) rate for Japan are [U]:** the current OECD Data Explorer short-term-rates dataflow lists a 3-month interbank measure (IR3TIB) that FRED also mirrors. Whether the *immediate-rate* series (IRSTCI) is still published as such is unverified.

**Proposed text, conditional:**
- If the OECD publishes the identical IRSTCI series, the JPY leg takes it from the OECD API: a source switch, same series, same v0.4 age rules.
- If only a different series exists (e.g. IR3TIB, 3-month), switching is a **series change**. It must be stated here with its definitional difference and a comparison on shared months before freezing.

**Terms:** OECD terms of use [U: not read].

## Candidate 3: BoJ daily call rate, as validation first

**Series:** the BoJ uncollateralized overnight call rate (daily), from BoJ Time-Series Data Search. The BoJ launched an API for this database on 18 February 2026 (JSON/CSV) [V: https://www.boj.or.jp/en/statistics/outline/notice_2026/not260218a.htm; exact series code, key requirement and API terms [U]].

**Proposed role, in this amendment: validation only, not booking.**
- Record the daily BoJ call rate beside the monthly JPY rate used for booking.
- Report the monthly-average difference.
- The question to settle (should booking switch to the daily rate?) is a separate later decision, because a daily rate changes roll-level amounts versus a monthly average.

## Common rules for all candidates

1. No candidate is used for booking before its overlap test passes and this amendment is frozen.
2. Missing data is never 0%; UNRESOLVED and TRUE-UP are unchanged.
3. Every booked roll records the source, series ID, observation date and retrieval time.
4. Each new host is a read-only allow-listed GET, with tests (order endpoints unaffected).
5. Historical comparisons use pre-2024 data only. Live overlap values are recorded inside the forward registry (D1).

## Decisions needed (together)

1. Candidate 1 (Treasury bank-discount), with the overlap condition.
2. Candidate 2: identify the exact OECD dataflow first (a read-only metadata query), then decide.
3. Candidate 3 as validation only.
4. Read the Treasury, OECD and BoJ API terms before freezing.
