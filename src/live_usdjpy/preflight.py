"""Market preflight and readiness check before every forward scan (next phase, Phase D, 2026-10-30).

OPERATING readiness only: is the plumbing able to observe, evaluate and paper-trade correctly right now? It says
nothing about market conditions or profitability and produces no score.

Verdict:
  READY      every required input is present and consistent
  DEGRADED   something non-essential is missing or doubtful (observation markets, clock offset, notification or
             backup health, a previous run error); scanning and paper workflows continue, the owner is told
  BLOCKED    a required input is missing: every action that depends on it fails closed (listed in `blocks`);
             safe observation and reporting continue

Capabilities that a BLOCKED check can switch off:
  rule_evaluation      F001/F002 evaluation is deferred (catch-up evaluates the bar later, labelled DETECTED LATE
                       if more than 30 minutes after completion); nothing is recorded as NO TRADE for missing data
  paper_entries        no new paper entry (added to the gate's reasons)
  position_monitoring  no exit decision on an open paper position (a stale or invalid price must never trigger a
                       paper exit); the position is reported as UNMONITORED and alerted
Market closure is not a fault: while FX is closed, entries are impossible anyway and the check reports INFO.
"""
from datetime import datetime, timedelta, timezone

import pandas as pd

from src import clock as K

from . import runner as RN
from .registry import verify_chain

ORDER = {"OK": 0, "INFO": 0, "DEGRADED": 1, "BLOCKED": 2}


def nyse_trading_day(d):
    return d.weekday() < 5 and d not in set(K.us_nyse_holidays(d.year))


