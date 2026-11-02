# AQ-1: proposal for FRED-free sources (audit queue item 1)

_Proposal only. No code was changed. Background: FRED's Full Terms prohibit storing or archiving FRED content, while its public-domain tag allows use without permission (`research/R12_VERIFICATION_2026-11-02.md` item 7). The live runner caches FRED observations by design: v0.4 keeps the history of successful observations._

| Series (use) | Today | Proposed source | Evidence of equality | Change type |
|---|---|---|---|---|
| DTB3: USD financing leg (v0.4 canonical); ETF cash interest | FRED `fredgraph.csv?id=DTB3` (`src/live_usdjpy/financing.py:28`; `tools/paper_books.py:190-194`) | Federal Reserve Board **H.15**, series RIFSGFSM03_N.B (the series FRED mirrors as DTB3) | Board H.15 DDP package vs the stored FRED copy: **identical on all 17,491 shared dates, 1954–2023** (`research/DATA_REGISTER.csv`, 2026-11-02) | **Source switch, same series:** no amendment, if the live values stay identical over an overlap test (below) |
| IRSTCI01JPM156N: JPY financing leg (v0.4 canonical) | FRED (OECD MEI mirror) | **OECD** directly (OECD Data Explorer / SDMX API; the dataset and key for Japan's immediate interbank rate are **[U]**, to be identified) | Not yet compared | Same series from its publisher: no amendment if identical. If the OECD's current dataset differs from the MEI series FRED mirrors, that is a **different series** and needs **v0.5** |
| DTWEXBGS: weekly brief (information only) | FRED | Board **H.10** broad dollar index from the H.10 release data | Not yet compared | Information-only; no amendment |
| DFII10: weekly brief (information only) | FRED | Board **H.15** (10-year TIPS yield) | Not yet compared | Information-only; no amendment |

**Durability caveat [V]:**
- The Board's DDP "Build Your Package" option goes the week of 2026-11-09, and the Board plans to remove preformatted packages and eventually retire the DDP (https://www.federalreserve.gov/data/data-download-fred-information.htm, read 2026-11-02).
- The Board itself points users to FRED.
- The H.15 and H.10 release pages keep historical data as files [U: exact live endpoint and update time to be checked before building].
- **If no durable Board endpoint exists for daily live use, option (a) remains:** keep FRED for the live runner as local, private use of public-domain series, with the cache restricted to what v0.4 needs. That is your decision.

**Plan (Friday batch or later, your call):**
1. Identify the durable Board H.15 endpoint and the OECD dataset key; read their terms. Read-only, no download beyond the test.
2. **Overlap test:** for 10 business days, fetch both sources each roll day and record both values. Switch only if every overlapping value is identical.
3. Switch the live fetch, keeping the same series IDs in records and adding `source` provenance. Tests: parsing, an allow-list for the new host, and the never-0% / UNRESOLVED behaviour unchanged.
4. Mark the FRED cache superseded; keep it, unused.

**Effort:** M. **Amendment:** none for identical series; v0.5 only if the OECD series differs.
