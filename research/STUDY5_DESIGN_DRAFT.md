# Study 5: design draft (NOT pre-registered; for the owner's review)

_Draft 2026-11-01. **Document only:** no data was loaded, nothing was run, and no trial ID was assigned. Historical N stays 142 and forward N stays 2. The 2024+ holdout stays locked, and the research pause stays in force until you approve a pre-registration. Every number marked "estimate" is arithmetic or an assumption, not a measurement._

## 1. Why, and what this is not

- **The problem:** the two forward rules can't be validated within a decade. F001 fires about 1.2 times a year (23 trigger days in 2004–2023), and F002 needs about 39 years for 80% power at an annual Sharpe of 0.4 (pre-registration §6).
- **The proposal:** a small, separately approved historical study of the three best-motivated directions from the Phase I recommendation, replicated across markets. Breadth comes from *markets*, not from more rule variants.
- **Not this:** a search for something that alerts more often, or a change to F001/F002 or the running forward test.

## 2. Hypotheses (economic rationale first; parameters fixed in advance as round numbers, not fitted)

### H5-A: carry-to-risk conditioning (USD/JPY, GBP/USD)

- **Mechanism:** carry is compensation for crash risk. A rate differential that is large *relative to recent volatility* should earn more per unit of risk than a small one (Menkhoff et al. 2012; Brunnermeier, Nagel & Pedersen 2008, read in full).
- **Rule:**
  - At each month-end compute C = (i_USD − i_foreign) ÷ σ60, where the rates are 3-month rates (US: DTB3 or TB3MS; Japan and UK: OECD immediate rates, monthly) and σ60 is the annualised volatility of the last 60 daily log returns of the pair.
  - If |C| ≥ 0.5, hold the pair for one month in the direction that earns the differential (long USD when i_USD > i_foreign). Otherwise stay flat.
  - Size 1.0x of the ledger, never above 1x.
- **Trials:** 2 (one per pair).
- **Contradicting evidence:** single-pair carry is weak, and the killed Study 4 carry rules (V135–V136, V139–V140) are in the same family (see §4). Gold has no usable carry series, so it is excluded.

### H5-B: volatility targeting as a risk overlay (USD/JPY, GBP/USD, gold)

- **Mechanism:** volatility clusters, so scaling exposure down when recent volatility is high should cut the left tail. Published evidence: tails fall, but Sharpe is not reliably improved (Harvey et al. 2018).
- **This is a risk claim, not a return claim.**
- **Rule:** take a fixed base position (gold long; each FX pair in the sign of its own historical sample mean, fixed once like D2) and scale it to x = min(1, 10% ÷ σ60), rebalanced monthly.
- **Trials:** 3 (one per market).
- **Success** means a lower worst drawdown and a lower 1% CVaR versus the unscaled base, with Sharpe not significantly lower (§7). It does **not** mean "profitable".

### H5-C: deleveraging-overshoot reversal, re-specified for power (USD/JPY, gold)

- **Mechanism:**
  - Forced deleveraging overshoots fundamentals and partly reverses: yen-funded carry unwinds (FX002) and margin-driven selling of gold in liquidity crises.
  - GBP is not a funding currency, so the mechanism does not apply to it; GBP/USD is **excluded** rather than tested for its own sake.
- **Rule:**
  - On a day when the market's log return ≤ −1.5 × σ60 **and** the US stock market's ≤ −1.5 × σ60, go long the market at the next day's close and hold 5 trading days.
  - Exclusions as in F001 (policy-decision days, bank holidays); MoF intervention days are flagged.
- **This is a new hypothesis, not a change to F001:** different threshold, horizon, entry timing and markets.
- **Trials:** 2.

**Total: 7 trials.** Under policy 1 below, cumulative N would become **149**.

## 3. Data sources and licences

| Need | Source | Coverage | Licence / terms | Notes |
|---|---|---|---|---|
| USD/JPY, GBP/USD daily | FRED: Fed H.10 noon rates DEXJPUS, DEXUSUK | 1971– | US public domain (FRED terms) | Already validated (H.10 calendar, stale 2007 rows known) |
| US 3-month rate | FRED DTB3 (daily), TB3MS (monthly) | 1954– | Public domain | |
| Japan, UK short rates | FRED mirror of OECD MEI immediate rates (IRSTCI01JPM156N, IRSTCI01GBM156N) | ~1985– (Japan); earlier coverage to check | OECD terms via FRED | **Monthly averages with a ~1-month publication lag: use the observation available at each month-end (no look-ahead)** |
| BoE Bank Rate | BoE database | — | **robots.txt disallows `/boeapps/iadb`: not used** | |
| US stock market, daily (H5-C) | Ken French daily market return | 1926– | Free for research | Already used in Study 3 (monthly) |
| Gold, daily | No free licensed long daily series (LBMA needs a licence; FRED dropped its gold series) | — | — | **H5-B and H5-C gold: see §4. Possibly monthly World Bank only, or excluded** |
| Gold, monthly | World Bank Pink Sheet | 1960– | Free | Burned for monthly trend (Study 3) |

## 4. Which periods are untouched and which are burned