def check(now, registry, snapshot, bars, events_store, state, cfg, fetch_error=None, kill_on=False,
          backup_problems=(), channels_configured=None, live_cfg=None):
    """Returns {"verdict", "blocks": [...], "checks": [{"check", "status", "detail", "blocks"}]}."""
    out = []

    def add(name, status, detail, blocks=()):
        out.append({"check": name, "status": status, "detail": detail, "blocks": list(blocks)})

    fx_open = K.fx_market_open(now)
    obs = {o["specialist"]: o for o in (snapshot or {}).get("observations", []) if o.get("role") == "primary"}

    # 1. sources responding / 2. quote timestamps
    if fetch_error or not snapshot:
        add("market data sources", "BLOCKED", "price or bar request failed: %s" % (fetch_error or "no snapshot"),
            ("rule_evaluation", "paper_entries", "position_monitoring"))
    else:
        uj = obs.get("usdjpy", {})
        fr = uj.get("freshness", "UNAVAILABLE")
        if uj.get("quote_problems"):
            add("USD/JPY quote", "BLOCKED", "invalid quote: %s" % ", ".join(uj["quote_problems"]), ("paper_entries", "position_monitoring"))
        elif fx_open and fr != "LIVE":
            add("USD/JPY quote", "BLOCKED", "USD/JPY price is %s while FX is open (%s)" % (fr, uj.get("freshness_note")),
                ("paper_entries", "position_monitoring"))
        elif not fx_open:
            add("USD/JPY quote", "INFO", "FX market closed; last price %s (entries impossible until the reopen)" % fr)
        else:
            add("USD/JPY quote", "OK", "LIVE, age %s s, spread %s pips" % (uj.get("age_s"), uj.get("spread_pips")))
        notes = [o.get("clock_note") for o in obs.values() if o.get("clock_note")]
        offs = [abs(o["server_clock_offset_s"]) for o in obs.values() if o.get("server_clock_offset_s") is not None]
        if notes or (offs and max(offs) > cfg["clock_offset_limit_s"]):
            add("clock", "DEGRADED", "; ".join(notes) or "local clock differs from the venue's by %.1f s" % max(offs))
        else:
            add("clock", "OK", "venue clock offset %s s" % (max(offs) if offs else "UNKNOWN"))
        for spec, name in (("gbpusd", "GBP/USD"), ("gold", "Gold (GLD)")):
            st_ = ((snapshot or {}).get("status") or {}).get(spec, "UNKNOWN")
            o = obs.get(spec, {})
            if st_ != "DATA OK" and o.get("session_open", True):
                add("%s data" % name, "DEGRADED", "%s (%s); observation only" % (st_, o.get("freshness")))

    # 3. required bars complete
    comp = RN.last_bar_completion(now)
    fx = (bars or {}).get("USD_JPY")
    spy = (bars or {}).get("SPY")
    if bars is not None and comp is not None:
        last_fx = fx.index[-1].date() if fx is not None and len(fx) else None
        want = comp.date()
        if last_fx is None:
            add("USD/JPY daily bars", "BLOCKED", "no completed USD/JPY bars", ("rule_evaluation",))
        elif last_fx < want:
            late = now - comp > RN.BAR_WAIT
            add("USD/JPY daily bars", "DEGRADED" if not late else "BLOCKED",
                "latest completed bar %s; the %s bar completed at 17:00 ET and is not available yet" % (last_fx, want),
                () if not late else ("rule_evaluation",))
        else:
            add("USD/JPY daily bars", "OK", "latest completed bar %s" % last_fx)
        if last_fx is not None and nyse_trading_day(last_fx):
            spy_ok = spy is not None and pd.Timestamp(last_fx) in spy.index
            if not spy_ok:
                add("SPY daily bars", "BLOCKED", "no SPY bar for %s although NYSE traded that day: F001 evaluation deferred "
                    "(it would otherwise be recorded as NO TRADE for a data gap)" % last_fx, ("rule_evaluation",))
            else:
                add("SPY daily bars", "OK", "SPY bar for %s present" % last_fx)

    # 4. calendars and instrument hours
    try:
        hol = set(K.jp_bank_holidays(now.year)) | set(K.us_nyse_holidays(now.year))
        add("calendars", "OK" if hol else "DEGRADED", "FX %s; %d holidays known for %d" % (
            "open" if fx_open else "closed", len(hol), now.year))
    except Exception as ex:
        add("calendars", "BLOCKED", "market calendar error: %s" % type(ex).__name__, ("paper_entries",))

    # 5. event monitor
    gen = (events_store or {}).get("generated_utc")
    if not gen:
        add("event monitor", "BLOCKED", "event store missing: blackout windows cannot be checked", ("paper_entries",))
    else:
        age_h = (now - datetime.fromisoformat(gen)).total_seconds() / 3600
        if age_h > cfg["events_max_age_hours"]:
            add("event monitor", "BLOCKED", "event store %.0f h old (limit %d h): blackout windows unknown" % (
                age_h, cfg["events_max_age_hours"]), ("paper_entries",))
        else:
            add("event monitor", "OK", "updated %.1f h ago" % age_h)

    # 6. risk engine
    try:
        from . import gate as G
        rs = G.current_state(registry) or {"state": "ACTIVE"}
        if kill_on:
            add("risk engine", "BLOCKED", "kill switch ON", ("paper_entries",))
        elif rs["state"] != "ACTIVE":
            add("risk engine", "BLOCKED" if rs["state"] == "HALTED" else "DEGRADED", "trading state %s: %s" % (
                rs["state"], "; ".join(rs.get("why", []))), ("paper_entries",))
        else:
            add("risk engine", "OK", "state ACTIVE")
    except Exception as ex:
        add("risk engine", "BLOCKED", "risk state unreadable: %s" % type(ex).__name__, ("paper_entries",))

    # 7. registry writable and consistent
    try:
        broken = verify_chain(registry.db)
        registry.db.execute("BEGIN IMMEDIATE")
        registry.db.execute("ROLLBACK")
        if broken:
            add("registry", "BLOCKED", "hash chain broken: %s" % broken, ("rule_evaluation", "paper_entries"))
        else:
            add("registry", "OK", "writable; chain intact (%d records)" % registry.count())
    except Exception as ex:
        add("registry", "BLOCKED", "registry not writable: %s" % type(ex).__name__, ("rule_evaluation", "paper_entries"))

    # 8. previous run / reconciliation
    rec = registry.records("reconciliation")
    if rec and not rec[-1]["payload"].get("ok"):
        add("reconciliation", "BLOCKED", "last reconciliation failed", ("paper_entries",))
    if (state or {}).get("last_error"):
        add("previous run", "DEGRADED", "previous run ended with an error: %s" % state["last_error"])

    # 9. notification delivery
    if channels_configured is not None and not channels_configured:
        add("notifications", "DEGRADED", "no phone channel configured")
    else:
        stuck = _stuck(registry, now, cfg["notification_stuck_minutes"])
        add("notifications", "DEGRADED" if stuck else "OK",
            "%d notification(s) not accepted by any provider after %d min" % (stuck, cfg["notification_stuck_minutes"])
            if stuck else "outbox clear")

    # 9b. financing rates (owner decision 2026-11-01: DEGRADED only; financing never blocks anything)
    if live_cfg and live_cfg.get("financing", {}).get("policy") != "legacy":
        from . import financing as FIN
        st_ = FIN.series_status((state or {}).get("financing"), now, live_cfg)
        bad_ = ["%s %s%s" % (r["series"], r["state"], " (last fetch failed: %s)" % r["last_error"] if r.get("last_error") else "")
                for r in st_.values() if r["state"] not in ("VALID", "VALID_ZERO") or r.get("last_error")]
        pend = sum(len(__import__("src.live_usdjpy.paper", fromlist=["x"]).unresolved(registry, rule)) for rule in live_cfg["rules"])
        if pend:
            bad_.append("%d UNRESOLVED financing roll(s) awaiting TRUE-UP" % pend)
        add("financing rates", "DEGRADED" if bad_ else "OK", "; ".join(bad_) if bad_ else
            "; ".join("%s %s (%s, age %s)" % (r["series"], r["state"], r["obs_date"], r["age"]) for r in st_.values()))

    # 10. backup health
    if backup_problems:
        add("backup", "DEGRADED", "; ".join(t for _, t in backup_problems))
    else:
        add("backup", "OK", "snapshot and off-site copy within limits")

    worst = max((ORDER[c["status"]] for c in out), default=0)
    verdict = {0: "READY", 1: "DEGRADED", 2: "BLOCKED"}[worst]
    blocks = sorted({b for c in out for b in c["blocks"]})
    return {"verdict": verdict, "blocks": blocks, "checks": out, "at_utc": now.astimezone(timezone.utc).isoformat()}


