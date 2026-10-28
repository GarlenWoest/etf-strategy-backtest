"""Official event monitor (Phase C): parsers on short fixtures copied from the official pages (2026-10-28), times and
DST, facts without interpretation, indicative reaction windows, idempotent merge, isolation. Offline."""
import ast
import importlib.util
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import PROJECT_ROOT
from src import events as E

UTC = timezone.utc

FED_OCT = ("|FOMC Meetings |Time:|Release Date(s):|2:00 p.m.|FOMC Minutes|Meeting of September 15-16|7|2:30 p.m.|"
           "FOMC Press Conference|28|2:00 p.m.|FOMC Meeting|Two-day meeting, October 27 - 28|Press Conference|28|Beige Book |")
FED_DEC = "|2:00 p.m.|FOMC Meeting|Two-day meeting, December 8 - 9|Press Conference|9|2:30 p.m.|FOMC Press Conference|9|"
FED_FEED = ("<rss><channel><item><title>Federal Reserve issues FOMC statement</title><link><![CDATA[https://www.federalreserve"
            ".gov/newsevents/pressreleases/monetary20261028a.htm]]></link><pubDate><![CDATA[Wed, 28 Oct 2026 18:00:00 GMT]]>"
            "</pubDate></item></channel></rss>")
STATEMENT = ("<div>Share</div><p>Recent indicators suggest ... </p><p>In support of its goals, the Committee decided to "
             "maintain the target range for the federal funds rate at 3-3/4 to 4 percent. In considering ...</p>")
BEA = ('<tr><td class="scheduled-date"><div class="release-date">October 29</div>\n<small class="text-muted">8:30 AM</small>'
       '</td><td><div class="icon-letter">News</div></td><td class="release-title views-field">GDP (Advance Estimate), 3rd '
       'Quarter 2026 </td></tr><tr><td class="scheduled-date"><div class="release-date">November 4</div>\n<small class="'
       'text-muted">8:30 AM</small></td><td></td><td class="release-title x">U.S. International Trade in Goods and Services,'
       ' September 2026 </td></tr><tr><td class="scheduled-date"><div class="release-date">October 29</div><small class="t">'
       '8:30 AM</small></td><td></td><td class="release-title y">Personal Income and Outlays, September 2026 </td></tr>')
BOJ = ("|Table : 2026|Date of MPM|Release Schedule|Sept. 17 (Thurs.), 18 (Fri.) [PDF 204KB]|-|Oct. 1 (Thurs.) [PDF 227KB]|"
       "Nov. 5 (Thurs.)|Oct. 29 (Thurs.), 30 (Fri.)|Oct. 30 (Fri.)|Nov. 10 (Tues.)|Dec. 23 (Wed.)|Dec. 17 (Thurs.), 18 (Fri.)|"
       "-|Dec. 28 (Mon.)|Jan. 27 (Wed.), 2027|Note: |Table : 2027|Jan. 21 (Thurs.), 22 (Fri.)|")
ONS = ('<li><a>Producer <strong>price</strong> inflation, UK: October 2026</a><p>Release date: <span>18 November 2026 7:00am'
       '</span></p><p>Confirmed</p></li><li><a><strong>Consumer</strong> <strong>price</strong> <strong>inflation</strong>, '
       'UK: October 2026 time series</a><p>Release date: 18 November 2026 7:00am</p><p>Confirmed</p></li><li><a><strong>'
       'Consumer</strong> price inflation, UK: October 2026</a><p>Release date:</p><p>18 November 2026 7:00am</p><p>'
       'Confirmed</p></li><li><a>Consumer price inflation, UK: September 2026</a><p>Release date: 21 October 2026 7:00am'
       '</p><p>Published</p></li>')
MOF = ("|Foreign Exchange Intervention Operations|Quarterly Release|Latest Press Release: |April - June 2026|(August 7, 2026)|"
       "Historical Data|Monthly Release|Latest Press Release: |August 27, 2026 - September 28, 2026|(September 30, 2026)|HOME|")


