"""Weekly opportunity review (Phase H, 2026-10-31): a short, factual desk review of one New York week, built only
from the forward registry. No statistics below 30 resolved signals, no parameter suggestions, no new strategies.

Sections: meaningful opportunities; experimental ideas and their status; approved paper signals; resolved paper
positions; blocked or invalidated setups; notification failures; data-quality and readiness problems; significant
official events; expected vs observed outcomes; lessons and unresolved limitations.
"""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from . import lifecycle as LC
from . import notify as N

NY = ZoneInfo("America/New_York")
STANDING_LIMITS = (
    "Costs and financing are assumptions (practice quotes are not fills; no venue swap data).",
    "About 1.2 F001 signals a year and 12 F002 decisions a year: no conclusion is possible for decades (pre-registered power).",
    "The system runs only while this Mac is awake; there is no external watchdog.",
)


def week_bounds(any_day):
    """Monday 00:00 ET .. next Monday 00:00 ET of the week containing `any_day` (a date)."""
    mon = any_day - timedelta(days=any_day.weekday())
    a = datetime.combine(mon, time(0), tzinfo=NY)
    return a, a + timedelta(days=7)


def build(registry, cfg, week_day, now):
    a, b = week_bounds(week_day)
    inwk = lambda r: a <= datetime.fromisoformat(r["created_utc"]).astimezone(NY) < b
    tr = [r for r in registry.records("setup_transition") if inwk(r)]
    allstates = {}
    for r in registry.records("setup_transition"):
        allstates.setdefault(r["payload"]["setup_id"], []).append(r["payload"]["state"])
    touched = sorted({r["payload"]["setup_id"] for r in tr})
    evals = [r["payload"] for r in registry.records("evaluation") if inwk(r) and r["payload"].get("type") == "rule_signal"]
    outcomes = [r["payload"] for r in registry.records("outcome") if inwk(r)]
    notifs = {r["record_id"]: r for r in registry.records("notification")}
    dl = [r for r in registry.records("delivery") if inwk(r)]
    pfs = [r["payload"] for r in registry.records("preflight") if inwk(r)]
    gaps = [r["payload"] for r in registry.records("note") if inwk(r) and r["payload"].get("type") == "runner_gap"]
    scans = [r for r in registry.records("scan_run") if inwk(r)]
    L = ["# Weekly opportunity review: week of %s" % a.date().isoformat(), "",
         "_Generated %s from the forward registry. EXPERIMENTAL SHADOW SYSTEM: paper only; nothing here is validated, "
         "a trading signal or financial advice._" % LC.et(now), ""]
    trig = [r["payload"] for r in tr if r["payload"]["state"] == "triggered"]
    L += ["## 1. Meaningful opportunities", ""]
    L += ["- %s TRIGGERED (bar %s%s)" % (t["setup_id"], t.get("bar_date"), ", DETECTED LATE" if t.get("detected_late") else "") for t in trig] or ["- None this week."]
    L += ["", "## 2. Experimental ideas and their status (shadow forward test, NOT VALIDATED)", ""]
    if touched:
        L += ["| Setup | States this week | Current state |", "|---|---|---|"]
        L += ["| %s | %s | %s |" % (s, " → ".join(r["payload"]["state"] for r in tr if r["payload"]["setup_id"] == s),
                                    allstates[s][-1].upper()) for s in touched]
    else:
        L.append("No setup changed state this week.")
    kinds = {}
    for e in evals:
        kinds.setdefault(e["rule_id"], []).append(e["kind"])
    L += ["", "Rule evaluations this week: %s." % ("; ".join("%s %s" % (k, ", ".join(v)) for k, v in sorted(kinds.items())) or "none")]
    L += ["", "## 3. Approved paper signals", "", "None. No rule is approved for paper trading; F001 and F002 run only as shadow signals."]
    L += ["", "## 4. Resolved paper positions", ""]
    if outcomes:
        L += ["| Setup | Exit reason | Sub-ledger change, entry to exit (base costs, estimated financing) |", "|---|---|---|"]
        L += ["| %s | %s | %s |" % (o.get("setup_id"), o.get("exit_reason"),
                                    "%+.3f%%" % (100 * (o["equity_after"] / o["equity_at_entry"] - 1))
                                    if o.get("equity_after") and o.get("equity_at_entry") else "UNKNOWN") for o in outcomes]
    else:
        L.append("None this week.")
    bi = [r["payload"] for r in tr if r["payload"]["state"] in ("blocked", "invalidated", "expired")]
    L += ["", "## 5. Blocked, invalidated or expired setups", ""]
    L += ["- %s %s: %s" % (x["setup_id"], x["state"].upper(), "; ".join(x.get("reasons", [])) or x.get("reason", "")) for x in bi] or ["- None."]
    fails = [d for d in dl if d["payload"]["result"] in ("failed", "rejected", "unknown", "expired_unsent", "emergency_expired_unacknowledged")]
    L += ["", "## 6. Notification failures", ""]
    L += ["- %s: %s (%s, %s)" % (LC.et(d["created_utc"]), N.provider_status(registry, d["payload"]["notification_id"]),
                                  d["payload"]["channel"], (notifs.get(d["payload"]["notification_id"]) or {"payload": {}})["payload"].get("title", "?")[:70])
          for d in fails] or ["- None recorded."]
    sent = sum(1 for d in dl if d["payload"]["result"] == "sent")
    digest = sum(1 for d in dl if d["payload"]["result"] == "routed_to_digest")
    L.append("- Accepted by a provider this week: %d; logged for the digest instead of the phone: %d." % (sent, digest))
    L += ["", "## 7. Data quality and readiness", ""]
    bad = {}
    for p in pfs:
        for c in p["checks"]:
            if c["status"] in ("DEGRADED", "BLOCKED"):
                bad.setdefault("%s %s" % (c["check"], c["status"]), 0)
                bad["%s %s" % (c["check"], c["status"])] += 1
    L.append("- Scans: %d; readiness checks: %d (READY %d, DEGRADED %d, BLOCKED %d)." % (
        len(scans), len(pfs), sum(p["verdict"] == "READY" for p in pfs), sum(p["verdict"] == "DEGRADED" for p in pfs),
        sum(p["verdict"] == "BLOCKED" for p in pfs)))
    L += ["- %s: %d scan(s)" % (k, v) for k, v in sorted(bad.items())]
    L += ["- Runner gap of %.0f min from %s (%s)" % (g["minutes"], LC.et(g["from_utc"]), g["likely_cause"]) for g in gaps]
    rel = [n["payload"] for n in notifs.values() if inwk(n) and (n["payload"].get("fields") or {}).get("class") == "OFFICIAL RELEASE"]
    mof = [r["payload"] for r in registry.records("market_watch") if inwk(r) and r["payload"].get("condition") == "W004" and r["payload"].get("alerted")]
    L += ["", "## 8. Significant official events (published; no interpretation)", ""]
    L += ["- %s (%s)" % (p["title"], p["fields"].get("event_time_et")) for p in rel]
    L += ["- MoF intervention release: %s (%s)" % (m.get("release"), m.get("period")) for m in mof]
    if not rel and not mof:
        L.append("- None alerted this week.")
    L += ["", "## 9. Expected vs observed", ""]
    if outcomes:
        for o in outcomes:
            L.append("- %s: planned exits (invalidation / target / expiry) vs actual: %s." % (o.get("setup_id"), o.get("exit_reason")))
    else:
        L.append("- No position resolved, so there is nothing to compare.")
    n_res = len(registry.records("outcome"))
    L.append("- Resolved signals to date: %d. Fewer than 30: **no statistical conclusion is possible**, and no parameter is changed "
             "on the basis of a few prospective observations." % n_res)
    L += ["", "## 10. Lessons and unresolved limitations", ""]
    if gaps:
        L.append("- The runner missed scheduled runs while the Mac slept (%d gap(s)); keep it on AC power." % len(gaps))
    if any(d["payload"]["result"] == "emergency_expired_unacknowledged" for d in dl):
        L.append("- A HIGH alert expired without acknowledgement.")
    L += ["- %s" % s for s in STANDING_LIMITS]
    return a.date().isoformat(), "\n".join(L) + "\n"


def due(state, now):
    """Generate the previous week's review once, at the first run on Saturday 12:00 ET or later (FX closed)."""
    ny = now.astimezone(NY)
    if ny.weekday() != 5 or ny.hour < 12:
        return None
    wk = week_bounds(ny.date())[0].date().isoformat()
    return None if state.get("last_weekly_review") == wk else ny.date()
