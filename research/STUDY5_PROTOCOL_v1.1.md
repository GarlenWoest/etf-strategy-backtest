# Study 5 protocol v1.1: for freeze approval (NOT frozen, NOT run)

_2026-11-02. The final review-ready protocol. It supersedes v1.0 (`research/STUDY5_PROTOCOL_v1.0.md`) and the drafts `research/STUDY5_DESIGN_DRAFT.md` (v0.1) and `research/STUDY5_DESIGN_DRAFT_v0.2.md`, all kept. **Nothing has been run:** no returns were computed and no trial ID is assigned until freeze. Historical N = 142, forward N = 2, the 2024+ holdout stays locked. The research pause lifts for this study only once you approve the freeze (R1)._

**Blocking items before freeze:** none apart from your freeze approval (§9).

## 1. Decisions applied

| Decision (2026-11-02) | Effect here |
|---|---|
| R2; pooling decision; Q1 withdrawn | Primary test per **STATS_POLICY v1.0 (frozen)**: strict DSR, full cumulative N, raw full-pool variance (option A). Test windows are 9 years, inside the P7 range 2.5–10 years, so no policy amendment is needed |
| P6 with conditions | Risk-claim trials (T1, T2) count in N and join the variance pool; their pass thresholds are the fixed numbers in §6 |
| D-FRED | H.10 data from the Federal Reserve Board's own Data Download Program; the FRED copies are SUPERSEDED (kept, not used) |
| Financing | **Spot-only** (no carry), stated as a limitation (§5); every return-claim result says "excludes carry" |
| R3 | GBP/USD on the approved scheme: in-sample 1990–2014, validation 2015–2023, 2024+ locked |
| R4 / R4a | Option P. H5-B USD/JPY on 1990–2014 / 2015–2023, labelled **"weak confirmation: years seen in aggregate by Study 4"**. Amendment A1 rejected (kept as a rejected draft). Volatility targeting is judged on **risk reduction, not Sharpe** |
| R5 | Fixed kill-rule definitions (§6) |
| R7 | G1 frequency count done: **72 events in validation, 189 in-sample** (≥ 50, so G1 stays) |
| R8 | Ken French daily factors downloaded (`research/DATA_REGISTER.csv`); DEXUSUK replaced by the Board copy under D-FRED |
| R9 | Family-wise test: **"not computed"** |
| R11 | G1 in; G2 rejected; G3 forward only |
| R12 | Verification record: `research/R12_VERIFICATION_2026-11-02.md` |
| G1 kept | With the evidence statement in §7 |

## 2. Trials (IDs assigned at freeze; cumulative N 142 → 145)

| Proposed ID | Trial | Market | Claim | Windows |
|---|---|---|---|---|
| V143 | T1 H5-B volatility-target overlay | GBP/USD | **Risk** | IS 1990-01-02..2014-12-31; validation 2015-01-02..2023-12-29 |
| V144 | T2 H5-B volatility-target overlay. **Weak confirmation: years seen in aggregate by Study 4** | USD/JPY | **Risk** | same |
| V145 | T3 G1 month-end equity-hedge flow | GBP/USD | Return | same |

## 3. Data

All series are truncated before 2024-01-01; nothing 2024+ is opened.

| Series | File | Status before the run |
|---|---|---|
| USD per GBP, H.10 noon (Board series RXI$US_N.B.UK) | `data/raw/board_h10/board_h10_usd_per_gbp.csv` (sha256 in the register) | **Validate first** (duplicates, gaps against the H.10 Board calendar, stale runs, large moves); report before any rule is evaluated. Identical to the superseded FRED DEXUSUK copy on all 13,290 common dates (data-quality cross-check, counts only); 535 "ND" holiday rows are blank |
| JPY per USD, H.10 noon (Board series RXI_N.B.JA) | `data/raw/board_h10/board_h10_jpy_per_usd.csv` | Identical to the superseded FRED DEXJPUS copy (validated 1990+, `reports/specialists/usdjpy/data_quality.md`) on all 13,284 common dates; re-run the same validation on the Board file |
| Ken French daily (Mkt-RF + RF) | `data/raw/r8_kenfrench_daily/kf_factors_daily.csv` | Already used for the R7 count; units are decimal |
| 3-month T-bill, secondary market (Board H.15 series RIFSGFSM03_N.B; the series FRED mirrors as DTB3) | `data/raw/board_h15/board_h15_tbill_3m_secondary.csv` (sha256 in the register) | Identical to the superseded FRED DTB3 copy on all 17,491 shared dates (0 mismatches); 769 "ND" rows blank |
| Foreign short rates | Not held, not used | Spot-only decision (§5) |

## 4. Rules (fixed numbers; nothing fitted)

**T1 / T2: H5-B volatility-target overlay (a risk claim)**
- **Base position:** constant, in the sign of the pair's in-sample (1990–2014) mean daily log return, computed once at the run's start and recorded. This follows the D2 approach (`research/USDJPY_FORWARD_TEST_PREREG.md:89`). The unscaled base is 1.0x in that sign.
- **Scaled position:** x_t = min(1, 0.10 ÷ σ60_t), where σ60 is the annualized standard deviation of the last 60 daily log returns up to the month-end decision day. Decided at each month-end, executed at the next FX day's noon rate.
- **Comparison:** scaled vs unscaled base, with the same costs, financing treatment and cash.