def test_fed_month_times_and_dst():
    ev = {e["event_id"]: e for e in E.parse_fed_month(FED_OCT, 2026, 10, "u")}
    st = ev["US-FED-FOMC_STATEMENT-2026-10-28"]
    assert st["scheduled_time_utc"] == "2026-10-28T18:00:00+00:00"                 # 2:00 p.m. EDT
    assert ev["US-FED-FOMC_PRESSCONF-2026-10-28"]["scheduled_time_utc"] == "2026-10-28T18:30:00+00:00"
    assert ev["US-FED-FOMC_MINUTES-2026-10-07"]["scheduled_time_utc"] == "2026-10-07T18:00:00+00:00"
    assert st["status"] == "SCHEDULED" and st["interpretation"] is None and st["expected"] is None
    assert set(st["markets_affected"]) == {"usdjpy", "gbpusd", "gold"}
    dec = {e["event_id"]: e for e in E.parse_fed_month(FED_DEC, 2026, 12, "u")}
    assert dec["US-FED-FOMC_STATEMENT-2026-12-09"]["scheduled_time_utc"] == "2026-12-09T19:00:00+00:00"   # EST


def test_fed_feed_and_statement_facts():
    it = E.parse_fed_feed(FED_FEED)[0]
    assert it["date"] == date(2026, 10, 28) and it["published_utc"] == datetime(2026, 10, 28, 18, 0, tzinfo=UTC)
    s = E.fomc_target_sentence(STATEMENT)
    assert s.startswith("In support of its goals") and "Share" not in s
    assert E.target_range(s) == (3.75, 4.0)
    assert E.target_range("... at 4 to 4-1/4 percent.") == (4.0, 4.25)
    assert E.target_range(None) is None and E.fomc_target_sentence("<p>No decision text.</p>") is None


def test_bea_keeps_gdp_and_pce_only():
    ev = E.parse_bea(BEA, 2026, "u")
    assert [e["event_id"] for e in ev] == ["US-BEA-GDP-2026-10-29", "US-BEA-PIO_PCE-2026-10-29"]
    assert ev[0]["scheduled_time_utc"] == "2026-10-29T12:30:00+00:00"


def test_boj_date_only_for_the_right_year():
    ev = E.parse_boj_schedule(BOJ, 2026, "u")
    ids = [e["event_id"] for e in ev]
    assert ids == ["JP-BOJ-MPM_STATEMENT-2026-09-18", "JP-BOJ-MPM_STATEMENT-2026-10-30", "JP-BOJ-MPM_STATEMENT-2026-12-18"]
    assert all(e["scheduled_time_utc"] is None for e in ev)                       # no time is published


def test_ons_main_bulletins_with_highlight_tags():
    ev = {e["event_id"]: e for e in E.parse_ons(ONS, "u")}
    assert set(ev) == {"UK-ONS-CPI-2026-11-18", "UK-ONS-CPI-2026-10-21"}           # no time series, no PPI
    assert ev["UK-ONS-CPI-2026-11-18"]["scheduled_time_utc"] == "2026-11-18T07:00:00+00:00"   # GMT
    assert ev["UK-ONS-CPI-2026-10-21"]["scheduled_time_utc"] == "2026-10-21T06:00:00+00:00"   # BST
    assert ev["UK-ONS-CPI-2026-10-21"]["ons_status"] == "Published"


def test_mof_latest_releases():
    m = E.parse_mof(MOF, "u")
    assert m["Monthly Release"] == {"period": "August 27, 2026 - September 28, 2026", "published": "2026-09-30", "source_url": "u"}
    assert m["Quarterly Release"]["published"] == "2026-08-07"


