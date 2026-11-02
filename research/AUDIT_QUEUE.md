# Audit queue

_Items waiting for an audit or fix. Each needs its own proposal and your approval. **No runner changes** until today's (2026-11-02) 16:45 ETF run and 17:02 ET financing roll are verified, and then only between scheduled runs, in a worktree, with tests._

## AQ-1: FRED terms vs the live runner's FRED pulls and cached copies (added 2026-11-02, decision D-FRED)

- **Finding:** FRED's Full Terms prohibit storing, caching or archiving FRED content, while series tagged "Public Domain: Citation Requested" "may be used without permission" (`research/R12_VERIFICATION_2026-11-02.md` item 7). Which clause governs public-domain series isn't stated.
- **Where the project pulls or stores FRED data** (from a code search, 2026-11-02):
  - **Live runner:**
    - `src/live_usdjpy/financing.py` pulls DTB3 and IRSTCI01JPM156N (`FRED_CSV`, line 28) and keeps a per-series cache of observations in the runner state (lines 8–9, 76–89).
    - `tools/usdjpy_pipeline.py` (rate fetch for financing).
  - **ETF books:** `tools/paper_books.py` uses FRED DTB3 for cash interest (`:190-194`); `tools/brief_market_data.py` pulls DTWEXBGS and DFII10 (`:10`, `:80`).
  - **Monitoring:** `tools/market_intel.py` (no longer scheduled).
  - **Historical downloads** (one-off, git-ignored `data/`): `tools/download_usdjpy.py`, `download_commodities.py`, `download_longhist.py`, `download_r8.py`, `validate_usdjpy.py`.
  - **Superseded for new studies:** the FRED copies of DEXUSUK and DEXJPUS (`research/DATA_REGISTER.csv`), replaced by the Board's own H.10 files, which are identical on every common date.
- **Proposed compliant sources, to check for terms and coverage before switching:**
  - **US T-bill (DTB3):** the Board's H.15 release (Data Download Program, or the H.15 data files on federalreserve.gov). Note that the Board is retiring parts of the DDP (the "Build Your Package" option goes the week of 2026-11-09), so the release's own data files are the durable source.
  - **Japan call rate (IRSTCI01JPM156N, an OECD series):** the OECD's own data API/explorer, under the OECD's terms. The deferred BoJ daily call-rate proposal (v0.5) would also remove this dependency.
  - **DTWEXBGS:** the Board's H.10 broad dollar index from the H.10 data files.
  - **DFII10:** the Board's H.15 (TIPS yields).
- **Constraint:** v0.4 freezes **IRSTCI01JPM156N** and DTB3 as the canonical financing series. Switching the *source* of the same series needs no rule change, if values are identical. Switching to a different series needs a new amendment (v0.5).
- **Status:** queued. No code changed.
