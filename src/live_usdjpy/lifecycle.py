r"""Setup lifecycle and alert records for the USD/JPY forward system (master prompt step 5, 2026-10-29).

A setup has a persistent ID (e.g. "F001-2026-11-02", "F002-2026-10") and moves through:
  detected -> watching -> triggered -> blocked -> entered -> exited -> resolved
                                  \-> invalidated / expired
Each (setup, state) is recorded at most once (idempotency key "setup:<id>:<state>"), so re-runs and repeated scans
never spam. Alerts are queued only on meaningful transitions (ALERT_ON); the notifier (step 6) delivers them.
Every alert carries the full field set; anything not known is the literal string UNKNOWN. All times are ET.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
STATES = ("detected", "watching", "triggered", "blocked", "invalidated", "expired", "entered", "exited", "resolved")
TERMINAL = ("invalidated", "expired", "resolved")
ALLOWED = {None: {"detected", "watching", "triggered"}, "detected": {"watching", "triggered", "expired"},
           "watching": {"triggered", "expired"}, "triggered": {"blocked", "entered", "invalidated", "expired"},
           "blocked": {"entered", "invalidated", "expired"}, "entered": {"exited"}, "exited": {"resolved"},
           "invalidated": set(), "expired": set(), "resolved": set()}
# state -> priority of the alert queued on entering it (None = record only, no alert)
ALERT_ON = {"watching": "LOW", "triggered": "NORMAL", "blocked": "LOW", "invalidated": "NORMAL", "expired": "LOW",
            "entered": "NORMAL", "exited": "NORMAL", "resolved": "LOW", "detected": None}

ALERT_FIELDS = ("market", "instrument", "class", "setup_id", "rule_version", "event_time_et", "quote_time_et",
                "reference_price", "price_label", "session", "direction", "trigger", "invalidation", "target_or_exit",
                "size", "max_planned_loss", "estimated_costs", "relevant_events", "evidence_for", "evidence_against",
                "validation_status", "expiry", "why_sent")


def et(ts):
    if not ts:
        return "UNKNOWN"
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    return ts.astimezone(NY).strftime("%Y-%m-%d %H:%M ET")


FULL_CLASSES = ("EXPERIMENTAL IDEA (shadow ledger)", "APPROVED PAPER CANDIDATE")


def alert(priority, title, summary=None, **fields):
    """Alert payload. EXPERIMENTAL IDEA and APPROVED PAPER CANDIDATE alerts carry the full field list (a field that
    applies but is not known reads UNKNOWN). Every other class (RISK/SYSTEM ALERT, MARKET WATCH, PAPER POSITION
    UPDATE, TEST) carries only the fields that apply: those passed in, minus any marked "not applicable"; a field
    passed as None means "applies but unknown" and reads UNKNOWN. `summary` is the one-line lock-screen text."""
    cls = fields.get("class")
    na = lambda v: isinstance(v, str) and v.lower().startswith("not applicable")
    if cls in FULL_CLASSES:
        body = {k: (fields.get(k) if fields.get(k) not in (None, "") else "UNKNOWN") for k in ALERT_FIELDS}
    else:
        body = {k: (v if v not in (None, "") else "UNKNOWN") for k, v in fields.items() if k in ALERT_FIELDS and not na(v)}
    return {"status": "queued", "priority": priority, "title": title, "summary": summary, "fields": body}


def current(registry, setup_id):
    recs = [r for r in registry.records("setup_transition") if r["payload"]["setup_id"] == setup_id]
    return recs[-1]["payload"]["state"] if recs else None


def open_setups(registry):
    last = {}
    for r in registry.records("setup_transition"):
        last[r["payload"]["setup_id"]] = r["payload"]
    return {k: v for k, v in last.items() if v["state"] not in TERMINAL}


def transition(registry, setup_id, state, info, alert_fields=None, now=None, title=None):
    """Record a lifecycle transition (once per setup and state) and queue its alert. Returns True if new."""
    if state not in STATES:
        raise ValueError(state)
    prev = current(registry, setup_id)
    if prev == state:
        return False
    if state not in ALLOWED[prev]:
        raise ValueError("illegal transition %s -> %s for %s" % (prev, state, setup_id))
    now = now or datetime.now(timezone.utc)
    r = registry.append("setup_transition", {"setup_id": setup_id, "state": state, "from": prev, **info},
                        idem_key="setup:%s:%s" % (setup_id, state), now=now)
    if r["duplicate"]:
        return False
    pr = ALERT_ON.get(state)
    if pr and alert_fields is not None:
        f = dict(alert_fields)
        f["why_sent"] = f.get("why_sent") or "setup %s moved %s -> %s" % (setup_id, prev or "new", state)
        registry.append("notification", alert(pr, title or "%s %s" % (setup_id, state.upper()), **f),
                        idem_key="notif:setup:%s:%s" % (setup_id, state), now=now)
    return True
