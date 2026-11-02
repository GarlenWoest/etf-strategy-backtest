"""Alert presentation and notification policy (next phase, Phase E, 2026-10-30). Plain Python; no strategy change.

Level A, short phone alert (`phone_text`): line 1 is the lock-screen line "MARKET | CLASSIFICATION"; then, at most,
what happened, the direction (only when a rule supplies one), the key reason, whether any action is authorized, the
event time with a short status, and a pointer to the copy-ready ticket. Never the full field list.

Level B, copy-ready trade ticket (`build_ticket`): a fixed plain-text form for a specific setup, built only from
recorded values (the setup's rule signal, the gate decision, the paper position, the scan's recorded quote). A field
with no recorded value reads UNKNOWN or NOT APPLICABLE. A paper fill is labelled simulated, never executable. Every
ticket is stored as an immutable, versioned `ticket` record (version n+1 whenever the setup's state changes) and the
latest one per setup is printed in STATUS.md. No real-money trading is authorized by any ticket.

Notification policy (`route`): what reaches the phone and what is only logged for the daily digest.
  phone   HIGH and RISK/SYSTEM alerts (never suppressed or rate-limited); setup triggered / blocked / entered /
          exited / invalidated; paper-position updates; OFFICIAL RELEASE; MARKET WATCH W004 (MoF) and USD/JPY W001
          (big daily move); W005 data outage; TEST; the daily digest itself
  digest  setup watching / expired / resolved; W002 regime changes; W003 "event within 24 h"; gold and GBP/USD W001;
          anything beyond the daily cap of non-HIGH phone alerts; a repeat of a title already sent within the dedup
          window; a non-HIGH alert that could not be sent before it expired (e.g. after a long outage: never pushed
          stale)
Routing decisions are recorded as `delivery` records (result "routed_to_digest" or "expired_unsent", with the reason),
so nothing disappears silently and the digest can list them.
"""
import hashlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
MARKET_LABEL = {"USDJPY": "USD/JPY", "GOLD": "Gold (GLD)", "GBPUSD": "GBP/USD"}
CLASS_LABEL = {"EXPERIMENTAL IDEA (shadow ledger)": "EXPERIMENTAL SETUP", "APPROVED PAPER CANDIDATE": "APPROVED PAPER SETUP",
               "PAPER POSITION UPDATE": "PAPER POSITION", "MARKET WATCH": "MARKET WATCH", "OFFICIAL RELEASE": "OFFICIAL RELEASE",
               "RISK/SYSTEM ALERT": "SYSTEM ALERT", "TEST": "TEST"}
AUTH = {"EXPERIMENTAL SETUP": "WATCH ONLY. NOT VALIDATED. No real-money trade.",
        "PAPER POSITION": "SHADOW PAPER LEDGER ONLY (simulated). No real-money trade.",
        "APPROVED PAPER SETUP": "PAPER ONLY. No real-money trade.",
        "MARKET WATCH": "INFORMATION ONLY. No trade implied.",
        "OFFICIAL RELEASE": "INFORMATION ONLY. No interpretation.",
        "SYSTEM ALERT": "ACTION: check the system (see STATUS.md).",
        "TEST": "TEST. No action needed.", "DAILY DIGEST": "NOT A TRADING SIGNAL.",
        "MONITORING STATUS": "Monitoring status only; observation continues. See STATUS.md.",
        "WEEKLY REVIEW": "Review only. NOT A TRADING SIGNAL."}
PHONE_STATES = ("triggered", "blocked", "entered", "exited", "invalidated")
DIGEST_STATES = ("watching", "expired", "resolved", "detected")
NA = "NOT APPLICABLE"


def _cls(payload):
    if payload.get("kind") == "digest":
        return "DAILY DIGEST"
    f = payload.get("fields") or {}
    c = f.get("class") or payload.get("class")
    return CLASS_LABEL.get(c, c or "INFO")


def _short(s, n):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _state_of(payload):
    t = (payload.get("title") or "").upper()
    for st in ("TRIGGERED", "BLOCKED", "ENTERED", "EXITED", "INVALIDATED", "EXPIRED", "RESOLVED", "WATCHING"):
        if t.endswith(st) or (" %s" % st) in t:
            return st.lower()
    return None


