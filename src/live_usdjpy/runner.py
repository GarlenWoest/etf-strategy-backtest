"""Unattended runner logic for the LaunchAgent (step 9, approved 2026-10-29). Pure decisions + small helpers; the
network work is in tools/usdjpy_pipeline.py `run`.

The agent fires at :02, :17, :32, :47 (StartCalendarInterval; missed fires during sleep coalesce into one run on
wake). Each run:
  notify            always (outbox, digest at 18:00 ET, liveness alerts)
  scan              if FX is open and no scan yet in this clock hour; or a position is open / a setup is pending;
                    or the last scan predates the latest daily-bar completion (17:00 New York on the last weekday,
                    including Friday's close while the market is closed)
  events poll       at the first run after 06:00, 09:00, 13:00 and 16:40 ET, and 5 minutes after any scheduled
                    release time of today (official sources only)
A run never claims coverage it did not have: gaps between runs are recorded with the power log's sleep evidence.
"""
import re
import subprocess
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from src import clock as K

NY = ZoneInfo("America/New_York")
EVENT_POLL_TIMES = ((6, 0), (9, 0), (13, 0), (16, 40))
GAP_MINUTES = 25
BAR_WAIT = timedelta(hours=6)


def last_bar_completion(now):
    """Most recent 17:00 New York on a weekday at or before `now` (when the latest OANDA daily candle completed)."""
    n = now.astimezone(NY)
    d = n.date()
    for _ in range(8):
        t = datetime.combine(d, time(17, 0), tzinfo=NY)
        if d.weekday() < 5 and t <= n:
            return t
        d -= timedelta(days=1)
    return None


def plan(now, st, active_setups, todays_releases):
    """Tasks for this run. st: runner state dict (ISO UTC strings). active_setups: bool (open position or a setup
    triggered/blocked). todays_releases: aware datetimes of today's scheduled official releases."""
    tasks, why = {"notify"}, []
    last_scan = datetime.fromisoformat(st["last_scan_utc"]) if st.get("last_scan_utc") else None
    n = now.astimezone(NY)
    fx_open = K.fx_market_open(now)
    comp = last_bar_completion(now)
    if last_scan is None:
        tasks.add("scan"); why.append("first scan")
    elif comp and last_scan < comp:
        tasks.add("scan"); why.append("new daily bar completed %s" % comp.strftime("%a %H:%M ET"))
    elif comp and st.get("last_bar_seen") and st["last_bar_seen"] < comp.date().isoformat() and now - comp < BAR_WAIT:
        # the scan after 17:00 ran before the venue flagged the candle complete: keep scanning every run (up to BAR_WAIT)
        tasks.add("scan"); why.append("waiting for the %s daily bar (last seen %s)" % (comp.date().isoformat(), st["last_bar_seen"]))
    elif fx_open and active_setups:
        tasks.add("scan"); why.append("open position or pending setup")
    elif fx_open and last_scan.astimezone(NY).replace(minute=0, second=0, microsecond=0) < n.replace(minute=0, second=0, microsecond=0):
        tasks.add("scan"); why.append("hourly")
    last_poll = datetime.fromisoformat(st["last_events_poll_utc"]) if st.get("last_events_poll_utc") else None
    targets = [datetime.combine(n.date(), time(h, m), tzinfo=NY) for h, m in EVENT_POLL_TIMES]
    targets += [t + timedelta(minutes=5) for t in todays_releases]
    due = [t for t in targets if t <= now and (last_poll is None or last_poll < t) and now - t < timedelta(hours=3)]
    if due:
        tasks.add("events"); why.append("event poll due (%s)" % max(due).astimezone(NY).strftime("%H:%M ET"))
    return tasks, why


def sleep_evidence(start, end):
    """Count of system Sleep entries in `pmset -g log` between start and end (None if the log cannot be read)."""
    try:
        out = subprocess.run(["pmset", "-g", "log"], capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return None
    n = 0
    for line in out.splitlines():
        m = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ([+-]\d{4})\s+Sleep\s", line)
        if m:
            t = datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M:%S %z")
            if start <= t <= end:
                n += 1
    return n


def gap_record(st, now):
    """A gap record if the previous run is more than GAP_MINUTES ago, else None."""
    if not st.get("last_run_utc"):
        return None
    last = datetime.fromisoformat(st["last_run_utc"])
    gap = (now - last).total_seconds() / 60
    if gap <= GAP_MINUTES:
        return None
    sl = sleep_evidence(last, now)
    return {"type": "runner_gap", "from_utc": last.isoformat(), "to_utc": now.astimezone(timezone.utc).isoformat(),
            "minutes": round(gap, 1), "power_log_sleep_entries": sl,
            "likely_cause": "Mac asleep" if sl else ("job not running (app/Mac off, logged out, or not installed)" if sl == 0 else "UNKNOWN")}