def test_reaction_windows_use_only_past_bars():
    t0 = datetime(2026, 10, 28, 18, 0, tzinfo=UTC)
    idx = pd.date_range("2026-10-28T17:00", "2026-10-28T21:00", freq="1min", tz="UTC")
    px = pd.Series(150.0, index=idx)
    px[idx >= pd.Timestamp("2026-10-28T18:05", tz="UTC")] = 151.5                  # +1% after the release
    px[idx >= pd.Timestamp("2026-10-28T19:00", tz="UTC")] = 150.0                  # back later
    pending = E.reaction(px, t0, t0 + timedelta(minutes=20), pip=0.01)
    assert pending["status"] == "PENDING" and abs(pending["initial_pips"] - 150) < 1e-9 and "subsequent_bp" not in pending
    done = E.reaction(px, t0, t0 + timedelta(hours=3), pip=0.01)
    assert done["status"] == "COMPLETE" and abs(done["initial_bp"] - 100) < 1e-9 and done["subsequent_bp"] < -95
    assert E.reaction(None, t0, t0 + timedelta(hours=3))["status"] == "UNAVAILABLE"


def _tool():
    spec = importlib.util.spec_from_file_location("ev", PROJECT_ROOT / "tools" / "events.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_merge_is_idempotent_and_logs_schedule_changes(tmp_path, monkeypatch):
    T = _tool()
    monkeypatch.setattr(T, "OUT", tmp_path)
    now = datetime(2026, 10, 28, 12, tzinfo=UTC)
    store = {"events": {}, "sources": {}}
    ev = E.parse_fed_month(FED_OCT, 2026, 10, "u")
    T.merge(store, ev, now)
    T.merge(store, E.parse_fed_month(FED_OCT, 2026, 10, "u"), now)
    lines = (tmp_path / "changes.jsonl").read_text().splitlines()
    assert len(store["events"]) == 3 and len(lines) == 3                          # second merge: no change, no log
    moved = E.parse_fed_month(FED_OCT.replace("2:30 p.m.", "3:00 p.m."), 2026, 10, "u")
    T.merge(store, moved, now)
    assert store["events"]["US-FED-FOMC_PRESSCONF-2026-10-28"]["scheduled_time_utc"] == "2026-10-28T19:00:00+00:00"
    assert "schedule changed" in (tmp_path / "changes.jsonl").read_text().splitlines()[-1]


def test_publication_marked_once_and_before_monitoring_noted(tmp_path, monkeypatch):
    T = _tool()
    monkeypatch.setattr(T, "OUT", tmp_path)
    now = datetime(2026, 10, 28, 18, 11, tzinfo=UTC)
    store = {"events": {}, "sources": {}, "monitoring_started_utc": "2026-10-28T17:00:00+00:00"}
    T.merge(store, E.parse_fed_month(FED_OCT, 2026, 10, "u"), now)
    eid = "US-FED-FOMC_STATEMENT-2026-10-28"
    assert T.mark_published(store, eid, datetime(2026, 10, 28, 18, 0, tzinfo=UTC), "link", now)
    assert store["events"][eid]["detection_delay_s"] == 660                        # detected 11 min after 2:00 p.m.
    assert not T.mark_published(store, eid, datetime(2026, 10, 28, 18, 0, tzinfo=UTC), "link", now)
    store2 = {"events": {}, "sources": {}, "monitoring_started_utc": "2026-10-28T18:30:00+00:00"}
    T.merge(store2, E.parse_fed_month(FED_OCT, 2026, 10, "u"), now)
    T.mark_published(store2, eid, datetime(2026, 10, 28, 18, 0, tzinfo=UTC), "link", now)
    assert store2["events"][eid]["detection_delay_s"] is None and "before monitoring" in store2["events"][eid]["detection_note"]


def test_isolation_and_write_guard():
    T = _tool()
    with pytest.raises(RuntimeError):
        T._guard(PROJECT_ROOT / "data" / "x.json")
    for p in list((PROJECT_ROOT / "src").rglob("*.py")) + list((PROJECT_ROOT / "tools").glob("*.py")):
        rel = str(p.relative_to(PROJECT_ROOT))
        if rel in ("src/events.py", "tools/events.py"):
            continue
        tree = ast.parse(p.read_text())
        mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | \
               {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        names = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == "src" for a in n.names}
        assert "src.events" not in mods and "events" not in names, rel


ICS = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nSUMMARY:Employment Situation for October 2026\r\n"
       "DTSTART;TZID=US-Eastern:20261106T083000\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nSUMMARY:Consumer Price Index for Oc\r\n"
       " tober 2026\r\nDTSTART:20261112T133000Z\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nSUMMARY:Producer Price Index for Octob"
       "er 2026\r\nDTSTART;TZID=Mars/Olympus:20261113T083000\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nSUMMARY:County Employment"
       " and Wages\r\nDTSTART;TZID=US-Eastern:20261203T100000\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nSUMMARY:Job Openings and "
       "Labor Turnover Survey for September 2026\r\nDTSTART:20261103T100000\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")