def phone_text(payload, ticket_ref=None):
    """Level A: (title, body). Title = lock-screen line; body = at most six short lines."""
    if payload.get("kind") == "digest":
        return payload.get("title", "Daily digest")[:250], payload.get("body", "")[:1000]
    f = payload.get("fields") or {}
    cls = _cls(payload)
    if payload.get("priority") == "HIGH" or f.get("class") == "RISK/SYSTEM ALERT":
        cls = "SYSTEM ALERT" if cls not in ("PAPER POSITION",) else cls
    market = MARKET_LABEL.get(f.get("market"), f.get("market"))
    title = "%s | %s" % (market, cls) if market else cls
    lines = [_short(payload.get("title", ""), 110)]
    d = f.get("direction")
    if d and d not in ("none", "UNKNOWN") and not str(d).lower().startswith("not applicable"):
        lines.append("Direction: %s" % d)
    reason = f.get("trigger") if cls in ("EXPERIMENTAL SETUP", "APPROVED PAPER SETUP", "PAPER POSITION", "MARKET WATCH") else None
    reason = reason or f.get("why_sent") or f.get("relevant_events")
    if reason and reason != "UNKNOWN":
        lines.append(_short(reason, 140))
    if cls == "OFFICIAL RELEASE" and f.get("relevant_events"):
        lines[-1] = _short(f["relevant_events"], 160)
    lines.append(AUTH.get(cls, "INFORMATION ONLY."))
    st = _state_of(payload)
    when = f.get("event_time_et") or "UNKNOWN"
    lines.append("Event: %s%s" % (when, " | Status: %s" % st.upper() if st else ""))
    if ticket_ref:
        lines.append("Ticket: %s in STATUS.md" % ticket_ref)
    return title[:250], "\n".join(lines)[:1000]


def is_phone(payload):
    """Policy category (before dedup, cap and expiry)."""
    f = payload.get("fields") or {}
    if payload.get("priority") == "HIGH" or f.get("class") == "RISK/SYSTEM ALERT":
        return True, "HIGH / system alert"
    if payload.get("kind") == "digest":
        return True, "daily digest"
    c = f.get("class")
    if c == "OFFICIAL RELEASE" and f.get("market") not in (None, "USDJPY"):
        return False, "OFFICIAL RELEASE for an observation market: logged for the digest"
    if c in ("TEST", "OFFICIAL RELEASE", "PAPER POSITION UPDATE"):
        return True, c
    if c in ("EXPERIMENTAL IDEA (shadow ledger)", "APPROVED PAPER CANDIDATE"):
        st = _state_of(payload)
        return (st in PHONE_STATES or st is None), "setup %s" % (st or "update")
    if c == "MARKET WATCH":
        trig = str(f.get("trigger", ""))
        if trig.startswith("W004") or trig.startswith("W005"):
            return True, trig.split()[0]
        if trig.startswith("W001") and f.get("market") == "USDJPY":
            return True, "W001 USD/JPY"
        return False, "%s: logged for the digest" % (trig.split()[0] if trig else "market watch")
    return True, "unclassified (sent)"


def route(registry, rec, now, cfg, delivered_today):
    """('phone' | 'digest' | 'expired', reason) for a not-yet-handled notification record."""
    p = rec["payload"]
    phone, why = is_phone(p)
    high = p.get("priority") == "HIGH" or (p.get("fields") or {}).get("class") == "RISK/SYSTEM ALERT"
    if high:
        return "phone", why
    age = now - datetime.fromisoformat(rec["created_utc"])
    if age > timedelta(hours=cfg["expire_unsent_hours"]) and p.get("kind") != "digest":
        return "expired", "not sent within %d h (never pushed stale)" % cfg["expire_unsent_hours"]
    if not phone:
        return "digest", why
    if p.get("kind") == "digest" or (p.get("fields") or {}).get("class") == "TEST":
        return "phone", why
    since = now - timedelta(hours=cfg["dedup_hours"])
    for t, title in delivered_today:
        if title == p.get("title") and t >= since:
            return "digest", "same alert already sent at %s" % t.astimezone(NY).strftime("%H:%M ET")
    day = now.astimezone(NY).date()
    n_today = sum(1 for t, _ in delivered_today if t.astimezone(NY).date() == day)
    if n_today >= cfg["max_phone_alerts_per_day"]:
        return "digest", "daily cap of %d non-HIGH phone alerts reached" % cfg["max_phone_alerts_per_day"]
    return "phone", why


# ---------------------------------------------------------------- copy-ready trade tickets

TICKET_FIELDS = ("MARKET", "INSTRUMENT", "STRATEGY ID", "VALIDATION STATUS", "DIRECTION", "REFERENCE BID/ASK",
                 "QUOTE TIMESTAMP", "ENTRY TRIGGER", "ENTRY PRICE", "STOP / INVALIDATION", "TARGET / EXIT RULE",
                 "EXPIRATION", "POSITION SIZE", "MAXIMUM PLANNED LOSS", "ESTIMATED COSTS", "IMPORTANT NEWS",
                 "REASONS FOR", "REASONS AGAINST", "CURRENT STATUS", "ALLOWED ACTION")


