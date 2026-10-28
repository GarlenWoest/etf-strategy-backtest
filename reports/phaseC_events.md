# Phase C: official economic event monitoring (2026-10-28)

_Plain Python, no LLM calls, no signals, no orders. Code: `src/events.py` (parsers, record schema, reaction windows) and `tools/events.py poll`. Output: `live/events/` (private): `events.json`, `changes.jsonl` (append-only), `cache/`, `latest.md`. Tests: `tests/test_events.py` (10, on short fixtures copied from the official pages). Development runs before 18:11 UTC were discarded; monitoring officially began **2026-10-28 18:11:37 UTC**._

## 1. Sources and coverage

| Market / body | Official source read | What it provides | Status |
|---|---|---|---|
| Federal Reserve (US) | Monthly calendars `/newsevents/YYYY-month.htm`; monetary-policy press feed; statement pages | FOMC statement, press conference and minutes with times; publication time; the target-range sentence verbatim | **OK** |
| BEA (US) | Release schedule | GDP and Personal Income and Outlays (incl. PCE), with times | **OK** (schedule only; no official feed read, so past releases read PAST_UNCONFIRMED) |
| BLS (US) | Release calendar (iCalendar) and five Atom release feeds, identified per BLS robot policy (contact from env var `BLS_CONTACT_EMAIL`, sent to bls.gov only; found in 0 written files) | CPI, Employment Situation, PPI, JOLTS, ECI with times; publication confirmation and BLS headline | **OK since 15:4x ET.** First live poll: 102 calendar events (Jan 2025 – Dec 2026). All 55 feed entries inside the calendar span match an event on the same New York date. **Feed timestamps are not release times:** 17 of 55 are stamped 39–40 min before the official time, so the official scheduled time is recorded and the feed time kept as a separate fact. |
| Bank of Japan | MPM schedule; What's New feed | Meeting dates (**no statement time is published in advance**); publication detection | **OK** (detection depends on the feed title containing "Statement on Monetary Policy", not yet seen in a live release) |
| Japan MoF | Intervention page | Latest monthly and quarterly intervention releases | **OK.** Verified interventions come only from these releases; amounts are in linked files, not parsed. |
| ONS (UK) | Release calendar (upcoming and published) | CPI, monthly GDP and UK Labour Market, with times and Confirmed/Published status | **OK** |
| Bank of England | MPC dates page | MPC decisions | **BLOCKED:** "Access Denied" to an automated client. No browser disguise. |

**First full poll: 31 events.**
- 17 scheduled;
- 8 published, all confirmed by an official feed or page;
- 6 past but unconfirmed (BoJ meetings before the current feed window).

**A second poll changed nothing:** 31 events and 46 change-log lines both times, so it's idempotent.

## 2. Every event record holds

- **Identity:** event ID, source and URL, country, markets affected, type, title.
- **Schedule:** scheduled date, time (UTC and local, with the IANA zone) and a note on its basis. The Fed and BEA print times without a zone, so they're read as America/New_York (stated in each record).
- **Status:** SCHEDULED, PUBLISHED, or PAST_UNCONFIRMED.
- **Publication:** the source's publication time, our detection time and the detection delay. If the release came before monitoring began, no delay is claimed and a note says so.
- **Expected outcome and surprise:** always "not available: no licensed consensus source". **Nothing is fabricated.**
- **Facts:** copied from the official text. **Interpretation:** always empty; the monitor never interprets.
- **Previous result.**
- **Market reaction:** indicative price change from publication to +15 min ("initial") and +15 to +120 min ("subsequent") for each affected market. It uses Yahoo 1-minute closes and never a later bar, and it is **not attributed to the event**.

Any schedule change is logged in `changes.jsonl` and never silently overwritten (tested).

## 3. Today's FOMC decision (2026-10-28), from the official sources

