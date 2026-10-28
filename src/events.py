"""Official economic event monitoring (Phase C, 2026-10-28): pure logic, no network. READ-ONLY monitoring, not research.

Parsers read OFFICIAL pages only (Federal Reserve, BEA, Bank of Japan, ONS, Japan Ministry of Finance). Each returns
events with the schedule exactly as published; nothing is estimated. An event record separates:
  facts           text or numbers copied from the official publication (e.g. the FOMC target-range sentence)
  interpretation  always None here: the plain-Python monitor never interprets
  expected        None unless a legitimate consensus source exists (none is licensed: "not available")
  surprise        None for the same reason
  market_reaction indicative price changes around the publication time (src.market_intel.value_at); observed, NOT
                  attributed to the event (other news can coincide)
Isolation: used only by tools/events.py, which writes only live/events/; never by research code (tests enforce it).
"""
import html as _html
import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
LONDON = ZoneInfo("Europe/London")
TOKYO = ZoneInfo("Asia/Tokyo")
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                         "september", "october", "november", "december"], 1)}
ABBR = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "aug": 8,
        "sept": 9, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
MARKETS = {"US": ["usdjpy", "gbpusd", "gold"], "JP": ["usdjpy"], "UK": ["gbpusd"]}


def flatten(html_text):
    """Visible text with cell/element boundaries as '|' (stable across whitespace changes)."""
    x = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html_text, flags=re.S | re.I)
    x = re.sub(r"<[^>]+>", "|", x)
    x = re.sub(r"\s+", " ", _html.unescape(x))
    return re.sub(r"(\| ?)+", "|", x)


def _clock(s):
    """'2:00 p.m.' / '8:30 AM' / '7:00am' -> time."""
    m = re.match(r"\s*(\d{1,2}):(\d\d)\s*([ap])\.?\s*m\.?", s, re.I)
    h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3).lower()
    return time((h % 12) + (12 if ap == "p" else 0), mi)


def event(event_id, source, url, country, etype, title, sched_local, tz, sched_note, **kw):
    """One schedule record. sched_local: aware datetime, or a date when no time is published."""
    timed = isinstance(sched_local, datetime)
    return {"event_id": event_id, "source": source, "source_url": url, "country": country,
            "markets_affected": MARKETS[country], "event_type": etype, "title": title,
            "scheduled_date": (sched_local.date() if timed else sched_local).isoformat(),
            "scheduled_time_utc": sched_local.astimezone(UTC).isoformat() if timed else None,
            "scheduled_time_local": sched_local.isoformat() if timed else None, "time_zone": tz,
            "schedule_note": sched_note, "status": "SCHEDULED", "published_time_source": None,
            "detected_time_utc": None, "detection_delay_s": None, "publication_url": None,
            "expected": None, "expected_note": "not available: no licensed consensus source",
            "facts": [], "interpretation": None, "previous": None, "revision": None, "surprise": None,
            "market_reaction": {}, "reliability": kw.get("reliability", "official schedule")}


# ---------------------------------------------------------------- Federal Reserve

def parse_fed_month(flat_text, year, month, url):
    """Fed monthly calendar page (e.g. /newsevents/2026-october.htm). Times are as printed (Eastern; the page does
    not print the zone)."""
    out = []
    note = "Fed calendar %s; times printed without a zone, read as America/New_York" % url
    for t, m1, d1, d2, day in re.findall(r"\|(\d{1,2}:\d\d [ap]\.m\.)\|FOMC Meeting\|Two-day meeting, (\w+) (\d+) - (\d+)\|"
                                         r"(?:Press Conference\|)?(\d+)\|", flat_text):
        d = date(year, month, int(day))
        out.append(event("US-FED-FOMC_STATEMENT-%s" % d, "Federal Reserve", url, "US", "central bank decision",
                         "FOMC statement (meeting %s %s-%s)" % (m1, d1, d2),
                         datetime.combine(d, _clock(t), tzinfo=NY), "America/New_York", note))
    for t, day in re.findall(r"\|(\d{1,2}:\d\d [ap]\.m\.)\|FOMC Press Conference\|(\d+)\|", flat_text):
        d = date(year, month, int(day))
        out.append(event("US-FED-FOMC_PRESSCONF-%s" % d, "Federal Reserve", url, "US", "central bank communication",
                         "FOMC press conference", datetime.combine(d, _clock(t), tzinfo=NY), "America/New_York", note))
    for t, meeting, day in re.findall(r"\|(\d{1,2}:\d\d [ap]\.m\.)\|FOMC Minutes\|Meeting of ([^|]+)\|(\d+)\|", flat_text):
        d = date(year, month, int(day))
        out.append(event("US-FED-FOMC_MINUTES-%s" % d, "Federal Reserve", url, "US", "central bank communication",
                         "FOMC minutes (meeting of %s)" % meeting.strip(), datetime.combine(d, _clock(t), tzinfo=NY),
                         "America/New_York", note))
    return out


