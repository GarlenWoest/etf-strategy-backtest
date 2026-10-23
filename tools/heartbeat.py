"""Heartbeat for the scheduled runs (weekday watchlist/paper run, Sunday brief run). Writes ONLY live/heartbeat.json.

User decisions 2026-10-23:
  - every run records its start and finish (ok / error + short note); the last 120 runs are kept;
  - the Sunday brief starts with a status line for the week just ended: last successful weekday run, weekday runs vs the
    week's actual NYSE trading days, missed and late runs, errors;
  - "late" = a weekday run that started after 18:00 ET, or that ran on a later day (catch-up);
  - the weekday run notifies once if the last successful weekday run was more than 3 trading days ago (no repeat until
    runs are normal again).

Commands:
  start  --kind weekday|sunday                 -> prints the run id
  finish --id RUN_ID --status ok|error [--note TEXT]
  check-gap                                    -> prints a NOTIFY: line once when the gap rule fires
  status                                       -> prints the Sunday status line
"""
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from watchlist_signals import is_trading_day  # noqa: E402  (NYSE calendar)

ROOT = Path(__file__).resolve().parent.parent
ET = ZoneInfo("America/New_York")
KEEP = 120
GAP_TRADING_DAYS = 3


def load(path):
    return json.loads(path.read_text()) if path.exists() else {"runs": [], "gap_alerted": False}


def save(path, hb):
    hb["runs"] = hb["runs"][-KEEP:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(hb, indent=1))


def start(path, kind, now):
    hb = load(path)
    rid = "%s-%s" % (kind, now.strftime("%Y%m%dT%H%M%S"))
    hb["runs"].append({"id": rid, "kind": kind, "started": now.isoformat(timespec="seconds"), "finished": None,
                       "status": "running", "note": ""})
    save(path, hb)
    return rid


def finish(path, rid, status, note, now):
    hb = load(path)
    for r in hb["runs"]:
        if r["id"] == rid:
            r.update(finished=now.isoformat(timespec="seconds"), status=status, note=note[:200])
            break
    else:
        hb["runs"].append({"id": rid, "kind": rid.split("-")[0], "started": None,
                           "finished": now.isoformat(timespec="seconds"), "status": status, "note": "finish without start: " + note[:150]})
    save(path, hb)


def trading_days_after(a, b):
    """Trading days in (a, b]."""
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        n += is_trading_day(d)
    return n


def last_ok_weekday(hb, before=None):
    ok = [r for r in hb["runs"] if r["kind"] == "weekday" and r["status"] == "ok" and r["started"]
          and (before is None or r["id"] != before)]
    return datetime.fromisoformat(ok[-1]["started"]) if ok else None


def check_gap(path, now):
    """Called by the weekday run itself, after start: compares with the previous successful weekday run."""
    hb = load(path)
    current = [r for r in hb["runs"] if r["kind"] == "weekday" and r["status"] == "running"]
    last = last_ok_weekday(hb, before=current[-1]["id"] if current else None)
    if last is None:
        return None
    gap = trading_days_after(last.date(), now.date())
    msg = None
    if gap > GAP_TRADING_DAYS and not hb.get("gap_alerted"):
        msg = ("NOTIFY: [HEARTBEAT] the last successful weekday run was %s, %d trading days ago; runs were missed "
               "(the app was probably closed). Catch-up is running now." % (last.strftime("%a %Y-%m-%d %H:%M ET"), gap))
        hb["gap_alerted"] = True
    elif gap <= GAP_TRADING_DAYS:
        hb["gap_alerted"] = False
    save(path, hb)
    return msg


def week_status(path, now):
    """Status line for the Mon-Fri week before the most recent Sunday on or before `now`."""
    hb = load(path)
    sunday = now.date() - timedelta(days=(now.date().weekday() + 1) % 7)
    mon = sunday - timedelta(days=6)
    days = [mon + timedelta(days=i) for i in range(5) if is_trading_day(mon + timedelta(days=i))]
    wk = [r for r in hb["runs"] if r["kind"] == "weekday" and r["started"]]
    by_day = {}
    for r in wk:
        by_day.setdefault(datetime.fromisoformat(r["started"]).date(), []).append(r)
    ok_days, missed, late, errors = [], [], [], []
    for d in days:
        runs = [r for r in by_day.get(d, []) if r["status"] == "ok"]
        if runs:
            ok_days.append(d)
            t = datetime.fromisoformat(runs[0]["started"])
            if (t.hour, t.minute) >= (18, 0):
                late.append("%s (ran %s ET)" % (d.strftime("%a"), t.strftime("%H:%M")))
        else:
            later = [r for r in wk if r["status"] == "ok" and datetime.fromisoformat(r["started"]).date() > d]
            missed.append(d.strftime("%a") + (" (caught up %s)" % datetime.fromisoformat(later[0]["started"]).strftime("%a %m-%d")
                                              if later else ""))
    for r in hb["runs"]:
        st = r["started"] or r["finished"]
        if st and mon <= datetime.fromisoformat(st).date() <= sunday + timedelta(days=1) and r["status"] in ("error", "running"):
            if r["status"] == "running" and r["id"] == (hb["runs"][-1]["id"] if hb["runs"] else None):
                continue                                         # the run printing this line
            errors.append("%s %s: %s" % (r["kind"], st[:16].replace("T", " "), r["note"] or "did not finish"))
    last = last_ok_weekday(hb)
    return ("Status: last successful weekday run %s; weekday runs this week %d of %d trading days; missed: %s; late: %s; "
            "errors: %s." % (last.strftime("%a %m-%d %H:%M ET") if last else "none yet", len(ok_days), len(days),
                             ", ".join(missed) or "none", ", ".join(late) or "none", "; ".join(errors) or "none"))


if __name__ == "__main__":
    a = sys.argv
    path = Path(a[a.index("--file") + 1]) if "--file" in a else ROOT / "live" / "heartbeat.json"
    if not str(path.resolve()).startswith(str(ROOT.resolve())):
        sys.exit("heartbeat file must be inside the project")
    now = datetime.fromisoformat(a[a.index("--now") + 1]).replace(tzinfo=ET) if "--now" in a else datetime.now(ET)
    cmd = a[1]
    if cmd == "start":
        print(start(path, a[a.index("--kind") + 1], now))
    elif cmd == "finish":
        finish(path, a[a.index("--id") + 1], a[a.index("--status") + 1],
               a[a.index("--note") + 1] if "--note" in a else "", now)
    elif cmd == "check-gap":
        m = check_gap(path, now)
        print(m or "heartbeat ok")
    elif cmd == "status":
        print(week_status(path, now))
    else:
        sys.exit(__doc__)