def _fmt(v, d=3):
    return ("%%.%df" % d) % v if isinstance(v, (int, float)) and not isinstance(v, bool) else (v if v not in (None, "") else "UNKNOWN")


def _et(ts):
    if not ts:
        return "UNKNOWN"
    t = datetime.fromisoformat(ts) if isinstance(ts, str) else ts
    return t.astimezone(NY).strftime("%Y-%m-%d %H:%M:%S ET")


def build_ticket(registry, cfg, setup_id, evidence, now):
    """Plain-text ticket for `setup_id` from recorded values only. Returns (text, fields dict)."""
    from . import paper as PP
    trs = [r for r in registry.records("setup_transition") if r["payload"]["setup_id"] == setup_id]
    if not trs:
        raise ValueError("unknown setup %s" % setup_id)
    state = trs[-1]["payload"]["state"]
    trig = [r["payload"] for r in trs if r["payload"]["state"] == "triggered"]
    sig = (trig[0].get("signal") if trig else None) or {}
    rid = setup_id.split("-")[0]
    rcfg = cfg["rules"].get(rid, {})
    gates = [r["payload"] for r in registry.records("evaluation")
             if r["payload"].get("type") == "gate_decision" and r["payload"].get("setup_id") == setup_id]
    ms = registry.records("market_state")
    q = ((ms[-1]["payload"].get("quotes") or {}).get("usdjpy") or {}) if ms else {}
    pos = None
    led = PP.state(registry, rid, cfg) if rid in cfg["rules"] else None
    if led and led["position"] and led["position"]["setup_id"] == setup_id:
        pos = led["position"]
    intents = {r["payload"]["client_order_id"]: r["payload"].get("intent") for r in registry.records("order_event")
               if r["payload"].get("setup_id") == setup_id}
    fills = [dict(r["payload"], at_utc=r["created_utc"]) for r in registry.records("fill")
             if r["payload"].get("type") == "trade" and r["payload"].get("client_order_id") in intents]
    direction = {1: "LONG USD/JPY", -1: "SHORT USD/JPY"}.get(sig.get("direction"), NA)
    entry = [f_ for f_ in fills if intents[f_["client_order_id"]] == "entry"]
    exitf = [f_ for f_ in fills if intents[f_["client_order_id"]] == "exit"]
    if entry:
        e = entry[0]
        entry_txt = "%s simulated paper fill at %s (internal simulator: mid x (1 +/- %.3f%%); NOT an executable price)" % (
            _fmt(e.get("price")), _et(e.get("at_utc")), 100 * e.get("cost_rate", 0))
    else:
        entry_txt = "NOT ENTERED. Reference mid at the signal %s (indicative, not executable)" % _fmt(sig.get("entry_ref"))
    inv = sig.get("invalidation")
    tgt = sig.get("target")
    size_txt, loss_txt = NA + " (not entered)", NA + " (not entered)"
    if pos:
        n = pos.get("notional_usd")
        size_txt = "$%.2f notional in the $%d shadow sub-ledger (%.2fx); per $100: $%.2f" % (
            n, cfg["sizing"]["start_usd"], n / cfg["sizing"]["start_usd"], 100.0 * n / cfg["sizing"]["start_usd"])
        if inv and pos.get("entry_price"):
            loss = n * abs(pos["entry_price"] - inv) / pos["entry_price"]
            loss_txt = "about $%.2f if exited exactly at the invalidation level (planned %.2f%% of the sub-ledger); " \
                       "exits happen at scan prices, so gaps can lose more" % (loss, 100 * loss / cfg["sizing"]["start_usd"])
    elif gates and gates[-1].get("size_x") and gates[-1]["status"] in ("APPROVED", "SHRUNK"):
        size_txt = "%.2fx of the sub-ledger (gate %s)" % (gates[-1]["size_x"], gates[-1]["status"])
    status = state.upper()
    if gates and gates[-1]["status"] == "BLOCKED" and state in ("triggered", "blocked"):
        status += ": " + "; ".join(gates[-1].get("reasons", []))[:400]
    if exitf:
        status += " (exit fill %s at %s, simulated)" % (_fmt(exitf[-1].get("price")), _et(exitf[-1].get("at_utc")))
    late = " | DETECTED LATE (system was not running at bar completion)" if trig and trig[0].get("detected_late") else ""
    ev = evidence.get(rid, ("UNKNOWN", "UNKNOWN"))
    ba = "%s / %s (spread %s pips; OANDA practice quote, indicative, not executable)" % (
        _fmt(q.get("bid")), _fmt(q.get("ask")), _fmt(q.get("spread_pips"), 1)) if q.get("bid") else "UNKNOWN (not recorded in this scan)"
    fields = {
        "MARKET": "USD/JPY",
        "INSTRUMENT": "USD_JPY (OANDA practice, indicative)",
        "STRATEGY ID": "%s v%s (%s)" % (rid, rcfg.get("version", "UNKNOWN"), cfg["forward_trials"].get(rid, "").split(" v0.2")[0]),
        "VALIDATION STATUS": "EXPERIMENTAL: forward shadow test, NOT VALIDATED (fewer than 30 resolved signals)",
        "DIRECTION": direction,
        "REFERENCE BID/ASK": ba,
        "QUOTE TIMESTAMP": "%s (retrieved %s)" % (_et(q.get("source_ts_utc")), _et(q.get("retrieved_utc"))) if q else "UNKNOWN",
        "ENTRY TRIGGER": (sig.get("reason") or "UNKNOWN") + late,
        "ENTRY PRICE": entry_txt,
        "STOP / INVALIDATION": ("%s, checked at scans only: not a stop order, no guaranteed exit price" % _fmt(inv)) if inv else NA,
        "TARGET / EXIT RULE": "%s; %s" % ("target %s" % _fmt(tgt) if tgt else "no target", sig.get("expiry_rule") or "UNKNOWN"),
        "EXPIRATION": "entry window %d FX day(s) from detection; %s" % (
            cfg["entry_window_fx_days"].get(rid, 0), sig.get("expiry_rule") or "UNKNOWN"),
        "POSITION SIZE": size_txt,
        "MAXIMUM PLANNED LOSS": loss_txt,
        "ESTIMATED COSTS": "round trip %.3f%% of notional (base), %.3f%% (stress); financing estimated, unverified" % (
            200 * cfg["costs"]["base"]["one_way"], 200 * cfg["costs"]["stress"]["one_way"]),
        "IMPORTANT NEWS": _news(registry, now) or "none scheduled in the next 4 days (official calendars)",
        "REASONS FOR": ev[0],
        "REASONS AGAINST": ev[1],
        "CURRENT STATUS": status,
        "ALLOWED ACTION": "WATCH ONLY. The shadow paper ledger records it automatically. No real-money trading is authorized.",
    }
    head = "TRADE TICKET %s | %s" % (setup_id, _et(now))
    text = "\n".join([head] + ["%s: %s" % (k, fields[k]) for k in TICKET_FIELDS])
    return text, fields