- **Schedule, verified on the Fed's October 2026 calendar:** FOMC meeting October 27–28; statement at **2:00 p.m. ET (18:00 UTC)**; press conference at **2:30 p.m. ET**.
- **Publication:** in the Fed's press feed, "Federal Reserve issues FOMC statement", stamped 18:00:00 GMT, page `monetary20261028a.htm`.
  - A development poll first saw it at 18:09 UTC.
  - The kept record was created at 18:11 UTC, after the release, so no detection delay is claimed.
- **Fact (verbatim):** "The Committee decided to maintain the target range for the federal funds rate at 3-3/4 to 4 percent, in support of the Federal Reserve's dual mandate." Parsed as 3.75–4.00%.
- **Previous:** 3.75–4.00% (2026-09-16 statement, read from the same official feed).
- **Expected and surprise:** not available.
- **Market reaction:** see section 4.

## 4. Market reaction to the 10-28 statement (indicative; observed, not attributed)

Measured at the 20:01 UTC poll from Yahoo 1-minute closes. Each price is the bar ending at the window boundary; a later bar is never used.

| Market (instrument) | 14:00 → 14:15 ET ("initial") | 14:15 → 16:00 ET ("subsequent") | Status |
|---|---|---|---|
| USD/JPY (JPY=X, indicative) | +4.3 pips (+2.7 bp) | −34.8 pips (−22.0 bp) | complete |
| GBP/USD (GBPUSD=X, indicative) | +1.4 pips (+1.1 bp) | +23.9 pips (+18.0 bp) | complete |
| Gold (COMEX GC=F, context, 10-min delayed) | −16.8 bp | not yet available | INCOMPLETE: Yahoo's 10-minute delay meant the 16:00 bar didn't exist at 16:01; the next poll completes it |

**How to read this:**
- These are observed changes in indicative prices.
- The second window contains the **2:30 p.m. press conference** and any other news. **Nothing here attributes a move to the statement.**
- There is no consensus forecast, so no surprise is measured.
- No strategy is eligible to act: none has passed validation.

## 5. Upcoming, from the first poll (next 14 days)

| When (New York) | Event | Source |
|---|---|---|
| Wed 10-28 14:30 | FOMC press conference | Federal Reserve |
| Thu 10-29 08:30 | GDP (Advance Estimate), Q3 2026 | BEA |
| Thu 10-29 08:30 | Personal Income and Outlays (incl. PCE), September 2026 | BEA |
| Fri 10-30 (date only; time not published) | BoJ Monetary Policy Meeting statement (meeting Oct 29–30) | Bank of Japan |

Further out: ONS UK Labour Market on 11-17 and CPI on 11-18 (07:00 UK); FOMC minutes on 11-18 (2:00 p.m.); FOMC statement on 12-09 (2:00 p.m. EST = 19:00 UTC).

## 6. Scheduled task vs unattended monitoring

- The poll is plain Python. It only runs when something starts it: the proposed weekday-task step, a manual run, or a scheduler you approve.
- **It is not continuous or real time.** On the weekday 16:45 ET task:
  - US releases at 08:30 and FOMC at 14:00 would be detected the same afternoon (delay about 2.5–8 hours);
  - ONS 07:00 UK releases the same day;
  - BoJ statements (Tokyo daytime) the following New York afternoon;
  - nothing on weekends or US holidays.
- `latest.md` always shows when the poll ran, and every record carries its detection time and delay.

## 7. Politeness and licensing

- About 12 requests per poll, 1 second apart.
- Schedule pages are cached for 6 hours; feeds are read on each poll.
- The standard `python-requests` agent is used, with no disguise.
- Only short verbatim facts (e.g. the target-range sentence) are kept from official US government text. ONS, BoJ and MoF pages are used for dates, times and titles only.

## 8. Not done in Phase C

- BLS and BoE (blocked).
- BEA publication confirmation and released values (needs an official data API or ALFRED with your FRED key).
- Consensus forecasts (no licensed source).
- Japan CPI and other Japanese statistics.
- News monitoring.
- Any analysis, forecast or signal.
