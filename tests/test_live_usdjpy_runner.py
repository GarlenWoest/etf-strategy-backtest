"""Runner planning for the LaunchAgent (step 9): when to scan, poll events and notify; gap records. Pure logic,
synthetic times (tests, not live results)."""
from datetime import datetime, timedelta, timezone

from src.live_usdjpy import runner as RN

U = timezone.utc


def iso(dt):
    return dt.isoformat()


def test_first_run_scans_and_always_notifies():
    tasks, why = RN.plan(datetime(2026, 11, 2, 21, 2, tzinfo=U), {}, False, [])
    assert {"scan", "notify"} <= tasks and "first scan" in why


def test_hourly_scan_while_fx_open_and_not_twice_in_the_same_hour():
    now = datetime(2026, 11, 3, 15, 2, tzinfo=U)                                # Tue 10:02 ET
    st = {"last_scan_utc": iso(datetime(2026, 11, 3, 14, 2, tzinfo=U))}
    assert "scan" in RN.plan(now, st, False, [])[0]
    st = {"last_scan_utc": iso(datetime(2026, 11, 3, 15, 2, tzinfo=U))}
    assert "scan" not in RN.plan(now + timedelta(minutes=15), st, False, [])[0]
    assert "scan" in RN.plan(now + timedelta(minutes=15), st, True, [])[0]   # pending setup: every run


def test_new_bar_after_17_et_triggers_a_scan_including_friday_close_while_closed():
    st = {"last_scan_utc": iso(datetime(2026, 10, 30, 20, 47, tzinfo=U))}        # Fri 16:47 ET
    fri_after = datetime(2026, 10, 30, 21, 2, tzinfo=U)                         # Fri 17:02 ET: market closed, bar complete
    tasks, why = RN.plan(fri_after, st, False, [])
    assert "scan" in tasks and any("new daily bar" in w for w in why)
    st = {"last_scan_utc": iso(fri_after)}
    sat = datetime(2026, 10, 31, 15, 2, tzinfo=U)
    assert "scan" not in RN.plan(sat, st, False, [])[0]                         # weekend: nothing new, market closed


def test_event_polls_at_fixed_times_and_after_releases_once():
    ny0830 = datetime(2026, 11, 6, 13, 30, tzinfo=U)                            # Fri 08:30 ET jobs report
    st = {"last_scan_utc": iso(datetime(2026, 11, 6, 13, 2, tzinfo=U)), "last_events_poll_utc": iso(datetime(2026, 11, 6, 11, 2, tzinfo=U))}
    assert "events" not in RN.plan(datetime(2026, 11, 6, 13, 32, tzinfo=U), st, False, [ny0830])[0]   # before 08:35
    t, _ = RN.plan(datetime(2026, 11, 6, 13, 47, tzinfo=U), st, False, [ny0830])
    assert "events" in t
    st["last_events_poll_utc"] = iso(datetime(2026, 11, 6, 13, 47, tzinfo=U))
    assert "events" not in RN.plan(datetime(2026, 11, 6, 13, 59, tzinfo=U), st, False, [ny0830])[0]   # release poll done
    assert "events" in RN.plan(datetime(2026, 11, 6, 14, 2, tzinfo=U), st, False, [ny0830])[0]        # 09:00 ET poll due
    st["last_events_poll_utc"] = iso(datetime(2026, 11, 6, 14, 2, tzinfo=U))
    assert "events" not in RN.plan(datetime(2026, 11, 6, 14, 17, tzinfo=U), st, False, [ny0830])[0]


def test_gap_record_only_after_more_than_25_minutes():
    now = datetime(2026, 11, 3, 15, 2, tzinfo=U)
    assert RN.gap_record({"last_run_utc": iso(now - timedelta(minutes=15))}, now) is None
    g = RN.gap_record({"last_run_utc": iso(now - timedelta(hours=9))}, now)
    assert g["minutes"] == 540 and g["type"] == "runner_gap" and "likely_cause" in g


def test_last_bar_completion_skips_weekends():
    assert RN.last_bar_completion(datetime(2026, 11, 1, 18, 0, tzinfo=U)).isoformat().startswith("2026-10-30T17:00")


def test_keeps_scanning_until_the_new_daily_bar_is_actually_seen():
    """2026-10-30: if the 17:02 scan ran before the venue flagged the candle complete, the old plan considered the
    bar covered and (with FX closed on Friday evening) would not scan again until Sunday."""
    fri = datetime(2026, 10, 30, 21, 17, tzinfo=timezone.utc)            # Fri 17:17 ET, FX closed
    st = {"last_scan_utc": datetime(2026, 10, 30, 21, 2, tzinfo=timezone.utc).isoformat(), "last_bar_seen": "2026-10-29"}
    tasks, why = RN.plan(fri, st, False, [])
    assert "scan" in tasks and any("waiting for the 2026-10-30 daily bar" in w for w in why)
    assert "scan" not in RN.plan(fri, dict(st, last_bar_seen="2026-10-30"), False, [])[0]
    assert "scan" not in RN.plan(fri + timedelta(hours=7), st, False, [])[0]          # gives up after 6 h
    assert "scan" not in RN.plan(fri, {k: v for k, v in st.items() if k != "last_bar_seen"}, False, [])[0]  # old state
