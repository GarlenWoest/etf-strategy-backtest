"""Heartbeat for the scheduled runs (weekday watchlist/paper run, Sunday brief run). Writes ONLY live/heartbeat.json.

User decisions 2026-10-23:
  - every run records its start and finish (ok / error + short note); the last 120 runs are kept;
  - the Sunday brief starts with a status line for the week just ended: last successful weekday run, weekday runs vs the
    week's actual NYSE trading days, missed and late runs, errors;
  - "late" = a weekday run that started after 18:00 ET, or that ran on a later day (catch-up);
  - days before MONITORING_START (2026-10-23, the first scheduled weekday run) are not expected and never "missed";
  - the weekday run notifies once if the last successful weekday run was more than 3 trading days ago (no repeat until
    runs are normal again).

Phase H additions (user approval 2026-10-28):
  - run states: started (written at start), completed (finish ok, no failed step), partial (some steps failed or the
    session reported an error after some steps succeeded), failed (no step succeeded, or the run never finished);
    scheduled (the next expected run, shown in the status line) and missed (an expected trading day with no
    completed/partial run) are derived;
  - each step's result is recorded (`step`), and every notification's delivery (`notify`: delivered yes / no / unknown,
    with the tool's reason). The Sunday status line ends with an ALERT when a notification was not delivered.

Commands:
  start  --kind weekday|sunday                 -> prints the run id
  step   --id RUN_ID --name NAME --status ok|error [--note TEXT]
  notify --id RUN_ID --tag TEXT --delivered yes|no|unknown [--reason TEXT]
  finish --id RUN_ID --status ok|error [--note TEXT]
  check-gap                                    -> prints a NOTIFY: line once when the gap rule fires
  status                                       -> prints the Sunday status line
  runs   [--last N]                            -> prints recent runs with their states
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
STEPS = ("watchlist", "paper", "snapshot", "events", "bookb", "brief", "backup")
WEEKDAY_TIME = (16, 45)                    # scheduled weekday run (local = America/New_York), Mon-Fri
GAP_TRADING_DAYS = 3
MONITORING_START = date(2026, 10, 23)      # first scheduled weekday run (task created 2026-10-22 21:10 ET, after that day's run time)


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
                       "status": "running", "state": "started", "note": "", "steps": {}, "notifications": []})
    save(path, hb)
    return rid


def _find(hb, rid):
    for r in hb["runs"]:
        if r["id"] == rid:
            r.setdefault("steps", {})
            r.setdefault("notifications", [])
            return r
    return None


def step(path, rid, name, status, note, now):
    if name not in STEPS or status not in ("ok", "error"):
        raise ValueError("step name must be one of %s and status ok|error" % (STEPS,))
    hb = load(path)
    r = _find(hb, rid)
    if r is None:
        raise ValueError("unknown run id %s" % rid)
    r["steps"][name] = {"status": status, "note": note[:200], "at": now.isoformat(timespec="seconds")}
    save(path, hb)


def notify(path, rid, tag, delivered, reason, now):
    if delivered not in ("yes", "no", "unknown"):
        raise ValueError("delivered must be yes, no or unknown")
    hb = load(path)
    r = _find(hb, rid)
    if r is None:
        raise ValueError("unknown run id %s" % rid)
    r["notifications"].append({"at": now.isoformat(timespec="seconds"), "tag": tag[:80], "delivered": delivered,
                               "reason": reason[:160]})
    save(path, hb)


def run_state(status, steps):
    """completed / partial / failed from the session's reported status and the recorded steps."""
    oks = [k for k, v in steps.items() if v["status"] == "ok"]
    errs = [k for k, v in steps.items() if v["status"] == "error"]
    if status == "ok":
        return "partial" if errs else "completed"
    return "partial" if oks else "failed"


