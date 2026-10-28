"""Official economic event monitor (Phase C): READ-ONLY, plain Python, no LLM calls, no signals, no orders.

Writes only live/events/ (git-ignored): events.json (one record per event_id), changes.jsonl (every change, append-only),
cache/ (official pages; schedules are re-fetched at most every 6 hours) and latest.md. Each poll makes about a dozen
polite requests (1 s apart) to official sites: run it a few times a day at most.

Sources (official only):
  Federal Reserve   monthly calendars /newsevents/YYYY-month.htm (FOMC statement, press conference, minutes, with
                    times) and the monetary-policy press feed (publication detection; statement text)
  BEA               release schedule (GDP; Personal Income and Outlays incl. PCE), times 8:30 AM ET
  Bank of Japan     MPM schedule (dates only: no statement time is published) and the What's New feed (detection)
  ONS               release calendar (CPI, monthly GDP, labour market), times UK
  Japan MoF         latest foreign-exchange intervention releases (monthly, quarterly)
  BLS               release calendar (iCalendar) and release feeds, identified per BLS robot policy with the contact
                    address from env var BLS_CONTACT_EMAIL (user approval 2026-10-28; never written anywhere);
                    reported BLOCKED while the variable is unset
  Bank of England   BLOCKED: the page refuses automated clients. No unofficial calendar is substituted.
Statuses: SCHEDULED; PUBLISHED (confirmed by an official feed or page); PAST_UNCONFIRMED (time passed, no official
confirmation source); a change of schedule is logged, never silently overwritten.
Usage: .venv/bin/python tools/events.py poll
"""
import hashlib
import json
import os
import sys
import time as _t
import warnings
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from src import PROJECT_ROOT
from src import events as E

OUT = PROJECT_ROOT / "live" / "events"
CACHE = OUT / "cache"
SCHEDULE_TTL_S = 6 * 3600
FED_MONTH = "https://www.federalreserve.gov/newsevents/%d-%s.htm"
FED_FEED = "https://www.federalreserve.gov/feeds/press_monetary.xml"
BEA = "https://www.bea.gov/news/schedule"
BOJ_SCHED = "https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm"
BOJ_FEED = "https://www.boj.or.jp/en/rss/whatsnew.xml"
ONS = "https://www.ons.gov.uk/releasecalendar?release-type=type-%s&keywords=%s"
MOF = "https://www.mof.go.jp/english/policy/international_policy/reference/feio/index.html"
BLS_ICS = "https://www.bls.gov/schedule/news_release/bls.ics"
BLS_FEEDS = {"EMPSIT": "https://www.bls.gov/feed/empsit.rss", "CPI": "https://www.bls.gov/feed/cpi.rss",
             "PPI": "https://www.bls.gov/feed/ppi.rss", "JOLTS": "https://www.bls.gov/feed/jolts.rss",
             "ECI": "https://www.bls.gov/feed/eci.rss"}
YAHOO = {"usdjpy": ("JPY=X", 0.01), "gbpusd": ("GBPUSD=X", 1e-4), "gold": ("GC=F", None)}
BLOCKED = {"Bank of England (MPC dates, Bank Rate)": "the BoE page returned 403 Access Denied to an automated client "
           "(2026-10-28). Not polled; no browser disguise."}


def _guard(p):
    p = Path(p).resolve()
    if not str(p).startswith(str(OUT.resolve())):
        raise RuntimeError("events monitor may write only live/events/: %s" % p)
    return p


def _headers(url):
    """BLS only (user approval 2026-10-28, BLS robot policy): identify the program with the contact address from the
    environment variable BLS_CONTACT_EMAIL. The address is never written anywhere: not to the cache, logs, status
    texts, reports or config. Every other host gets the standard python-requests agent."""
    host = requests.utils.urlparse(url).hostname or ""
    if host == "bls.gov" or host.endswith(".bls.gov"):
        contact = os.environ.get("BLS_CONTACT_EMAIL", "").strip()
        if not contact:
            raise RuntimeError("BLS_CONTACT_EMAIL not set")
        return {"User-Agent": "trading-research personal read-only monitor (contact: %s)" % contact}
    return {}


