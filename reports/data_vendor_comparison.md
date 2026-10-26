# Historical market data: vendor comparison and acquisition plan (Priority 2)

_Research only, 2026-10-26. Nothing was downloaded, bought or registered. The only fetch was gov.uk's bank-holiday file, about 22 KB, used to check the clock in Priority 1._

**How each fact was checked:**
- **V:** read on the vendor's own page today.
- **T:** third-party only (a tool's documentation, a forum or a reseller).
- **?:** not found.

License statements are my reading of public text, not legal advice. Wherever the terms are unclear, the plan asks the vendor or you before any download.

## 1. What our research needs (the yardstick)

1. **Intraday bid and ask** to measure spreads by hour, session and around releases. Mid prices alone can't measure costs.
2. **Timestamps with a known zone,** checkable against known events. The test is that the US 08:30 ET release spike lands at 08:30 ET in both EST and EDT months.
3. **At least two independent sources** per market, so vendor artefacts aren't mistaken for market behaviour.
4. **Permission to store the data locally for private research and to publish aggregate results.** The data itself stays private, as data/ always has.
5. **Pre-2024 only.** The 2024+ holdout stays locked, so yearly files from 2024 onward are never downloaded.

## 2. Free and low-cost intraday sources

### Dukascopy (Swiss bank; prices from its own SWFX marketplace)

| Item | Finding |
|---|---|
| Cost | Free (V) |
| License: store and research? | **Unclear to restrictive** (V, Terms of Use, Dukascopy Bank SA). Downloads are licensed "ONLY for your own personal, non-commercial use", and the site's information "may not be used to construct a database of any kind". No separate data licence was found. |
| License: publish results? | Not addressed. The terms forbid publishing "the analysis and presentation included in the WEBSITE" (theirs, not ours). Our own aggregate statistics are probably fine, but that is unconfirmed. |
| History | Ticks from 2003-05-04 (USD/JPY, GBP/USD) and 2003-05-05 (XAU/USD); daily bars from 1986 (FX) and 1999 (gold) (T, dukascopy-node metadata) |
| Granularity | Tick to monthly (V) |
| Bid/ask | Yes, in the tick files (T) |
| Timestamp zone | UTC (T) |
| Known issues | Single-venue quotes; anecdotal gaps and spikes (T, vendor forums); no independent quality study found |
| Login | The web export says free, login requirement not stated; the JForex route needs a demo login (V) |

### HistData.com (source of quotes not disclosed)

| Item | Finding |
|---|---|
| Cost | Free; FTP access and automatic updates paid (V) |
| License: store and research? | No restrictions stated: "Use the data at your own will and risk"; no warranty (V) |
| License: publish results? | Not addressed (V) |
| History | USD/JPY tick and 1-minute data from 2000 (V); XAU/USD tick data from 2009 (V); GBP/USD listed (V), start year not checked |
| Granularity | Tick ("1 Second Bar") and 1-minute only (V) |
| Bid/ask | **Ask only in the tick files;** 1-minute bars are bid only (V) |
| Timestamp zone | "EST … WITHOUT Day Light Savings", i.e. fixed UTC−5 (V). We must convert; never treat it as New York time. |
| Known issues | Undisclosed source; volume removed; whole-second timestamps with many duplicates in some months (T); gap statistics published per file (V) |
| Login | Not needed for the per-year downloads (V) |

### TrueFX (Integral)

| Item | Finding |
|---|---|
| Cost | Historical downloads "at zero cost" (V). Real-time plans cost $4,950–7,450/month (V) and aren't needed. |
| License: store and research? | **Not found** (V: no terms page beyond the privacy policy). The FAQ lists "historic back-testing" as a client use (V). |
| License: publish results? | Not found |
| History | Since May 2009 (T) |
| Granularity | Tick, millisecond (V) |
| Bid/ask | Top of book, bid and offer (V) |
| Timestamp zone | ? (believed GMT; unverified) |
| Known issues | "Indicative, not executable" (V); sourced from Integral OCX, a multi-bank network (V); 15 pairs incl. USD/JPY and GBP/USD (T, 2012 list); **no gold found** |
| Login | **Free registration required** (V). I may not create accounts: you would register. |

### FXCM public repository

| Item | Finding |
|---|---|
| Cost | Free (V) |
| License | "for personal use and abides by our EULA" (V); EULA not read |
| History | Candles 2017–2020 only; ticks on email request (V) |
| Granularity | 1-minute, hourly, daily candles (V) |
| Bid/ask | Not stated for candles (V) |
| Timestamp zone | UTC (V) |
| Known issues | **Too short**; "indicative"; **no XAU/USD candles** (V) |
| Login | No |

### OANDA v20 API

| Item | Finding |
|---|---|
| Cost | Free with an account (practice accounts exist) |
| License | **Not found** (T only) |
| History | From 2005 (V, OANDA page) |
| Granularity | 5-second to monthly candles (V) |
| Bid/ask | Bid, ask and mid candles (T) |
| Timestamp zone | UTC (T) |
| Known issues | Broker's own quotes; you would need an account and API token, and rule 1 forbids me handling tokens |
| Login | **Account and token required** |

### FirstRate Data

| Item | Finding |
|---|---|
| Cost | One-off purchase (price not checked) plus $99.95/yr for updates (T) |
| License | "Perpetual licence", terms not read (T) |
| History | USD/JPY and GBP/USD from 2010 (T); gold not found |
| Granularity | 1-minute to daily (T) |
| Bid/ask | **Not confirmed**: their own page marks the price basis "to confirm" (T) |
| Timestamp zone | ? |
| Known issues | Bid/ask basis unknown, so cost questions can't be answered |
| Login | Purchase |

### Databento, CME Globex futures (6J = JPY, 6B = GBP, GC = gold)

| Item | Finding |
|---|---|
| Cost | Pay as you go, per GB, "from $0.50/GB" (T); **$125 free credits** for new accounts, expiring after 6 months (V); Standard plan $199/month (V) |
| License | Personal and commercial use are separate licence lines; redistribution depends on the dataset (V). Storage is not addressed (V). |
| History | CME Globex MDP 3.0 from 2010 (T) |
| Granularity | Trades, top of book (MBP-1), depth, 1-minute OHLCV |
| Bid/ask | **Yes:** real executable exchange quotes |
| Timestamp zone | UTC, nanosecond, from direct capture (T) |
| Known issues | Futures, not spot: basis, rolls and contract months to handle; Globex only (no interbank spot); an account is needed (you) |
| Login | Account required |

## 3. Institutional sources (reference; prices not published)

| Source | What it adds | Cost | Assessment |
|---|---|---|---|
| EBS historical data (via CME DataMine) | The main interbank venue for USD/JPY; used in the academic announcement literature | Quote on request (V: "varies based upon data type and duration") | Best quality for USD/JPY; out of budget for a $100 account |
| LSEG Tick History (Refinitiv) | Quotes from 1996 across contributors (T) | Quote; sometimes via a university's WRDS subscription (T) | Out of reach without institutional access |
| Bloomberg | Ticks and an economic calendar with consensus forecasts | Terminal subscription | Out of budget |
| LBMA Gold Price (ICE Benchmark Administration) | The official daily gold benchmark | **Licence required even for historical data** (T); WGC removed its free history at IBA's request in 2025 (T) | Don't use without a licence; our daily gold stays GLD and the World Bank series |

## 4. Economic calendar and point-in-time macro data

| Source | Cost | Store and research? | Publish results? | History | Granularity and timing | Known issues | Login |
|---|---|---|---|---|---|---|---|
| FRED / ALFRED API (US vintages) | Free | Yes for own personal use; third-party copyrighted series need the owner's permission for other uses (V) | Attribution notice required; copyrighted series flagged in notes (V) | Decades | Vintage = **date only**, no release time | No consensus forecasts; key is personal (V) | Free key (your FRED_API_KEY; rule 1 amendment) |
| Official release calendars (BLS, BEA, Federal Reserve, BoE MPC, BoJ MPM, ONS, Japan Cabinet Office / e-Stat) | Free | Yes (public information) | Yes | Varies: years of archived schedules, not one file | Scheduled **time of day** published (e.g. 08:30 ET for most US releases) | Historical schedules must be assembled and checked; exceptions occur (e.g. releases delayed by the October 2013 government shutdown) | No |
| OECD MEI Original Release and Revisions database | Free | Yes (OECD terms, not read in full) | Yes with citation | Since about 1999 (to verify) | Monthly or quarterly vintages, no times | Coverage per country to verify | No |
| Bank of England database | Free | Personal and internal non-commercial use allowed; specific re-use terms (V, partly read) | To check | Long | Daily or monthly | — | No |
| FXMacroData | Free tier: USD only, last 90 days; paid about $25–50/month (T, conflicting) | ? | ? | "Full history" claimed (T) | `announced_at` publication timestamps (T) | Young third-party vendor; **no consensus field found**; quality unverified | Key |
| Trading Economics API | Quote on request (V) | Single-user plan: no sharing (V) | ? | Long | Calendar with actual, consensus and previous (V) | Consensus definition is theirs; cost unknown | Account |
| ForexFactory / Investing.com calendars | Free to view | Terms not checked; scraping not planned | — | — | — | Not used | — |

**Gap:** no free source gives historical **consensus forecasts**, and announcement "surprise" studies need them. Free alternatives such as actual minus prior, or model-based expectations, are weaker. Decide this when a specific announcement hypothesis exists.

## 5. Quality tests (every source must pass before any research use)

| # | Test | Pass rule |
|---|---|---|
| Q1 | **License gate** | Written terms, or the vendor's or your written OK, allow local storage for private research and publication of aggregate results |
| Q2 | **Time-zone proof** | 1-minute absolute returns peak at 08:30 ET on US payroll Fridays in ≥ 90% of releases, in both EST and EDT months, after our conversion |
| Q3 | **Daily anchor** | Mid at 12:00 ET vs the FRED H.10 noon rate: median absolute difference ≤ 3 pips (USD/JPY, GBP/USD); for gold, vs the GC front-month settlement, accounting for basis |
| Q4 | **Cross-vendor agreement** | 1-minute mids, liquid hours: median absolute difference ≤ 0.5 pip (FX) and ≤ $0.30 (gold); 1-minute return correlation ≥ 0.95 |
| Q5 | **Bid/ask sanity** | Ask > bid everywhere; zero or negative spreads < 0.01% of ticks; spreads > 20× the hourly median listed and inspected |
| Q6 | **Coverage** | Per year: share of FX-open minutes with ≥ 1 quote ≥ 99% in London and New York hours, reported separately for Tokyo hours; gaps > 5 minutes listed |
| Q7 | **Weekend and holiday structure** | No quotes between Friday 17:00 and Sunday 17:00 ET beyond the vendor's documented convention; thin holidays match `src/clock` |
| Q8 | **Stale and outlier ticks** | Runs of unchanged quotes > 2 minutes in liquid hours listed; 1-minute moves > 10σ kept only if the second vendor confirms them |
| Q9 | **Reproducibility** | Raw files are immutable with SHA-256 in a manifest; everything is truncated before 2024 on arrival; the cleaning rules are code |

## 6. Recommendation

**Is any free source good enough? Partly.** Free sources are indicative quotes from single venues, not the interbank market (EBS or LSEG):
- **Session, hour, day-of-week and volatility patterns:** free sources can be good enough *if two independent ones agree* (Q4).
- **Executable costs:** no free source shows what a given retail broker would charge. Cost conclusions would need that broker's own data or an exchange source such as Databento.

**Cheapest combination expected to pass, in order:**

| Market | Primary | Cross-check | Why |
|---|---|---|---|
| USD/JPY | HistData ticks (bid and ask, 2000+, permissive wording, no login) | TrueFX (2009+, multi-bank Integral; needs your free registration and its terms) | Free; two independent sources |
| GBP/USD | Same as USD/JPY | Same | Same |
| Gold | HistData XAU/USD ticks (2009+) | Databento GC 1-minute OHLCV plus a sample of MBP-1 inside the $125 free credits (needs your account) | TrueFX and FXCM have no gold; the exchange anchors timestamps and spreads |

**Dukascopy:** the longest and cleanest-looking free source (2003+, UTC, bid and ask, all three markets), but its terms forbid building "a database of any kind". I recommend it only if Dukascopy confirms in writing that private research storage is allowed. You would need to ask them; I can draft the email.

## 7. Limited acquisition plan (each step needs your approval)

| Step | What | Size or cost | Gate |
|---|---|---|---|
| A0 | Licence check: you read the TrueFX terms at registration; optionally ask Dukascopy and HistData by email | $0 | Q1 |
| A1 | **Pilot:** HistData USD/JPY ticks for 2019 only (one year) | One yearly zip, size to be checked on the page before download | Run Q2–Q9 on one year; report |
| A2 | If A1 passes: TrueFX USD/JPY for 2019 (monthly files, after your registration) | 12 files | Q4 cross-vendor |
| A3 | Extend to 2009–2023 for USD/JPY and GBP/USD, then XAU/USD | Sizes listed before download | All tests |
| A4 | Optional: Databento GC and 6J 1-minute for 2019 within the free credits | ≤ $125 credit, $0 cash | Exchange anchor for gold and USD/JPY |
| A5 | Calendar: assemble official US release times (payrolls, CPI, FOMC) 2009–2023 from the official archives; ALFRED vintages via your key | $0 | Spot-checked against Q2 spikes |

**Rules for every step:**
- No paid service.
- No installs: CSV parsing with pandas is already available; Databento would use plain HTTPS rather than its package, or ask first.
- Nothing from 2024 onward.
- Every file hashed and logged.