def finish(path, rid, status, note, now):
    hb = load(path)
    for r in hb["runs"]:
        if r["id"] == rid:
            r.setdefault("steps", {})
            r.setdefault("notifications", [])
            state = run_state(status, r["steps"])
            r.update(finished=now.isoformat(timespec="seconds"), state=state,
                     status="ok" if state in ("completed", "partial") else "error", note=note[:200])
            break
    else:
        hb["runs"].append({"id": rid, "kind": rid.split("-")[0], "started": None, "state": "failed", "steps": {},
                           "notifications": [], "finished": now.isoformat(timespec="seconds"), "status": status,
                           "note": "finish without start: " + note[:150]})
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
    days = [mon + timedelta(days=i) for i in range(5)
            if is_trading_day(mon + timedelta(days=i)) and mon + timedelta(days=i) >= MONITORING_START]
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
    pre = "" if mon >= MONITORING_START else " (monitoring started %s; earlier days not expected)" % MONITORING_START
    week = [r for r in hb["runs"] if (r["started"] or r["finished"]) and
            mon <= datetime.fromisoformat(r["started"] or r["finished"]).date() <= sunday + timedelta(days=1)]
    partial = ["%s %s (failed steps: %s)" % (r["kind"], (r["started"] or "")[:10], ", ".join(
        k for k, v in r.get("steps", {}).items() if v["status"] == "error") or "reported error") for r in week if r.get("state") == "partial"]
    notes = [n for r in week for n in r.get("notifications", [])]
    undelivered = [n for n in notes if n["delivered"] != "yes"]
    nxt = next_scheduled(now)
    line = ("Status: last successful weekday run %s; weekday runs this week %d of %d trading days%s; missed: %s; late: %s; "
            "errors: %s; partial: %s; notifications: %d recorded, %d not confirmed delivered; next scheduled weekday run: %s." % (
                last.strftime("%a %m-%d %H:%M ET") if last else "none yet", len(ok_days), len(days), pre,
                ", ".join(missed) or "none", ", ".join(late) or "none", "; ".join(errors) or "none",
                "; ".join(partial) or "none", len(notes), len(undelivered), nxt.strftime("%a %m-%d %H:%M ET")))
    if undelivered:
        line += " ALERT: notifications NOT DELIVERED: %s." % "; ".join(
            "%s %s (%s%s)" % (n["at"][:16].replace("T", " "), n["tag"], n["delivered"], ": " + n["reason"] if n["reason"] else "")
            for n in undelivered[:6])
    return line


def next_scheduled(now):
    """Next Monday-Friday 16:45 New York after `now` (the app adds a few minutes of jitter)."""
    d = now.astimezone(ET)
    cand = d.replace(hour=WEEKDAY_TIME[0], minute=WEEKDAY_TIME[1], second=0, microsecond=0)
    if cand <= d:
        cand += timedelta(days=1)
    while cand.weekday() >= 5:
        cand += timedelta(days=1)
    return cand


def runs_table(path, last=10):
    hb = load(path)
    out = []
    for r in hb["runs"][-last:]:
        steps = ",".join("%s:%s" % (k, v["status"]) for k, v in r.get("steps", {}).items()) or "-"
        nd = sum(n["delivered"] != "yes" for n in r.get("notifications", []))
        out.append("%s | %s | state %s | steps %s | notifications %d (%d not confirmed) | %s" % (
            r["id"], (r["started"] or "")[:16], r.get("state", r["status"]), steps, len(r.get("notifications", [])), nd,
            r["note"] or ""))
    return "\n".join(out)


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
    elif cmd == "step":
        step(path, a[a.index("--id") + 1], a[a.index("--name") + 1], a[a.index("--status") + 1],
             a[a.index("--note") + 1] if "--note" in a else "", now)
        print("step recorded")
    elif cmd == "notify":
        notify(path, a[a.index("--id") + 1], a[a.index("--tag") + 1], a[a.index("--delivered") + 1],
               a[a.index("--reason") + 1] if "--reason" in a else "", now)
        print("notification recorded")
    elif cmd == "runs":
        print(runs_table(path, int(a[a.index("--last") + 1]) if "--last" in a else 10))
    elif cmd == "check-gap":
        m = check_gap(path, now)
        print(m or "heartbeat ok")
    elif cmd == "status":
        print(week_status(path, now))
    else:
        sys.exit(__doc__)
