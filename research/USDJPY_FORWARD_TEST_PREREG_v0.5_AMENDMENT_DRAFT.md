# Forward test, amendment v0.5: financing-rate sources (DRAFT: candidates only; not frozen, not built)

_Draft 2026-11-02 at the owner's request (codes confirmed by read-only metadata lookups the same day): one amendment, reviewed together. It would replace FRED as the source of the two v0.4 financing series (risk register RR-1). Until you approve and freeze a final text, v0.4 stays in force unchanged (FRED DTB3 and FRED IRSTCI01JPM156N, with the minimal cache from the 11-06 batch)._

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

**Today:** FRED IRSTCI01JPM156N, the FRED mirror of the OECD series "Immediate interest rates, call money, interbank rate, Japan, monthly".

**Confirmed by read-only metadata lookups, 2026-11-02 (no observations downloaded):**
- **Dataflow:** `OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0` ("Financial market"). DSD `DSD_STES` 4.0, with dimensions REF_AREA, FREQ, MEASURE, UNIT_MEASURE, ACTIVITY, ADJUSTMENT, TRANSFORMATION, TIME_HORIZ, METHODOLOGY [V: https://sdmx.oecd.org/public/rest/dataflow/OECD.SDD.STES/DSD_STES@DF_FINMARK/latest?references=all].
- **Measure code:** `IRSTCI` = "Immediate interest rates, call money, interbank rate" (CL_MEASURE). Distinct from `IR3TIB` (3-month) and `IRLT` (long-term) [V: same response].
- **Series key:** `JPN.M.IRSTCI.PA._Z._Z._Z._Z.N` is **available**, with 495 observations reported by the availability constraint (metadata) [V: https://sdmx.oecd.org/public/rest/availableconstraint/OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0/JPN.M.IRSTCI......?mode=available].
- **Data request (for later, not used):** `https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0/JPN.M.IRSTCI.PA._Z._Z._Z._Z.N`.

**Still to confirm:**
- that the values equal FRED IRSTCI01JPM156N on shared months: a comparison on pre-2024 months, after you approve that data download;
- the OECD terms of use [U].

**Proposed text:** the JPY leg takes `JPN.M.IRSTCI.PA._Z._Z._Z._Z.N` from the OECD API. This is a source switch of the same series under the unchanged v0.4 age rules, conditional on the value comparison and the live overlap test.

## Candidate 3: BoJ daily call rate, as validation first

**Series (confirmed, 2026-11-02, metadata only):**
- **Database and code:** database `FM01` ("Uncollateralized Overnight Call Rate (average)", updated every business day), series code **`STRDCLUCON`**: "Call Rate, Uncollateralized Overnight, Average (Daily)", unit percent per annum, frequency daily.
- **Coverage:** start 1998-01-05; metadata reported last observation 2026-10-29 and last update 2026-11-02 [V: live `getMetadata` response, https://www.stat-search.boj.or.jp/api/v1/getMetadata?format=json&lang=en&db=FM01].
- **Companion series:** STRDCLUCONH and STRDCLUCONL, listed beside it in the manual's example.
- **API:** base `https://www.stat-search.boj.or.jp/api/v1/` with `getDataCode`, `getDataLayer` and `getMetadata`. Example: `getDataCode?lang=en&db=FM01&code=STRDCLUCON&startDate=YYYYMM`. Launched 18 February 2026 [V: https://www.boj.or.jp/en/statistics/outline/notice_2026/not260218a.htm; manual https://www.stat-search.boj.or.jp/info/api_manual_en.pdf].
- **Access conditions:** no API key appears in any documented request [V: manual]. A credit line is requested, and the service may be suspended without notice; the usage notice https://www.stat-search.boj.or.jp/info/api_notice_en.pdf must be read before use [U: not read in full].

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
2. Candidate 2: dataflow and key confirmed; approve a pre-2024 value comparison with FRED IRSTCI01JPM156N before deciding.
3. Candidate 3 as validation only.
4. Read the Treasury, OECD and BoJ API terms before freezing.