def _news(registry, now):
    import json
    from pathlib import Path
    from src import PROJECT_ROOT
    p = PROJECT_ROOT / "live" / "events" / "events.json"
    try:
        evs = json.loads(p.read_text()).get("events", {}).values()
    except Exception:
        return None
    end = (now + timedelta(days=4)).date().isoformat()
    hi = ("FOMC", "Employment Situation", "Consumer Price Index", "GDP", "Personal Income", "BoJ Monetary Policy")
    sel = sorted((e for e in evs if e.get("status") == "SCHEDULED" and "usdjpy" in (e.get("markets_affected") or [])
                  and str(e.get("scheduled_date")) <= end and any(h.lower() in e.get("title", "").lower() for h in hi)),
                 key=lambda e: e.get("scheduled_time_utc") or str(e.get("scheduled_date")))
    return "; ".join("%s %s" % (e["title"], _et(e["scheduled_time_utc"]) if e.get("scheduled_time_utc")
                                else "%s (time not published)" % e.get("scheduled_date")) for e in sel[:4])


def record_ticket(registry, setup_id, text, fields, now):
    """Versioned, immutable ticket: a new version only when the setup's state or the content changes."""
    prev = [r["payload"] for r in registry.records("ticket") if r["payload"]["setup_id"] == setup_id]
    body = "\n".join(text.splitlines()[1:])                 # the header carries the build time; compare the content
    h = hashlib.sha256(body.encode()).hexdigest()
    if prev and prev[-1]["content_sha256"] == h:
        return prev[-1]["version"], False
    v = len(prev) + 1
    registry.append("ticket", {"setup_id": setup_id, "version": v, "state": fields["CURRENT STATUS"].split(":")[0].split(" ")[0],
                               "text": text, "fields": fields, "content_sha256": h},
                    idem_key="ticket:%s:v%d" % (setup_id, v), now=now)
    return v, True


def latest_ticket(registry, setup_id):
    t = [r["payload"] for r in registry.records("ticket") if r["payload"]["setup_id"] == setup_id]
    return t[-1] if t else None
