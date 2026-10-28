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
| FX002 Brunnermeier et al. | Partly → verified in full text (later on 10-28) | The October 7–8, 1998 USD/JPY drop is in the paper as a no-news move; its link to carry unwinding is the authors' conjecture |
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
- **Closed later on 10-28:**
  - **The 1998 crash claim is verified** in the NBER full text (WP 14473, PDF p. 3). It's presented as a no-news move, with carry unwinding as the authors' conjecture.
  - **Chen & Tsang's journal is verified:** Review of Economics and Statistics 95(1) 185–205 (2013), DOI 10.1162/REST_a_00231, from the Virginia Tech repository record.
  - Corrections applied: 23. USD/JPY depth is now L1 16, L2 5.

## 6. Addendum (2026-10-28 evening): full-text reads of five USD/JPY sources

**Why these five:** they're the sources most directly about the yen and our trial families (carry, crash risk, safe haven, UIP), plus the announcement-response paper that future event research would rely on. FX006 already had a content-level read, so it was skipped.

**How they were read:** each paper's lawful open-access full text was fetched (NBER working papers, the author's open-access JIE copy, City Research Online, the SNB working-paper series). Text was extracted locally with macOS PDFKit into git-ignored `tmp/papers/`, and the method, data, result tables and conclusions were read. **Depth is now L2 for all five. None is L3:** nothing was reproduced.

USD/JPY kept sources are now L0 5, L1 12, L2 9, L3 2. Across all sources: L0 207, L1 12, L2 9, L3 6. Records: `verification.csv` and `knowledge.csv`; build and audit rerun, 0 quality problems.

| Source | Method and sample | Main findings (as stated) | Limitations | What would invalidate it, and what it means for USD/JPY |
|---|---|---|---|---|
| **FX003** Engel, Kazakova, Wang, Xiang (JIE 2022) | Monthly Fama regressions with small-sample bias corrections, rolling 10-year windows, medium- and long-run versions; G10 vs USD, 1979:06–2020:09 | The interest-differential slope is unstable and changes sign after 2007 (JPY: −2.45 in 1987–2006, +3.61 in 2007–2020). Inflation differentials predict excess returns **in the panel** (−0.091, p < 0.01) | In-sample only, with no out-of-sample test; the authors call the findings "not definitive"; a risk-premium explanation isn't ruled out | **For the yen the inflation result fails:** the JPY slope is insignificant in every sample (p 0.20–0.89) and positive in 2007–2020. Invalidated if the panel slope fails out of sample after 2020. **No support for a USD/JPY inflation-differential rule** |
| **FX002** Brunnermeier, Nagel, Pedersen (NBER 2008) | Quarterly panel regressions with country fixed effects (1986–2006), weekly 1992–2006; CFTC futures positions, realised skewness, risk reversals, VIX/TED; VAR | A wider rate differential predicts negative skewness (crash risk); JPY is the funding currency with the highest positive skewness; VIX/TED rises coincide with carry losses and unwinds | In-sample; one regime; futures positions are a partial proxy; peso problem; the 1998 crash link is a conjecture | Invalidated if USD/JPY carry shows no negative skewness after 2006 in independent data. It describes the crash risk of being long USD/JPY, not a timing rule (our V139/V140 were killed) |
| **FX005** Menkhoff, Sarno, Schmeling, Schrimpf (JF 2012) | Monthly sorts of 48 currencies into 5 carry portfolios net of bid-ask, Nov 1983–Aug 2009; global FX-volatility innovations as a priced factor | Carry earns more than 5% a year net; volatility risk explains more than 90% of the cross-section; low-rate currencies (yen) hedge volatility shocks | Volatility innovations are estimated on the full sample, "preventing pure out-of-sample tests" (authors); a many-currency result, not a single-pair rule | Invalidated if the volatility-beta relation fails after 2009. For USD/JPY: a risk description, not a forecast |
| **FX010** Ranaldo, Söderlind (SNB WP 2007-17) | Regressions of depreciation on S&P and Treasury futures returns and FX volatility, contemporaneous plus one lag, from 3 hours to 4 days; 1993–2006 Reuters quotes | The franc is the strongest safe haven. **Yen/USD:** S&P t 2.84, FX volatility t 3.13, **Treasury notes insignificant (t 0.54)**, daily R² 0.02 | Contemporaneous co-movement, partly reversed the next day; "further lags were not significant"; table signs were lost in text extraction, so the authors' text was used | Invalidated if the yen doesn't rise against the USD in equity sell-offs or volatility spikes after 2006. A same-moment description, not a lead |
| **FX022** Andersen, Bollerslev, Diebold, Vega (NBER 2002 / AER 2003) | 5-minute Reuters quotes 1992–1998 regressed on standardized surprises against MMS consensus for 41 indicators | Prices jump in the first 5-minute interval. Yen/$ moves per 1 s.d. surprise: payroll 0.072%, trade balance 0.115% (significant). Bad news moves prices more, with a pronounced asymmetry for Yen/$ | Expansionary 1990s only; needs licensed consensus data (we have none); indicative quotes | Invalidated if independently timestamped data show no first-interval jump at scheduled releases. Supports our 0–5 s payroll timestamp test; gives no edge without consensus data |

**Overall:** none of the five offers a validated, single-pair USD/JPY trading rule. Three (FX002, FX005, FX010) describe risk and co-movement. FX003's positive result doesn't hold for the yen. FX022 needs consensus data we don't have.
