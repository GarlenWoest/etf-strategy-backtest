# FX period scheme, amendment A1: pre-1990 USD/JPY confirmation window (REJECTED DRAFT)

**Status: REJECTED by the owner 2026-11-02 (decision R4a).** Kept for the record. H5-B USD/JPY runs on the approved 1990–2014 / 2015–2023 scheme instead, labelled "weak confirmation: years seen in aggregate by Study 4". The approved FX period scheme is unchanged.

_Draft 2026-11-02, written to resolve the contradiction you raised under R4. Not in force until you approve it._

## 1. The contradiction

- **The approved FX scheme** (decision 2026-10-23, `research/memory/research.jsonl` line 1; `research/EXPANSION_PLAN.md:245-248`; `config.yaml:206`):
  - USD/JPY and GBP/USD in-sample 1990–2014;
  - validation 2015–2023;
  - 2024+ locked.
- **Nothing allows pre-1990 FX data.** A search of `config.yaml`, the research memory and `research/USDJPY_PREREGISTRATION.md` found no approval for using 1971–1989 [L].
- **The conflict:** Study 5 option P's trial H5-B on USD/JPY 1974–1989 is outside the scheme, so it needs this amendment, or it must be dropped.
- **GBP/USD stays on the approved scheme** (your R3); this amendment does not touch it.

## 2. What is already held and what has been examined

- **Held:** `data/raw/usdjpy/fred_DEXJPUS.csv` covers 1971-01-04 to 2023-12-29 (`data/raw/usdjpy/download_meta.json`) [L].
- **Examined so far, all from 1990 onward:**
  - the data-quality report covers 1990+ only (`reports/specialists/usdjpy/data_quality.md:5-7`);
  - Study 4 used 1990–2023 (warm-up from 1990, `config.yaml:255`);
  - the D2 constant used 1991–2023 (`research/USDJPY_FORWARD_TEST_PREREG.md:89`);
  - the D3 count used 2004–2023 (`:128`).
- **So no pre-1990 USD/JPY return, signal or statistic has been computed by the project** [L, from those records]. The rows are on disk, but unexamined.

## 3. Proposed amendment

- **A1.1 Window:** 1974-01-01 to 1989-12-31, USD/JPY only, as a single **confirmation window**. There is no in-sample/validation split: parameters come from the pre-registration, nothing is fitted, and K6 reads "n/a".
  - **Why 1974:** the yen floated in February 1973 [OV]. One year of warm-up gives σ60 and the other lookbacks a floating-rate history.
- **A1.2 Use:** only for trial **H5-B (volatility-target risk overlay)**, a risk claim judged on drawdown/CVaR. Any other hypothesis that wants this window needs its own amendment.
- **A1.3 One use:** the window may be used once, by the frozen Study 5 trial. Its results count toward cumulative N like any trial. Afterwards the window is "burned" for H5-B's family.
- **A1.4 Data rules:**
  - DEXJPUS (held) and DTB3 (held from 1954);
  - **Japan short rate:** the OECD IRSTCI01JPM156N starts around 1985 [OV]. The held MoF JGB file starts 1974-09-24, but which maturities exist that early is unverified.
  - Pre-register one of: (a) **spot-only** returns plus the USD T-bill (carry excluded, disclosed); or (b) a JGB-based JPY rate, if its coverage is verified. **Recommendation: (a),** because H5-B is a risk claim and carry is not its subject.
- **A1.5 Regime disclosure:** Japan's capital controls were liberalised around December 1980 [OV], and 1985 brought the Plaza Accord [OV]. The window is reported in full and in two halves (1974–1980, 1981–1989) for information. The decision uses the full window only.
- **A1.6 Nothing else changes:** the 2015–2023 validation window and the 2024+ holdout are untouched.

## 4. Alternatives

- **Decline A1:** drop H5-B USD/JPY. Study 5 becomes 2 trials (H5-B GBP/USD, G1 GBP/USD), N = 144.
- **Replace it:** test H5-B on USD/JPY within the approved scheme (1990–2014 / 2015–2023). That window has already been used by Study 4 for other hypotheses, but **not** for volatility targeting, so H5-B's family is untouched there [L: V135–V142 hypotheses, `reports/specialists/usdjpy/study1_kill_table.md:16-23`]. It needs no amendment. **This is probably the cleaner choice** (see the Study 5 v0.2 draft, §4).