def parse_fed_feed(xml_text):
    """Fed monetary-policy press feed -> [{title, link, published_utc, date}] (regex, no XML entity expansion)."""
    out = []
    for it in re.findall(r"<item>(.*?)</item>", xml_text, re.S):
        g = lambda k: (re.search(r"<%s>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</%s>" % (k, k), it, re.S) or [None, None])[1]
        link, pub = g("link"), g("pubDate")
        m = re.search(r"monetary(\d{8})", link or "")
        out.append({"title": _html.unescape(g("title") or "").strip(), "link": (link or "").strip(),
                    "published_utc": datetime.strptime(pub.strip(), "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=UTC)
                    if pub else None,
                    "date": datetime.strptime(m.group(1), "%Y%m%d").date() if m else None})
    return out


def fomc_target_sentence(statement_html):
    """The statement sentence that sets the federal funds target range, verbatim (a fact, not an interpretation).
    Reads paragraph text only, so navigation and page furniture cannot leak in."""
    for para in re.findall(r"<p[^>]*>(.*?)</p>", statement_html, re.S | re.I):
        text = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", para))).strip()
        for s in re.split(r"(?<=\.) (?=[A-Z])", text):
            if "target range for the federal funds rate" in s and "percent" in s:
                return s.strip()
    return None


def target_range(sentence):
    """'... at 3-1/2 to 3-3/4 percent' -> (3.5, 3.75); None if not found."""
    if not sentence:
        return None
    m = re.search(r"(\d+(?:-\d/\d)?)\s+to\s+(\d+(?:-\d/\d)?)\s+percent", sentence)
    if not m:
        return None

    def num(s):
        if "-" in s:
            w, f = s.split("-")
            a, b = f.split("/")
            return int(w) + int(a) / int(b)
        return float(s)
    return num(m.group(1)), num(m.group(2))


# ---------------------------------------------------------------- BEA

BEA_KEEP = ("GDP (", "Personal Income and Outlays")


def parse_bea(html_text, year, url):
    """BEA release schedule table: rows of date, time (ET), type, title. Keeps GDP and Personal Income and Outlays
    (which contains PCE)."""
    out = []
    for d, t, title in re.findall(r'<div class="release-date">([A-Za-z]+ \d{1,2})</div>\s*<small[^>]*>([^<]+)</small>'
                                  r'.*?<td class="release-title[^"]*"[^>]*>(.*?)</td>', html_text, re.S):
        title = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", title))).strip()
        if not title.startswith(BEA_KEEP):
            continue
        mon, day = d.split()
        dd = date(year, MONTHS[mon.lower()], int(day))
        kind = "GDP" if title.startswith("GDP") else "PIO_PCE"
        out.append(event("US-BEA-%s-%s" % (kind, dd), "US Bureau of Economic Analysis", url, "US", "economic release",
                         title, datetime.combine(dd, _clock(t), tzinfo=NY), "America/New_York",
                         "BEA release schedule; times printed without a zone, read as America/New_York"))
    return out


# ---------------------------------------------------------------- BLS (iCalendar)

BLS_KEEP = {"Employment Situation": "EMPSIT", "Consumer Price Index": "CPI", "Producer Price Index": "PPI",
            "Job Openings and Labor Turnover": "JOLTS", "Employment Cost Index": "ECI"}
ICS_ZONES = {"US-Eastern": NY, "America/New_York": NY, "Eastern Standard Time": NY, "US/Eastern": NY}


def parse_ics(text):
    """Minimal RFC 5545 reader: unfolds continuation lines, returns [{SUMMARY, DTSTART (aware datetime or date),
    tz_basis}] per VEVENT. Unknown TZIDs are not guessed: such events get dtstart None."""
    lines = re.sub(r"\r?\n[ \t]", "", text).splitlines()
    out, cur = [], None
    for ln in lines:
        if ln == "BEGIN:VEVENT":
            cur = {}
        elif ln == "END:VEVENT" and cur is not None:
            out.append(cur)
            cur = None
        elif cur is not None and ":" in ln:
            k, v = ln.split(":", 1)
            name, *params = k.split(";")
            if name == "SUMMARY":
                cur["SUMMARY"] = v.replace("\\,", ",").replace("\\;", ";").strip()
            elif name == "DTSTART":
                p = dict(x.split("=", 1) for x in params if "=" in x)
                if p.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", v):
                    cur["DTSTART"], cur["tz_basis"] = datetime.strptime(v[:8], "%Y%m%d").date(), "date only"
                elif v.endswith("Z"):
                    cur["DTSTART"], cur["tz_basis"] = datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC), "UTC"
                elif "TZID" in p:
                    z = ICS_ZONES.get(p["TZID"])
                    cur["DTSTART"] = datetime.strptime(v, "%Y%m%dT%H%M%S").replace(tzinfo=z) if z else None
                    cur["tz_basis"] = "TZID=%s" % p["TZID"] + ("" if z else " (unknown zone: not guessed)")
                else:
                    cur["DTSTART"], cur["tz_basis"] = None, "floating time (no zone): not guessed"
    return out