def get(url, ttl=None):
    """Fetch an official page; with ttl, reuse the cached copy if it is younger than ttl seconds."""
    _guard(CACHE).mkdir(parents=True, exist_ok=True)
    f = _guard(CACHE / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".txt"))
    meta = f.with_suffix(".json")
    if ttl and f.exists() and meta.exists():
        m = json.loads(meta.read_text())
        if _t.time() - m["fetched"] < ttl:
            return f.read_text(), m
    _t.sleep(1)
    try:
        r = requests.get(url, headers=_headers(url), timeout=30)
    except requests.RequestException as ex:                 # message only; never the request headers
        raise RuntimeError(type(ex).__name__) from None
    if r.status_code != 200:
        raise RuntimeError("HTTP %d" % r.status_code)
    ctype = r.headers.get("Content-Type", "")
    text = r.content.decode(r.encoding if "charset" in ctype.lower() else "utf-8", errors="replace")
    m = {"url": url, "fetched": _t.time(), "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "last_modified": r.headers.get("Last-Modified")}
    f.write_text(text)
    meta.write_text(json.dumps(m))
    return text, m


def load():
    p = OUT / "events.json"
    return json.loads(p.read_text()) if p.exists() else {"events": {}, "mof_intervention": {}, "sources": {}}


def log_change(kind, event_id, detail, now):
    with open(_guard(OUT / "changes.jsonl"), "a") as fh:
        fh.write(json.dumps({"at_utc": now.isoformat(timespec="seconds"), "kind": kind, "event_id": event_id,
                             "detail": detail}, default=str) + "\n")


SCHED_FIELDS = ("scheduled_date", "scheduled_time_utc", "title")


def merge(store, new, now):
    for e in new:
        old = store["events"].get(e["event_id"])
        if old is None:
            store["events"][e["event_id"]] = e
            log_change("added", e["event_id"], {k: e[k] for k in SCHED_FIELDS}, now)
            continue
        diff = {k: (old[k], e[k]) for k in SCHED_FIELDS if old[k] != e[k]}
        if diff:
            log_change("schedule changed", e["event_id"], diff, now)
            for k in SCHED_FIELDS + ("scheduled_time_local", "schedule_note"):
                old[k] = e[k]
        if e.get("ons_status") and old.get("ons_status") != e["ons_status"]:
            log_change("ons status", e["event_id"], (old.get("ons_status"), e["ons_status"]), now)
            old["ons_status"] = e["ons_status"]


def mark_published(store, eid, published_utc, url, now, facts=None):
    e = store["events"].get(eid)
    if e is None or e["status"] == "PUBLISHED":
        return False
    e["status"] = "PUBLISHED"
    e["published_time_source"] = published_utc.isoformat() if published_utc else None
    e["detected_time_utc"] = now.isoformat(timespec="seconds")
    started = datetime.fromisoformat(store.setdefault("monitoring_started_utc", now.isoformat(timespec="seconds")))
    if published_utc and published_utc < started:
        e["detection_note"] = "published before monitoring began (%s); no detection delay is measured" % started.isoformat()
    elif e["scheduled_time_utc"]:
        e["detection_delay_s"] = round((now - datetime.fromisoformat(e["scheduled_time_utc"])).total_seconds())
    e["publication_url"] = url
    if facts:
        e["facts"] = facts
    e["reliability"] = "official schedule; publication confirmed by an official feed"
    log_change("published", eid, {"published": e["published_time_source"], "url": url}, now)
    return True


def collect(store, now):
    store["sources"] = {}                       # rebuilt every poll: no stale statuses
    st = store["sources"]
    new = []
    ny_today = now.astimezone(E.NY).date()
    months = [(ny_today.year + (ny_today.month - 1 + k) // 12, (ny_today.month - 1 + k) % 12 + 1) for k in range(3)]
    for y, m in months:
        name = list(E.MONTHS)[m - 1]
        try:
            txt, meta = get(FED_MONTH % (y, name), SCHEDULE_TTL_S)
            new += E.parse_fed_month(E.flatten(txt), y, m, FED_MONTH % (y, name))
            st["Fed calendar %d-%02d" % (y, m)] = "OK (%s)" % meta["fetched_utc"]
        except Exception as ex:
            st["Fed calendar %d-%02d" % (y, m)] = "FAILED: %s" % ex
    for label, fn in (("BEA schedule", lambda: E.parse_bea(get(BEA, SCHEDULE_TTL_S)[0], ny_today.year, BEA)),
                      ("BoJ MPM schedule", lambda: E.parse_boj_schedule(E.flatten(get(BOJ_SCHED, SCHEDULE_TTL_S)[0]),
                                                                       ny_today.year, BOJ_SCHED))):
        try:
            got = fn()
            new += got
            st[label] = "OK (%d events)" % len(got)
        except Exception as ex:
            st[label] = "FAILED: %s" % ex
    for kw in ("consumer price inflation", "gdp monthly estimate", "labour market overview"):
        for typ in ("upcoming", "published"):
            url = ONS % (typ, kw.replace(" ", "%20"))
            try:
                got = E.parse_ons(get(url, SCHEDULE_TTL_S if typ == "upcoming" else 1800)[0], url)
                if typ == "upcoming":
                    new += got
                else:
                    for e in got:
                        if e["ons_status"] == "Published":
                            if e["event_id"] not in store["events"]:
                                new.append(e)
                st["ONS %s (%s)" % (kw, typ)] = "OK (%d)" % len(got)
            except Exception as ex:
                st["ONS %s (%s)" % (kw, typ)] = "FAILED: %s" % ex
    try:
        got = E.parse_bls_ics(get(BLS_ICS, SCHEDULE_TTL_S)[0], BLS_ICS)
        new += got
        st["BLS release calendar (iCalendar)"] = "OK (%d events)" % len(got)
    except Exception as ex:
        st["BLS release calendar (iCalendar)"] = "BLOCKED: %s" % ex if "BLS_CONTACT_EMAIL" in str(ex) else "FAILED: %s" % ex
    merge(store, new, now)
    # BLS publication: an item in the release's official feed dated on the scheduled New York date
    if "OK" in st.get("BLS release calendar (iCalendar)", ""):
        for kind, feed in BLS_FEEDS.items():
            try:
                items = E.parse_atom(get(feed)[0])                     # BLS feeds are Atom
                st["BLS feed %s" % kind] = "OK (%d entries)" % len(items)
                for it in items:
                    if not it["published_utc"]:
                        continue
                    d = it["published_utc"].astimezone(E.NY).date()
                    eid = "US-BLS-%s-%s" % (kind, d)
                    e = store["events"].get(eid)
                    if e is None:
                        continue
                    # BLS feed entries are stamped before the official release time (e.g. 07:51 for an 08:30
                    # release), so the official scheduled time is recorded as the release time.
                    rel = datetime.fromisoformat(e["scheduled_time_utc"]) if e["scheduled_time_utc"] else it["published_utc"]
                    mark_published(store, eid, rel, it["link"], now,
                                   [{"fact": "BLS headline: %s" % it["title"], "source": it["link"]},
                                    {"feed_entry_timestamp_utc": it["published_utc"].isoformat(),
                                     "note": "feed timestamp, not the release time"}])
            except Exception as ex:
                st["BLS feed %s" % kind] = "FAILED: %s" % ex
    # ONS publication: the calendar itself marks a release Published at its stated time
    for typ in ("published",):
        for kw in ("consumer price inflation", "gdp monthly estimate", "labour market overview"):
            try:
                for e in E.parse_ons(get(ONS % (typ, kw.replace(" ", "%20")), 1800)[0], ""):
                    if e["ons_status"] == "Published":
                        mark_published(store, e["event_id"], datetime.fromisoformat(e["scheduled_time_utc"]),
                                       "https://www.ons.gov.uk/releasecalendar", now)
            except Exception:
                pass
    # Fed feed: statements and minutes
    try:
        items = E.parse_fed_feed(get(FED_FEED)[0])
        st["Fed monetary-policy feed"] = "OK (%d items)" % len(items)
        for it in items:
            if not it["date"]:
                continue
            if it["title"] == "Federal Reserve issues FOMC statement":
                eid = "US-FED-FOMC_STATEMENT-%s" % it["date"]
                if eid not in store["events"]:            # an earlier statement, known only from the official feed
                    e = E.event(eid, "Federal Reserve", FED_FEED, "US", "central bank decision", "FOMC statement",
                                it["published_utc"].astimezone(E.NY), "America/New_York",
                                "added after the fact from the Fed's press feed (publication time used as schedule)")
                    store["events"][eid] = e
                    log_change("added from feed (past)", eid, None, now)
                if store["events"][eid]["status"] != "PUBLISHED":
                    facts = []
                    try:
                        s = E.fomc_target_sentence(get(it["link"], 86400)[0])
                        rng = E.target_range(s)
                        facts = [{"fact": s, "source": it["link"]}] + ([{"target_range_percent": list(rng)}] if rng else [])
                    except Exception as ex:
                        facts = [{"fact": None, "error": "statement not read: %s" % ex}]
                    mark_published(store, eid, it["published_utc"], it["link"], now, facts)
            elif it["title"].startswith("Minutes of the Federal Open Market Committee"):
                mark_published(store, "US-FED-FOMC_MINUTES-%s" % it["date"], it["published_utc"], it["link"], now)
    except Exception as ex:
        st["Fed monetary-policy feed"] = "FAILED: %s" % ex
    # BoJ feed: policy statements
    try:
        items = E.parse_boj_feed(get(BOJ_FEED)[0])
        st["BoJ What's New feed"] = "OK (%d items)" % len(items)
        for it in items:
            if "Statement on Monetary Policy" in it["title"] and it["published_utc"]:
                d = it["published_utc"].astimezone(E.TOKYO).date()
                mark_published(store, "JP-BOJ-MPM_STATEMENT-%s" % d, it["published_utc"], it["link"], now,
                               [{"fact": "BoJ published: %s" % it["title"], "source": it["link"]}])
    except Exception as ex:
        st["BoJ What's New feed"] = "FAILED: %s" % ex
    # MoF intervention releases
    try:
        mof = E.parse_mof(E.flatten(get(MOF, SCHEDULE_TTL_S)[0]), MOF)
        if mof != store.get("mof_intervention"):
            log_change("mof releases", "JP-MOF-INTERVENTION", mof, now)
        store["mof_intervention"] = mof
        st["MoF intervention page"] = "OK" if mof else "FAILED: layout not recognised"
    except Exception as ex:
        st["MoF intervention page"] = "FAILED: %s" % ex
    for k, v in BLOCKED.items():
        st[k] = "BLOCKED: " + v
    # previous result and past-unconfirmed status
    stmts = sorted([e for e in store["events"].values() if e["event_id"].startswith("US-FED-FOMC_STATEMENT")],
                   key=lambda e: e["scheduled_date"])
    for a, b in zip(stmts, stmts[1:]):
        rng = [f["target_range_percent"] for f in a["facts"] if "target_range_percent" in f]
        if rng and b["previous"] is None:
            b["previous"] = {"target_range_percent": rng[0], "from_event": a["event_id"]}
    for e in store["events"].values():
        if e["status"] != "SCHEDULED":
            continue
        if e["scheduled_time_utc"]:
            past = now > datetime.fromisoformat(e["scheduled_time_utc"]) + timedelta(hours=1)
        else:                                   # date only (BoJ): past once that local date has ended
            tz = E.TOKYO if e["time_zone"] == "Asia/Tokyo" else E.NY
            past = now.astimezone(tz).date() > date.fromisoformat(e["scheduled_date"])
        if past:
            e["status"] = "PAST_UNCONFIRMED"
            log_change("past, not confirmed by an official feed this monitor reads", e["event_id"], None, now)


def reactions(store, now):
    """Indicative reactions for events published in the last 7 days (Yahoo keeps 1-minute history about 7 days)."""
    import yfinance as yf
    cand = [e for e in store["events"].values() if e["status"] == "PUBLISHED" and
            (e.get("published_time_source") or e.get("scheduled_time_utc")) and
            now - datetime.fromisoformat(e.get("published_time_source") or e["scheduled_time_utc"]) < timedelta(days=7)
            and any(r.get("status") != "COMPLETE" for r in e["market_reaction"].values()) | (not e["market_reaction"])]
    if not cand:
        return
    bars = {}
    for mk, (sym, _) in YAHOO.items():
        try:
            h = yf.Ticker(sym).history(period="7d", interval="1m")
            bars[mk] = h["Close"].tz_convert("UTC") if len(h) else None
        except Exception:
            bars[mk] = None
    for e in cand:
        t0 = datetime.fromisoformat(e.get("published_time_source") or e["scheduled_time_utc"])
        for mk in e["markets_affected"]:
            sym, pip = YAHOO[mk]
            r = E.reaction(bars.get(mk), t0, now, pip)
            r["instrument"] = sym + (" (COMEX futures, context)" if mk == "gold" else " (indicative)")
            e["market_reaction"][mk] = r


def report(store, now):
    ev = list(store["events"].values())
    L = ["# Official economic events (read-only monitor; no signal)\n",
         "Generated %s UTC (%s New York). Plain Python; official sources only; nothing interpreted.\n" % (
             now.strftime("%Y-%m-%d %H:%M"), now.astimezone(E.NY).strftime("%a %H:%M")),
         "**Validated strategy eligible to act on any event: NONE** (140 trials killed by pre-registered rules; 2 "
         "(V119, V122) passed Study 3's primary rule but failed all robustness checks; none judged robust).\n",
         "## Sources\n", "| Source | Status |", "|---|---|"]
    L += ["| %s | %s |" % (k, v) for k, v in sorted(store["sources"].items())]
    L += ["\n## Next 14 days\n", "| When (New York) | When (UTC) | Event | Source | Markets |", "|---|---|---|---|---|"]
    for e in E.upcoming(ev, now, 14):
        tny = datetime.fromisoformat(e["scheduled_time_utc"]).astimezone(E.NY).strftime("%a %m-%d %H:%M") \
            if e["scheduled_time_utc"] else "%s (date only; time not published)" % e["scheduled_date"]
        L.append("| %s | %s | %s | %s | %s |" % (tny, (e["scheduled_time_utc"] or "—")[:16].replace("T", " "), e["title"],
                                               e["source"], ", ".join(e["markets_affected"])))
    L += ["\n## Last 7 days\n", "| Event | Status | Published (source time, UTC) | Detected | Facts | Reaction (indicative, not attributed) |",
          "|---|---|---|---|---|---|"]
    recent = [e for e in ev if e["scheduled_date"] >= (now - timedelta(days=7)).date().isoformat()
              and e["scheduled_date"] <= now.date().isoformat()]
    for e in sorted(recent, key=lambda e: e["scheduled_date"]):
        facts = "; ".join(str(f.get("target_range_percent") or f.get("fact") or f.get("error"))[:160] for f in e["facts"]) or "—"
        rx = "; ".join("%s %s%s" % (mk, r.get("status"), (" init %+.1f bp, then %+.1f bp" % (r.get("initial_bp", float("nan")),
                       r.get("subsequent_bp", float("nan")))) if "initial_bp" in r else "") for mk, r in e["market_reaction"].items()) or "—"
        L.append("| %s | %s | %s | %s | %s | %s |" % (e["title"], e["status"], (e["published_time_source"] or "—")[:16].replace("T", " "),
                                                      (e["detected_time_utc"] or "—")[:16].replace("T", " "), facts, rx))
    mof = store.get("mof_intervention") or {}
    L += ["\n## Japan MoF intervention releases (verified interventions come only from these)\n"]
    L += ["- %s: period %s, published %s." % (k, v["period"], v["published"]) for k, v in mof.items()] or ["- not available"]
    L += ["\n## Limits\n", "- Expected outcomes and surprises: not available (no licensed consensus source).",
          "- Detection delay depends on when this monitor runs; it is not real time.",
          "- BEA releases have no official feed here: past ones show PAST_UNCONFIRMED until a confirmation source is added."]
    md = "\n".join(L) + "\n"
    _guard(OUT / "latest.md").write_text(md)
    return md


def poll():
    now = datetime.now(timezone.utc)
    _guard(OUT).mkdir(parents=True, exist_ok=True)
    store = load()
    store.setdefault("monitoring_started_utc", now.isoformat(timespec="seconds"))
    collect(store, now)
    reactions(store, now)
    store["generated_utc"] = now.isoformat(timespec="seconds")
    _guard(OUT / "events.json").write_text(json.dumps(store, indent=1, default=str))
    print(report(store, now))


if __name__ == "__main__":
    if (sys.argv[1:] or [""])[0] == "poll":
        poll()
    else:
        sys.exit(__doc__)