| Market | Used before | Burned for | Untouched |
|---|---|---|---|
| USD/JPY | Study 4: warm-up from 1990, in-sample 1991–2014, validation 2015–2023 (carry, differential momentum, risk-off filter, curve slope). D3 counted F001 trigger *frequency* (no returns) on 2004–2023. Forward test 2026– | **The carry family on 1990–2023** (H5-A is in the same economic family). H5-C's returns weren't examined, but 2004–2023 frequencies were | **1971–1989** daily FX (rates from ~1985 for the OECD Japan series: H5-A window ~1986–1989, too short). H5-B and H5-C: 1971–1989 (H5-C needs stock data: Ken French daily OK) |
| GBP/USD | Never studied (the FX period scheme was set in 2026-10 but never run) | Nothing | **1971–2023**, subject to the rate series' start |
| Gold | Studies 1/2 (GLD 2006–2023, daily); Study 3 (monthly 1960s–2018 average prices) | Daily 2006–2023; monthly trend | **No untouched licensed daily window.** Monthly pre-2006 only for families other than trend (H5-B), and only on monthly averages (smoothing caveat: correlation 0.58 with month-end prices) |
| All | — | — | **2024+ is the locked holdout for every market** |

**Consequence:**
- GBP/USD carries the main historical test of H5-A and H5-B.
- USD/JPY 1971–1989 is a short confirmation window (H5-B, H5-C), and 1986–1989 for H5-A, which is too short to judge alone.
- Gold can be tested historically only weakly (H5-B on monthly averages) or not at all. Its realistic route is the **forward** observation layer, which is already running as INFORMATION ONLY.

## 5. Cumulative-N policy (a decision for you)

| Option | What it means | Pros | Cons |
|---|---|---|---|
| **1. Keep cumulative N** (142 → 149) in the Deflated Sharpe | Every trial ever run counts | Most conservative; consistent with Studies 1–4 | At realistic single-market Sharpes (~0.2–0.5) the hurdle is close to unreachable in 20–50-year windows: a likely "nothing passes" by construction |
| **2. Effective N** (cluster correlated trials, e.g. by return correlation > 0.7, before seeing Study 5's results) | Counts *independent* tries | More accurate when many trials are near-duplicates (Studies 1–2 had many) | The clustering rule must be fixed in advance; judgment enters; can look like loosening the bar |
| **3. Family-wise tests** (Hansen SPA / Romano-Wolf StepM over the Study 5 family, with Studies 1–4 disclosed) | Controls false discoveries *within* the new family, against its benchmarks | Standard and transparent; power matches the family size | Doesn't penalise earlier families unless they are included; needs a bootstrap implementation (the `arch` package would need install approval) |

**Suggestion (yours to decide):** pre-register **3** as the primary test, **1** (DSR at N = 149) as a reported secondary, and state in advance that a pass on 3 that fails 1 is reported exactly as such. Never silently.

## 6. Power (estimates; normal approximation; nothing computed on data)

- **H5-A, monthly holding (GBP/USD 1975–2023 ≈ 49 years ≈ 590 months):** at a true annual Sharpe of 0.3, the t-statistic is about 0.3 × √49 ≈ 2.1, roughly 55% power one-sided at 5%. At 0.4, about 2.8 (~80%). One pair alone is marginal; two pairs help only partly, since both are quoted against the USD.
- **H5-B:** a tail claim. Its power depends on the number of crisis episodes in the window (GBP/USD 1975–2023 has perhaps 6–10 large stress episodes): low precision. It would be judged on effect size with bootstrap intervals, not a p-value alone.
- **H5-C:** event count at the −1.5σ joint threshold, **to be counted on frequency only (no returns) under a D3-style approval before freezing.** Under independence a −1.5σ day is ~6.7% of days per leg; the joint rate depends on the correlation (the −2.0σ count was 23 days in 2004–2023). A rough estimate is 3–4 times that: ~4–5 events a year. At 5-day holds, d = 0.2 needs ~155 events, about 30–40 years: borderline even with 1971–1989 plus a second market.

## 7. Kill criteria (adapted from K1–K7; fixed before any run)

- **K1, benchmarks:** beat cash, the market's sample-mean-sign position, and a simple trend (SMA20 sign) out of sample. H5-B instead: lower worst drawdown **and** 1% CVaR by ≥ 25% versus the unscaled base, with Sharpe not significantly lower (paired bootstrap, 5%).
- **K2, luck:** family-wise test p < 0.05 (policy 3), DSR reported at N = 149 (policy 1).
- **K3, costs:** still positive at 2x the frozen costs (FX 0.015% one-way plus financing; gold per the instrument).
- **K4, sample:** ≥ 30 independent outcomes (H5-A months, H5-C events) or ≥ 10 years.
- **K5, fragility:** one pre-set neighbour per trial (H5-A threshold 0.75; H5-B target 12%; H5-C −1.75σ) must not reverse the sign.
- **K6, decay:** out-of-sample at least half of in-sample, where a split exists. With no fitting, the whole untouched window is out of sample and K6 reads "n/a".
- **K7, crash:** no fall to 20% of capital in any stress window.

## 8. What a forward test would look like

- **Who qualifies:** only trials that pass every kill criterion.
- **How:** each becomes F003+ with its own pre-registration (parameters frozen, forward N increased) and runs in the existing shadow plumbing: registry, gate, internal simulator, reconciliation, tickets labelled EXPERIMENTAL, scorer with baselines and power banner, and the v0.4 financing rules.
- **Gold or GBP/USD forward trials** would need your separate decision to extend paper workflows beyond USD/JPY. Today they are observation-only.
- **Nothing advances automatically.**

## 9. Open decisions before anything is pre-registered

1. The cumulative-N policy (§5).
2. Whether the frequency-only H5-C event count (pre-2024, no returns) may be run, like D3.
3. Gold: exclude it from the historical part, or accept monthly-average H5-B only.
4. Any install (the `arch` package for SPA/StepM) and any new data download, each separately.