def parse_atom(xml_text):
    """Atom feed (BLS release feeds) -> [{title, link, published_utc}] (regex; no XML entity expansion)."""
    out = []
    for en in re.findall(r"<entry>(.*?)</entry>", xml_text, re.S):
        t = re.search(r"<title[^>]*>(.*?)</title>", en, re.S)
        l = re.search(r'<link[^>]*href="([^"]+)"', en)
        p = re.search(r"<published>(.*?)</published>", en)
        pub = None
        if p:
            v = re.sub(r"\.\d+(?=[+-]\d\d:\d\d$)", "", p.group(1).strip())
            pub = datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(UTC)
        out.append({"title": _html.unescape(t.group(1)).strip() if t else "", "link": l.group(1) if l else "",
                    "published_utc": pub})
    return out


def parse_bls_ics(text, url):
    out = []
    for v in parse_ics(text):
        title, start = v.get("SUMMARY", ""), v.get("DTSTART")
        kind = next((k for t, k in BLS_KEEP.items() if title.startswith(t)), None)
        if not kind or start is None:
            continue
        d = start.astimezone(NY).date() if isinstance(start, datetime) else start
        out.append(event("US-BLS-%s-%s" % (kind, d), "US Bureau of Labor Statistics", url, "US", "economic release",
                         title, start.astimezone(NY) if isinstance(start, datetime) else start, "America/New_York",
                         "BLS iCalendar (%s)" % v.get("tz_basis")))
    return out


# ---------------------------------------------------------------- Bank of Japan

def parse_boj_schedule(flat_text, year, url):
    """BoJ MPM table for `year`: 'Oct. 29 (Thurs.), 30 (Fri.)' -> statement date = last day. The BoJ publishes no fixed
    time for the policy statement ('after the meeting'), so only the date is recorded."""
    i = flat_text.find("Table : %d" % year)
    j = flat_text.find("Table : %d" % (year + 1))
    seg = flat_text[i:j if j > i else None] if i >= 0 else ""
    out = []
    for m1, d1, d2 in re.findall(r"\|([A-Z][a-z]+)\.? (\d{1,2}) \([A-Za-z]+\.?\), (\d{1,2}) \([A-Za-z]+\.?\)", seg):
        mo = ABBR.get(m1.lower().rstrip("."))
        if not mo:
            continue
        d = date(year, mo, int(d2))
        out.append(event("JP-BOJ-MPM_STATEMENT-%s" % d, "Bank of Japan", url, "JP", "central bank decision",
                         "BoJ Monetary Policy Meeting statement (meeting %s %s-%s)" % (m1, d1, d2), d, "Asia/Tokyo",
                         "BoJ MPM schedule; date only: the BoJ does not publish the statement time in advance"))
    return out


def parse_boj_feed(xml_text):
    out = []
    for it in re.findall(r"<item[^>]*>(.*?)</item>", xml_text, re.S):
        t = re.search(r"<title>(.*?)</title>", it, re.S)
        l = re.search(r"<link>(.*?)</link>", it, re.S)
        d = re.search(r"<pubDate>(.*?)</pubDate>", it) or re.search(r"<dc:date>(.*?)</dc:date>", it)
        pub = None
        if d:
            s = d.group(1).strip()
            for f in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z"):
                try:
                    pub = datetime.strptime(s, f).astimezone(UTC)
                    break
                except ValueError:
                    pass
        out.append({"title": _html.unescape(t.group(1)).strip() if t else "", "link": l.group(1).strip() if l else "",
                    "published_utc": pub})
    return out