def _stuck(registry, now, minutes, quiet=("22:00", "07:00")):
    """Notifications no provider has accepted `minutes` after they became sendable (HIGH at once; LOW/NORMAL after
    quiet hours end), within the last 2 days."""
    from zoneinfo import ZoneInfo
    ny_tz = ZoneInfo("America/New_York")
    q0, q1 = (tuple(int(x) for x in t.split(":")) for t in quiet)
    sent = {d["payload"]["notification_id"] for d in registry.records("delivery")
            if d["payload"]["result"] in ("sent", "delivered_confirmed_by_owner", "acknowledged")}
    n = 0
    for r in registry.records("notification"):
        p = r["payload"]
        if r["record_id"] in sent:
            continue
        start = datetime.fromisoformat(r["created_utc"])
        if p.get("priority") != "HIGH":
            ny = start.astimezone(ny_tz)
            hm = (ny.hour, ny.minute)
            if hm >= q0 or hm < q1:                                   # created in quiet hours: sendable at 07:00 ET
                day = ny.date() + timedelta(days=1) if hm >= q0 else ny.date()
                start = datetime(day.year, day.month, day.day, q1[0], q1[1], tzinfo=ny_tz)
        if timedelta(minutes=minutes) < now - start and now - start < timedelta(days=2):
            n += 1
    return n


def summary(pf):
    """Compact text: verdict plus the reasons that aren't OK."""
    bad = [c for c in pf["checks"] if c["status"] in ("DEGRADED", "BLOCKED")]
    s = pf["verdict"]
    if bad:
        s += ": " + "; ".join("%s %s (%s)" % (c["check"], c["status"], c["detail"]) for c in bad)
    if pf["blocks"]:
        s += " | fail-closed: %s" % ", ".join(pf["blocks"])
    return s


NOT_ALERTED_HERE = ("backup", "previous run")                # these have their own HIGH alerts (no duplicates)


def record(registry, now, pf, cfg, slot_key):
    """Store the preflight result and alert only when a problem persists `alert_after_consecutive` scans:
    BLOCKED -> HIGH, DEGRADED -> NORMAL; one alert per problem set per New York day; a recovery notice (NORMAL) when
    an alerted problem clears. Returns the alert title queued, if any."""
    from zoneinfo import ZoneInfo
    from . import lifecycle as LC
    ny = now.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    bad = sorted({c["check"] for c in pf["checks"] if c["status"] in ("DEGRADED", "BLOCKED") and c["check"] not in NOT_ALERTED_HERE})
    level = "BLOCKED" if any(c["status"] == "BLOCKED" for c in pf["checks"] if c["check"] in bad) else ("DEGRADED" if bad else "READY")
    prev = [r["payload"] for r in registry.records("preflight")][-(cfg["alert_after_consecutive"] - 1 or 1):]
    persists = bad and len(prev) >= cfg["alert_after_consecutive"] - 1 and all(set(p_.get("alert_checks", [])) & set(bad) for p_ in prev)
    title = None
    if persists:
        text = "; ".join("%s: %s" % (c["check"], c["detail"]) for c in pf["checks"] if c["check"] in bad)
        title = "MONITORING %s: %s" % (level, ", ".join(bad))
        r = registry.append("notification", LC.alert(
            "HIGH" if level == "BLOCKED" else "NORMAL", title,
            **{"class": "RISK/SYSTEM ALERT" if level == "BLOCKED" else "MONITORING STATUS", "event_time_et": LC.et(now),
               "why_sent": text[:600] + (" | fail-closed: %s" % ", ".join(pf["blocks"]) if pf["blocks"] else "")}),
            idem_key="preflight:%s:%s:%s" % (level, ",".join(bad), ny), now=now)
        if r["duplicate"]:
            title = None
    alerted_before = any(p_.get("alerted") for p_ in prev[-1:])
    if level == "READY" and alerted_before:
        title = "MONITORING RECOVERED: all preflight checks OK"
        registry.append("notification", LC.alert("NORMAL", title, **{"class": "MONITORING STATUS", "event_time_et": LC.et(now),
                                                                     "why_sent": "previous problem cleared"}),
                        idem_key="preflight:recovered:%s" % now.isoformat(), now=now)
    registry.append("preflight", dict(pf, alert_checks=bad, alerted=bool(persists) or (alerted_before and level != "READY")),
                    idem_key="preflight:%s" % slot_key, now=now)
    return title