def test_bls_icalendar_zones_folding_and_no_guessing():
    ev = {e["event_id"]: e for e in E.parse_bls_ics(ICS, "u")}
    assert set(ev) == {"US-BLS-EMPSIT-2026-11-06", "US-BLS-CPI-2026-11-12"}   # unknown zone and floating time dropped
    assert ev["US-BLS-EMPSIT-2026-11-06"]["scheduled_time_utc"] == "2026-11-06T13:30:00+00:00"    # 08:30 EST
    assert ev["US-BLS-CPI-2026-11-12"]["title"] == "Consumer Price Index for October 2026"         # folded line
    assert ev["US-BLS-CPI-2026-11-12"]["scheduled_time_local"].startswith("2026-11-12T08:30:00")


class _Resp:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status
        self.content = text.encode()
        self.headers = {"Content-Type": "text/plain; charset=utf-8"}
        self.encoding = "utf-8"


def test_bls_contact_sent_only_to_bls_and_never_written(tmp_path, monkeypatch):
    T = _tool()
    probe = "probe-7f3a@example.invalid"
    monkeypatch.setattr(T, "OUT", tmp_path)
    monkeypatch.setattr(T, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(T._t, "sleep", lambda s: None)
    monkeypatch.setenv("BLS_CONTACT_EMAIL", probe)
    seen = {}

    def fake_get(url, headers=None, timeout=None):
        seen[url] = dict(headers or {})
        if "fail" in url:
            raise T.requests.ConnectionError("boom with %s" % (headers or {}))
        return _Resp(ICS)
    monkeypatch.setattr(T.requests, "get", fake_get)
    T.get("https://www.bls.gov/schedule/news_release/bls.ics")
    T.get("https://www.federalreserve.gov/feeds/press_monetary.xml")
    with pytest.raises(RuntimeError) as err:
        T.get("https://www.bls.gov/fail.rss")
    assert probe not in str(err.value)                                          # exception text has no headers
    assert probe in seen["https://www.bls.gov/schedule/news_release/bls.ics"]["User-Agent"]
    assert seen["https://www.federalreserve.gov/feeds/press_monetary.xml"] == {}    # other hosts: standard agent
    store = {"events": {}, "sources": {}}
    T.merge(store, E.parse_bls_ics(ICS, "u"), datetime(2026, 10, 28, tzinfo=UTC))
    (tmp_path / "events.json").write_text(__import__("json").dumps(store))
    for f in tmp_path.rglob("*"):
        if f.is_file():
            assert probe not in f.read_text(errors="replace"), f


def test_bls_blocked_without_contact(monkeypatch):
    T = _tool()
    monkeypatch.delenv("BLS_CONTACT_EMAIL", raising=False)
    with pytest.raises(RuntimeError, match="BLS_CONTACT_EMAIL not set"):
        T._headers("https://www.bls.gov/schedule/news_release/bls.ics")
    assert T._headers("https://www.bea.gov/news/schedule") == {}
    assert T._headers("https://notbls.gov.example.com/x") == {}


ATOM = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Both payroll employment (+29,000) and unemployment rate '
        '(4.2%) change little in September</title><link href="https://www.bls.gov/news.release/archives/empsit_10022026.htm"/>'
        '<published>2026-10-02T07:51:08.289-04:00</published></entry></feed>')


def test_bls_atom_feed():
    it = E.parse_atom(ATOM)[0]
    assert it["published_utc"] == datetime(2026, 10, 2, 11, 51, 8, tzinfo=UTC)
    assert it["link"].endswith("empsit_10022026.htm") and it["title"].startswith("Both payroll")