# ---------------------------------------------------------------- ONS

ONS_KEEP = {"Consumer price inflation, UK": "CPI", "GDP monthly estimate, UK": "GDP_MONTHLY",
            "UK Labour Market": "LABOUR"}            # the calendar title of the labour market overview bulletin


def parse_ons(html_text, url):
    """ONS release calendar search results: 'Title|Release date:|18 November 2026 7:00am |Confirmed'. Only the main
    bulletins in ONS_KEEP (not their 'time series' companions). The search page wraps matched words in inline tags,
    which are removed (not turned into boundaries) before flattening."""
    flat_text = flatten(re.sub(r"</?(?:strong|em|mark|b|i|span)\b[^>]*>", "", html_text, flags=re.I))
    out = []
    for title, d, t, st in re.findall(r"\|([^|]+?)\|Release date:\s*\|?\s*(\d{1,2} [A-Z][a-z]+ \d{4}) (\d{1,2}:\d\d[ap]m)\s*\|\s*"
                                      r"(Confirmed|Provisional|Published|Cancelled)", flat_text):
        title = title.strip()
        base = title.split(":")[0].strip()
        if base not in ONS_KEEP or "time series" in title:
            continue
        dd = datetime.strptime(d, "%d %B %Y").date()
        e = event("UK-ONS-%s-%s" % (ONS_KEEP[base], dd), "UK Office for National Statistics", url, "UK",
                  "economic release", title, datetime.combine(dd, _clock(t), tzinfo=LONDON), "Europe/London",
                  "ONS release calendar (%s)" % st)
        e["ons_status"] = st
        out.append(e)
    return out


# ---------------------------------------------------------------- Japan Ministry of Finance (intervention)

def parse_mof(flat_text, url):
    """Latest MoF intervention releases (monthly and quarterly). Release dates are not scheduled in advance."""
    out = {}
    for kind in ("Quarterly Release", "Monthly Release"):
        m = re.search(re.escape(kind) + r"\|Latest Press Release: \|([^|]+)\|\(([A-Z][a-z]+ \d{1,2}, \d{4})\)", flat_text)
        if m:
            out[kind] = {"period": m.group(1).strip(), "published": datetime.strptime(m.group(2), "%B %d, %Y").date().isoformat(),
                         "source_url": url}
    return out


# ---------------------------------------------------------------- reaction and status

def reaction(bars, t0, now, pip=None, initial_min=15, later_min=120):
    """Indicative price changes from t0 to t0+15 min (initial) and t0+15 to t0+120 min (subsequent).
    bars: 1-minute closes indexed by bar START (UTC). Uses src.market_intel.value_at (never a later bar)."""
    from src.market_intel import value_at
    if bars is None or len(bars) == 0:
        return {"status": "UNAVAILABLE"}
    t1, t2 = t0 + timedelta(minutes=initial_min), t0 + timedelta(minutes=later_min)
    p0, _ = value_at(bars, t0)
    p1, _ = value_at(bars, t1) if now >= t1 else (None, None)
    p2, _ = value_at(bars, t2) if now >= t2 else (None, None)
    out = {"status": "COMPLETE" if p2 is not None else ("PENDING" if now < t2 else "INCOMPLETE")}
    if p0 is None:
        out["status"] = "UNAVAILABLE"
        return out
    if p1 is not None:
        out["initial_bp"] = 1e4 * (p1 / p0 - 1)
        if pip:
            out["initial_pips"] = (p1 - p0) / pip
    if p1 is not None and p2 is not None:
        out["subsequent_bp"] = 1e4 * (p2 / p1 - 1)
        if pip:
            out["subsequent_pips"] = (p2 - p1) / pip
    out["note"] = "observed indicative changes; not attributed to the event"
    return out


def upcoming(events, now, days):
    end = now + timedelta(days=days)
    def when(e):
        return datetime.fromisoformat(e["scheduled_time_utc"]) if e["scheduled_time_utc"] else \
            datetime.combine(date.fromisoformat(e["scheduled_date"]), time(0), tzinfo=UTC)
    return sorted([e for e in events if now <= when(e) <= end and e["status"] == "SCHEDULED"], key=when)
