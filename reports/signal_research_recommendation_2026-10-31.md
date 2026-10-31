# Should a future, separately approved signal-research programme look for better-motivated opportunities? (Phase I, 2026-10-31)

_Research recommendation only. **No backtest was run, no rule was added, and F001/F002 are unchanged.** The historical research pause, the locked 2024+ holdout and historical N = 142 all stay as they are. Anything below needs your approval and its own pre-registration first. Not financial advice._

## 1. The problem, in numbers already on record

- **F001** fires about **1.2 times a year** (23 trigger days in 2004–2023). It needs 69 resolved signals for 80% power at an effect of d = 0.3, which takes **about 58 years**. Even 30 signals takes about 25 years.
- **F002** decides **12 times a year**. At an annual Sharpe of 0.4 it needs about **39 years** for 80% power; at 0.6, about 17.
- **Historical:** 142 trials, 140 killed by pre-registered rules, 2 (V119, V122) passed Study 3's primary rule but failed all robustness checks; none judged robust. For a 9-year validation window at N = 142, the luck hurdle was a Sharpe of about 0.58; realistic single-pair gross Sharpes are about 0.2–0.5 (10-29 report).

So the forward test can prove the plumbing and catch clear harm, but it can't validate either rule. **More alerts would not fix this.** A rule invented to fire more often just adds noise and raises N.

## 2. What a better-motivated programme would need (selection criteria)

| Criterion | Why | Minimum |
|---|---|---|
| Economic mechanism | Without one, a fit is most likely luck (lesson 4: most edges were fragile) | A published mechanism with an identified counterparty or constraint, read at L2 or deeper |
| Observations | Power comes from independent outcomes, not from alerts | Enough independent outcomes in the available pre-2024 history to reach 80% power at a plausible effect (Sharpe 0.3–0.5), **before** looking at returns |
| Data | Data quality decided several earlier verdicts | Two agreeing sources, licensed for the use; intraday only after the cross-vendor (TrueFX) check passes |
| Costs | Busy rules lost up to 0.41 Sharpe at 3x costs | Turnover low enough that the edge survives the frozen cost assumptions **and** the newly recorded spreads |
| Breadth | One pair is one noisy experiment | Same hypothesis testable on USD/JPY, GBP/USD and gold (where it applies), counted together in N |
| Falsifiable | Avoid untestable stories | A pre-written failure condition (as in the 10-29 report's H-list) |

## 3. Candidate research directions, USD/JPY first (ranked; none authorized)

| Rank | Direction (from the 10-29 report's list) | Horizon | Mechanism | Independent outcomes per year (rough, from the design, not from data) | Data status | Main risk |
|---|---|---|---|---|---|---|
| 1 | **Carry-to-risk conditioning** (H3): does the rate differential divided by volatility change USD/JPY drift and crash risk? | Daily signal, weekly to monthly holding | Carry compensation vs crash risk (Menkhoff et al. 2012; BIS 90) | ~12–50 (holding-period outcomes), across 3 markets | Rates and realized vol held (Fed H.10, FRED); implied vol not free, so realized vol is the honest proxy | Overlaps the killed Study 4 carry family; must be framed as conditioning, counted in N |
| 2 | **Volatility targeting as a risk tool** (H7): does scaling exposure by recent vol cut left tails without changing the Sharpe? | Daily, swing | Vol clustering (well documented); a risk claim, not a return claim | Many (daily), but the claim is about tails | Daily data held | Easy to mistake reduced drawdown for an edge (lesson 3) |
| 3 | **Deleveraging-overshoot reversal, re-specified for power** (H2): joint risk-off shocks partly reverse over 1–5 days | Swing (1–5 days) | Brunnermeier, Nagel & Pedersen 2008 [L2] | F001's 1.2/yr is too few; a pre-set lower threshold or a cross-market panel might reach ~5–15/yr | Daily data held; needs pre-2024 MoF and policy-day calendars | Lowering the threshold weakens the mechanism; must be a **new** pre-registered hypothesis, never a change to F001 |
| 4 | **Single-asset time-series momentum vs a sample-mean benchmark** (H1) across the three markets, with long history (USD/JPY from 1971) | Monthly | Huang et al. 2020 say it mostly matches a sample-mean strategy | 12/yr per market; ~36/yr pooled | Long daily history for FX held or available officially; gold monthly | Likely null (F002 is already this rule as a control) |
| 5 | **Announcement-day behaviour** around US releases | Daily (event days) | Price discovery on scheduled news (ABDV 2003) | ~40–60 event days/yr | Event calendar built; no consensus data, so no "surprise" measure | Without consensus, the effect is hard to define |
| 6 | **Tokyo fix / gotobi dollar buying** (H9) and other intraday effects (H10, H11) | Intraday | Documented corporate flows (Ito & Yamada 2017) | Many | **Blocked** until the TrueFX cross-vendor check passes, plus measured spreads | Costs decide it; needs measured spreads |

**Not recommended:** more moving-average, RSI or MACD variants (killed families); pattern libraries; LLM or foundation-model price forecasts (random-walk-level evidence); any rule chosen because it would alert more often.

## 4. Recommended path, if you decide to resume research

1. **First decide the statistical policy (E10 in the 10-29 report).** Keep cumulative N as is, or add family-wise tests (SPA/StepM) and count cross-market replications as one family. This decides whether any new study can pass at all; it's a choice, not a calculation.
2. **Do a power check before any returns are looked at** (frequency only, as D3 did for F001): count independent outcomes per direction in pre-2024 data. Drop any direction that can't reach about 30 outcomes in the validation window.
3. **Pre-register one small study** (2–4 trials, not dozens) of direction 1 or 3, replicated across USD/JPY, GBP/USD and (where applicable) gold, with the frozen kill rules, 2x/3x costs and the recorded spreads as a cost check.
4. **Only a survivor** of that could become a new forward rule (F003+), with its own pre-registration, forward N and owner approval. The forward system already has the plumbing for that.
5. **Intraday ideas wait** for TrueFX and measured spreads.

## 5. What this recommendation does not do

It runs no backtest, opens no holdout, adds nothing to the live or shadow system, changes neither F001 nor F002, and claims no edge. The "outcomes per year" figures are rough design counts to judge feasibility, not results.