**T3: G1 month-end equity-hedge flow (a return claim)**
- **Trigger:** on the second-to-last NYSE trading day *t* of each month, R = the US market (Mkt-RF + RF) compounded return from the month's first trading day through *t − 1*.
- **Position:** if R ≥ +0.02, long GBP/USD; if R ≤ −0.02, short. Enter at day *t*'s H.10 noon rate, exit at day *t + 1*'s noon rate. Size 1.0x.
- **No-data days:** if *t* or *t + 1* has no H.10 rate (US Board holiday), there is no trade, recorded as "no data".
- **Placebo:** the same rule on the 10th NYSE trading day of each month.

## 5. Costs and financing

- **Costs:** 0.015% of notional one-way (the frozen FX assumption, `config.yaml:258`), with 2x and 3x as kill checks.
- **Financing: spot-only (owner decision 2026-11-02).** Positions earn the spot return only; the interest-rate differential (carry) and the broker financing markup are **not** included. Idle cash earns the USD 3-month T-bill (Board H.15).
- **Limitation, stated in every report:**
  - T1/T2 (risk claims) are scaled and unscaled versions of the same spot exposure, so the comparison is like for like, but the absolute returns exclude carry.
  - T3 (a return claim) holds one day per event, so omitted carry is at most one day's differential per event.
  - **Every return-claim result is labelled "excludes carry".**

## 6. Kill and pass criteria (R5 definitions)

**T1 / T2: primary criterion is risk reduction, not Sharpe** (R4a). Measured in the validation window, scaled vs unscaled:
- **R-1:** realized annualized volatility is lower, and the one-sided 95% interval of the difference excludes 0 (stationary bootstrap of 5-day blocks over paired daily returns; 10,000 resamples; seed 20261102).
- **R-2:** maximum drawdown is at least 25% smaller (relative).
- **R-3:** the worst calendar-month return is at least 25% smaller in loss (relative).
- **R-4 (robustness, as kill rules):** R-1 to R-3 still hold at 2x and 3x costs, and with execution one extra FX day later.
- **R-5:** the same direction holds in-sample on R-1 to R-3 (the 25% margins don't apply there; K6 sense).
- **K7:** no fall to 20% of capital in any stress window.

These thresholds (95%, 25%, 25%, 2x/3x, one extra day) are fixed now (P6(b)). T1 and T2 **count in cumulative N** (P6(a)). Their Sharpe and DSR (STATS_POLICY v1.0) and the family-wise status ("not computed") are reported, not decisive. **A pass means "reduced risk", never "has an edge".**

**T3:**
- **K1:** mean net excess return per event > 0 in validation, and greater than the placebo's.
- **K2:** DSR ≥ 0.95 at N = 145 under STATS_POLICY v1.0 (raw full-pool variance including T1–T3; hurdle about 0.71 annual Sharpe, to be recomputed with T1–T3 in the pool).
- **K3:** mean **excess** return per event still > 0 at 2x and 3x costs.
- **K4:** at least 30 validation events (R7 counted 72 trigger months; the realised count excludes no-data days).
- **K5:** thresholds of ±0.015 and ±0.03 must not reverse the sign of the validation mean.
- **K6:** validation mean at least ½ of in-sample, **only if** the in-sample mean is > 0.
- **K7:** no fall to 20% of capital.
- **Robustness as kill rule:** entering one day earlier (third-to-last day) must not reverse the sign.

## 7. Power (estimates)

- **T3:** validation, 72 events: d ≈ 0.29 per event needed for 80% power; in-sample, 189 events: d ≈ 0.18.
  - Round-trip cost ≈ 0.05 daily σ [estimate].
  - **Prior:** published evidence of the month-end effect is pre-2015 [V: Melvin & Prins 2015]. No primary post-2015 evidence was found [U]. Krohn et al. (2024) find their persisting fix reversals are not driven by the month-end channel [V].
  - **Mechanism evidence is weak.** No post-2015 primary evidence on the month-end effect was found (R12 item 5), and Krohn, Mueller & Whelan (2024) attribute the persisting fix reversals to another channel (dealer inventory risk around daily fixes), not month-end equity hedging (R12 item 4).
  - **Expected outcome registered in advance: rejection.**
- **T1 / T2:** precision limited by the number of stress episodes in 2015–2023. Bootstrap intervals are reported.

## 8. Run plan (after freeze only)

1. Freeze: SHA-256 of this file in the protocol register and the research memory; trial rows V143–V145 PRE-REGISTERED in `research_log.csv`.
2. DEXUSUK validation report, stopping if it fails.
3. One run, all trials, no reruns except for a disclosed bug fix.
4. Kill table and report, wording per policy §4; every return-claim figure labelled "excludes carry".
5. Results go to the research memory.

## 9. Open items

| Item | Status |
|---|---|
| Statistics policy | **Frozen v1.0** (option A + P7 + P6 conditions) |
| D-FRED | Done: Board H.10 files registered; FRED copies superseded |
| Financing | Spot-only (decided) |
| **Freeze approval of this protocol (R1)** | **Pending: yours** |

On approval: freeze (hash in the protocol register and research memory), log V143–V145 as PRE-REGISTERED, then stop. Run only on a separate instruction.
