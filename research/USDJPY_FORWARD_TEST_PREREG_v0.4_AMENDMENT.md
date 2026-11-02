# USD/JPY forward test: v0.4 financing-data amendment

**Status: FROZEN 2026-11-02, before any financing accrued on any forward position.** Owner decisions 2026-11-01. The only open paper position, F002-2026-10, was entered 2026-11-01 19:02 EST. Its first financing roll is 2026-11-02 17:00 EST. When this was frozen, the forward registry held **0 financing records**.

**What this does:** amends `research/USDJPY_FORWARD_TEST_PREREG.md` (v0.2, sha256 `763f8dc3…`) as already amended by v0.3 (sha256 `cf1b03cc…`). Both stay unchanged and pinned.

**What it changes:** only how financing **rate inputs** are resolved when they are late, stale or missing. Unchanged:
- every rule parameter (F001, F002), signals, entries, exits, levels and entry windows;
- sizing, costs (0.015%/0.030% one-way), the admin fees (1.00%/1.50% a year), and day counts (USD ACT/360, JPY ACT/365);
- the 17:00 ET roll, triple on Wednesday;
- baselines, metrics, minimum samples, and the success, failure and stop rules;
- forward N = 2, historical N = 142. Trial IDs stay F001/F002: no parameter or signal changes.

**Why:** an audit on 2026-11-01 (`reports/forward_reliability_2026-10-30.md`, "Financing audit") found that the code booked a missing rate as 0%. That contradicts v0.2 §4, so it is corrected as a **compliance fix**. It also found that v0.2's rule "a missing rate input uses the last known value, flagged STALE" sets **no age limit**: a months-old observation could stay in use indefinitely. This amendment adds the limit.

## 1. Rate definitions (canonical; clarifies v0.2 §4)

| Leg | Series | Meaning |
|---|---|---|
| USD | FRED **DTB3** | 3-month T-bill, secondary market, discount basis, % per year. Unchanged from v0.2 |
| JPY | FRED **IRSTCI01JPM156N** | OECD MEI "immediate rates: call money/interbank" for Japan, a **monthly average** of the overnight call rate, dated the 1st of the month, % per year |

The JPY series is the reading of v0.2's "BoJ Time-Series API **or FRED mirror**" that the system has used since activation. It is now named explicitly. The BoJ's daily uncollateralized overnight call rate would be a closer proxy; it is a **separate later proposal, not part of v0.4**.

Neither series is a broker financing rate. Booked financing remains the pre-registered **proxy model, estimated and unverified**.

## 2. Resolving each roll

1. **Which observation:** each 17:00 ET roll uses the latest observation **dated on or before the roll's New York date** that the system had fetched by the time it booked the roll. It is never a later-dated observation. Its **original observation date** is kept with it.
2. **Age at the roll:**
   - **DTB3**, in US business days (Fed Board holidays excluded): **VALID ≤ 3**; **carried forward 4–5** (booked, flagged CARRIED_FORWARD); **UNRESOLVED > 5**.
   - **IRSTCI01JPM156N**, in calendar days from its 1st-of-month date: **VALID ≤ 95**; **carried forward 96–125**; **UNRESOLVED > 125**.
3. **Values:** a published 0% is valid (VALID_ZERO); negative rates are valid. A value that isn't a finite number within −5% … +25% a year, or is dated in the future, is rejected. **A missing or rejected rate is never 0%.**
4. **UNRESOLVED roll:** if either leg is UNRESOLVED (too old, or no observation at all), **nothing is booked** for that roll. It is recorded as `financing_unresolved`, with the position legs at the roll, the missing source and the reason.
5. **TRUE-UP:** when acceptable data exists, an **appended** `financing_trueup` record books the exact amount for the **original roll date**, using the legs recorded at that roll. If the position has closed meanwhile, the amount goes to USD cash, with the JPY part converted at the recorded mid. The UNRESOLVED record is never edited.
6. **Reporting:** the v0.2 requirement to report results with and without financing stays in force. Scorer baselines use the same per-roll rates as the ledger. A position with an unresolved roll reports its baseline financing as UNKNOWN, never 0.

## 3. Operations (not part of the trial definition)

- **Fetching:** failed fetches are never cached as values; there is at most one retry per 15 minutes after a failure.
- **Readiness:** a late, stale or unavailable financing input makes the system **DEGRADED**, never BLOCKED.
- **Reconciliation:** the parity replay uses the same per-roll rates as the ledger. It is deferred, not failed, while an UNRESOLVED roll awaits its TRUE-UP; the exact recomputation still runs.
- **Rollback:** a `live_usdjpy.financing.policy: legacy` setting exists for rollback only.
