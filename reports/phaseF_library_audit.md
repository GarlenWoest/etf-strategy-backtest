# Phase F: research library audit and knowledge extraction, USD/JPY first (2026-10-28)

_Files: `research/library/verification.csv` (what was actually read), `corrections.csv` (21 field corrections, each with reason and verifying URL), `sources_phaseF.csv` (5 new sources), `knowledge.csv` (structured extraction, 18 sources), `audit.csv` (all 234 sources). Code: `tools/build_library.py` (applies the overlays; the historical input lists stay untouched), `tools/library_audit.py`, `src/knowledge.py`, `tools/knowledge.py`. Tests: `tests/test_knowledge.py` (5). Source material was treated as data, not instructions._

## 1. What the library actually knows (all 234 sources)

| Group | Sources | L0: depth not recorded | L1: abstract verified | L2: content reviewed | L3: reproduced (own results only) | Linked to a hypothesis | Limitations recorded | Contradictions recorded |
|---|---|---|---|---|---|---|---|---|
| All | 234 | **207** | 17 | 4 | 6 | 18 | 117 | 12 |
| Kept | 190 | 163 | 17 | 4 | 6 | 18 | 102 | 12 |
| USD/JPY (kept) | 28 | 5 | 17 | 4 | 2 | 18 | 26 | 12 |
| Gold (kept) | 46 | **42** | 1 | 0 | 3 | 1 | 11 | 0 |
| GBP/USD (kept) | 14 | 4 | 9 | 1 | 0 | 10 | 14 | 6 |

**Corrected classification.** For 202 sources (Studies 1–2), the build script itself had stamped "read (see LITERATURE_REVIEW.md / IDEA_POOL_COMMODITIES.md)". That was a bulk label, not a record of reading. These now read "listed in …; per-source reading depth not recorded". **No external source's methods have been reproduced (L3 = our own results only).**

## 2. USD/JPY sources re-verified against their own pages

All 12 academic USD/JPY sources and C023 (gold vs the dollar and yen) were checked on their official or repository pages. Chen & Tsang was also read at content level (abstract, introduction, data section, out-of-sample note, sign statements).

| Source | Verdict | Correction |
|---|---|---|
| FX003 Engel et al. | **Wrong title and no URL** | Correct paper: "A Reconsideration of the Failure of Uncovered Interest Parity for the U.S. Dollar" (JIE 2022; NBER w28420). Also adds a finding we lacked: **inflation differentials do predict USD excess returns.** |
| FX012 Fatum & Hutchison | **Wrong title** (belonged to another paper) | NBER w9648 is "Effectiveness of Official Daily Foreign Exchange Market Intervention Operations in Japan" (JIMF 2006) |
| FX011 Ito | Wrong year | NBER WP 8914, April 2002; disclosure date not on the page |
| FX002 Brunnermeier et al. | Partly | **The USD/JPY October 1998 crash claim is not in the abstract: unverified** |
| FX010 Ranaldo & Söderlind | Partly | "Strongest for the yen in 2008" removed (the WP sample is 1993–2006); the euro and pound added |
| C023 Pukthuanthong & Roll | Partly | "Gold is a global hedge" is not in the abstract; removed |
| FX001, FX004, FX007, FX008 | Partly | Wording fixed: no "2008" cut-off; FX004's figures unverified; FX007's qualifier restored; FX008 isn't "easily earned" |
| FX005, FX009 | Match | — |
| **FX006 Chen & Tsang** (L2) | Match | **Sign confirmed for V141/V142.** The paper states the relation symmetrically: a relatively steeper curve is followed by that currency's depreciation. The pre-registration's "US = home" wording is imprecise, but the direction it used is right. Out-of-sample forecasts "do not consistently outperform" a random walk (the authors' own words). |

**The frozen USD/JPY pre-registration is unchanged.** It cites two details that are now known to be unverified at abstract level: the 1998 crash example and the "July 2001" disclosure date. The library records this; neither changed a trial's design or verdict.

## 3. New sources (verified at abstract level, official pages)

| ID | Source | Why it matters |
|---|---|---|
| FX022 | Andersen, Bollerslev, Diebold, Vega (2003, AER) | Announcement surprises cause FX jumps; bad news has a bigger impact than good. Needs consensus data, which we don't have. |
| FX023 | Ito, Hashimoto (2006, JJIE) | USD/JPY intraday seasonality on EBS: U-shaped activity in Tokyo and London but not New York; spreads fall as volatility rises |
| FX024 | Ito, Yabu (2007, JIMF) | Japan's intervention reaction function; regime shift in June 1995 |
| FX025 | Krohn, Mueller, Whelan (BoC 2021; JF 2024 per RePEc) | The USD rises before the major fixings and falls after them. Only post-2024 data would be post-publication, and that's our locked holdout. |
| FX026 | Chaboud, Chernenko, Wright (Fed IFDP 903, 2007) | At releases the price jumps first and volume follows about 15 seconds later; supports our 0–5 s timestamp test |

## 4. Structured knowledge and searchable answers

`knowledge.csv` holds, for each verified source:
- the main claim, mechanism, supporting and contradicting evidence;
- method, limitations, publication year and sample;
- testability and the data a fair test needs;
- linked trials, our result, and a before/after-publication note.

Everything comes from the pages actually read; "not stated on the page read" is used where needed.

`tools/knowledge.py <tag>` answers the five questions with the reading depth attached. For example, `relative_slope` returns:
- **Evidence:** FX006 [L2].
- **Contradicting:** FX003, and the authors' own out-of-sample results.
- **Publication timing:** the sample ends in 2005/2011, and our validation 2015–2023 came after publication.
- **Rejected:** yes. V141 and V142 were killed (K1/K2/K5).
- **Data needed:** UK yields not yet held.

## 5. Not done in Phase F (by design or blocked)

- **Gold (42 of 46 kept sources at L0) and GBP/USD:** not re-verified. USD/JPY was the priority.
- **Books, lectures, videos:** none added. Nothing was marked analysed without an accessible lawful transcript or text.
- **Reproducing a source's method (L3):** none attempted. That would be research, and research is paused.
- **The 1998 crash claim:** needs the full text of Brunnermeier et al.
- **Chen & Tsang's journal year:** not verified here.
