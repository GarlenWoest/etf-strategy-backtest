"""Eligibility gate, risk gate and kill switch for the USD/JPY forward system (master prompt step 4, 2026-10-29).

Deterministic, plain Python. The gate can only BLOCK or SHRINK a candidate, never create or enlarge one. It returns
ALL reasons, not only the first. Limits come from config.yaml live_usdjpy (owner-approved 2026-10-29).

Trading states (persisted in the registry as `risk_state` records; the latest one is current):
  ACTIVE    new entries allowed (subject to every check)
  REDUCING  no new entries until the next New York trading day; exits continue (daily loss limit hit)
  HALTED    no new entries until a MANUAL resume (kill switch, drawdown <= -3%, integrity failure)
            at drawdown <= -5% the state is HALTED with close_all=True and experiment_stopped=True

Check labels:
  OPERATIONAL  mandatory safety rules (stale data, closed market, exposure, kill switch, invalid input)
  GUARD        "conservative temporary guard" timing restrictions, each with its rationale
"""
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from src import clock as K

NY = ZoneInfo("America/New_York")
TOKYO = ZoneInfo("Asia/Tokyo")
ALLOWED_PAPER_INSTRUMENTS = ("USDJPY",)       # gold and GBP/USD: observation / monitoring only (owner 2026-10-29)
HIGH_IMPACT = ("FOMC", "Employment Situation", "Consumer Price Index", "GDP", "Personal Income and Outlays",
               "BoJ Monetary Policy Meeting", "Monetary Policy")
STATES = ("ACTIVE", "REDUCING", "HALTED")


@dataclass
class Candidate:
    rule_id: str
    version: str
    instrument: str
    direction: int                     # +1 long, -1 short
    entry_ref: float                   # indicative reference price at the scan
    invalidation: float
    target: float = None
    expiry: str = None
    setup_id: str = ""
    mode: str = "shadow"               # "shadow" (forward test ledger) or "approved_paper" (separately approved rules)


@dataclass
class MarketView:
    now: datetime                      # aware
    price_freshness: str               # LIVE / DELAYED / CLOSED_LAST_PRICE / STALE / UNAVAILABLE
    price_age_s: float
    specialist_status: str             # DATA OK / STALE MARKET DATA / INSUFFICIENT DATA
    events: list = field(default_factory=list)          # event-monitor records
    mof_intervention_recent: object = None              # True / False / None (= UNKNOWN)
    preflight: list = field(default_factory=list)       # Phase D: reasons a required input is missing (fail closed)


@dataclass
class Book:
    equity: float
    peak_equity: float
    day_start_equity: float
    positions: dict = field(default_factory=dict)       # rule_id -> signed exposure as a multiple of equity


@dataclass
class Decision:
    status: str                        # APPROVED / SHRUNK / BLOCKED
    size_x: float
    reasons: list
    state: str
    notes: list = field(default_factory=list)

    def as_dict(self):
        return {"status": self.status, "size_x": self.size_x, "reasons": self.reasons, "state": self.state,
                "notes": self.notes}


def kill_flag_path(base):
    return Path(base) / "KILL_SWITCH"


def blackout_reasons(view, lim):
    """Scheduled high-impact events inside [now - after, now + before]; BoJ statements without a published time
    block the whole Tokyo calendar day of the meeting's last day."""
    out = []
    before, after = timedelta(minutes=lim["before"]), timedelta(minutes=lim["after"])
    tokyo_today = view.now.astimezone(TOKYO).date()
    for e in view.events:
        title = e.get("title", "")
        if not any(k.lower() in title.lower() for k in HIGH_IMPACT):
            continue
        if e.get("scheduled_time_utc"):
            t = datetime.fromisoformat(e["scheduled_time_utc"])
            if t - before <= view.now <= t + after:
                out.append("OPERATIONAL event blackout: %s at %s ET" % (title, t.astimezone(NY).strftime("%Y-%m-%d %H:%M")))
        elif e.get("scheduled_date") and str(e["scheduled_date"]) == tokyo_today.isoformat() and "BoJ" in title:
            out.append("OPERATIONAL event blackout: %s today (Tokyo date %s; statement time not published)" % (title, tokyo_today))
    return out


def eligibility(c, view, cfg, approved_paper_rules=()):
    """All eligibility reasons (empty list = eligible)."""
    r = ["OPERATIONAL preflight BLOCKED: %s" % x for x in getattr(view, "preflight", [])]
    if c.instrument not in ALLOWED_PAPER_INSTRUMENTS:
        r.append("OPERATIONAL invalid instrument %s: only %s is eligible for paper workflows" % (c.instrument, ALLOWED_PAPER_INSTRUMENTS))
    if c.mode == "approved_paper" and c.rule_id not in approved_paper_rules:
        r.append("OPERATIONAL rule %s v%s is not an approved paper rule (it may only run as a shadow signal)" % (c.rule_id, c.version))
    if c.direction not in (1, -1):
        r.append("OPERATIONAL invalid direction %r" % c.direction)
    if not c.entry_ref or c.entry_ref <= 0:
        r.append("OPERATIONAL missing entry reference price")
    elif c.direction == 1 and not c.invalidation < c.entry_ref or c.direction == -1 and not c.invalidation > c.entry_ref:
        r.append("OPERATIONAL invalidation level on the wrong side of the entry reference")
    if not K.fx_market_open(view.now):
        r.append("OPERATIONAL market closed (FX week runs Sun 17:00 to Fri 17:00 New York)")
    if view.price_freshness != "LIVE":
        r.append("OPERATIONAL stale data: USD/JPY price is %s (%.0f s old); entries need LIVE" % (view.price_freshness, view.price_age_s or -1))
    if view.specialist_status != "DATA OK":
        r.append("OPERATIONAL stale data: specialist status is %s" % view.specialist_status)
    r += blackout_reasons(view, cfg["risk_limits"]["event_blackout_minutes"])
    if view.mof_intervention_recent is True:
        r.append("GUARD recent MoF yen intervention (conservative temporary guard: managed-regime gap risk)")
    ny = view.now.astimezone(NY)
    if ny.weekday() == 4:
        r.append("GUARD no new entries on Fridays (conservative temporary guard: a once-daily scan cannot manage weekend gaps)")
    if time(17, 0) <= ny.time() < time(19, 0):
        r.append("GUARD thin hours 17:00-19:00 ET around the rollover (conservative temporary guard: spreads widen, 3 Jan 2019)")
    if ny.date() in K.jp_bank_holidays(ny.year) or view.now.astimezone(TOKYO).date() in K.jp_bank_holidays(view.now.astimezone(TOKYO).year):
        r.append("GUARD Japanese bank holiday (conservative temporary guard: thin yen liquidity)")
    return r


def derive_state(book, lim, prior_state, kill_on, now):
    """New trading state from the book and the persisted prior state. HALTED is sticky (manual resume only)."""
    dd = book.equity / book.peak_equity - 1 if book.peak_equity else 0.0
    day = book.equity / book.day_start_equity - 1 if book.day_start_equity else 0.0
    info = {"drawdown": dd, "daily_pnl": day, "close_all": False, "experiment_stopped": False, "why": []}
    if kill_on:
        info["why"].append("kill switch is on")
    if dd <= lim["drawdown_close_all_stop"]:
        info.update(close_all=True, experiment_stopped=True)
        info["why"].append("drawdown %.2f%% <= %.0f%%: close everything and stop the experiment" % (100 * dd, 100 * lim["drawdown_close_all_stop"]))
    elif dd <= lim["drawdown_halt_review"]:
        info["why"].append("drawdown %.2f%% <= %.0f%%: halt new entries for review" % (100 * dd, 100 * lim["drawdown_halt_review"]))
    if info["why"] or (prior_state or {}).get("state") == "HALTED":
        if not info["why"]:
            info["why"].append("HALTED earlier (%s); manual resume required" % "; ".join((prior_state or {}).get("why", [])))
        return "HALTED", info
    if day <= lim["daily_loss_stop_new_entries"]:
        info["why"].append("daily loss %.2f%% <= %.0f%%: no new entries until the next New York trading day" % (100 * day, 100 * lim["daily_loss_stop_new_entries"]))
        return "REDUCING", info
    if (prior_state or {}).get("state") == "REDUCING" and (prior_state or {}).get("ny_date") == now.astimezone(NY).date().isoformat():
        info["why"].append("REDUCING for the rest of %s" % prior_state["ny_date"])
        return "REDUCING", info
    return "ACTIVE", info


def risk(c, book, cfg, state, info):
    """Size the candidate (block or shrink only). Returns (size_x, reasons, notes)."""
    lim, sz = cfg["risk_limits"], cfg["sizing"]
    reasons, notes = [], []
    if state != "ACTIVE":
        reasons.append("OPERATIONAL trading state %s: %s" % (state, "; ".join(info["why"])))
    if c.rule_id in book.positions and book.positions[c.rule_id]:
        reasons.append("OPERATIONAL rule %s already has an open position (max 1 per rule)" % c.rule_id)
    if sum(1 for v in book.positions.values() if v) >= 2:
        reasons.append("OPERATIONAL 2 positions already open (max 2 in total)")
    dist = abs(c.entry_ref - c.invalidation) / c.entry_ref if c.entry_ref else 0
    want = min(sz["per_rule_max_x"], lim["risk_per_trade"] / dist) if dist > 0 else 0.0
    if dist > 0 and lim["risk_per_trade"] / dist < sz["per_rule_max_x"]:
        notes.append("sized by risk: %.2f%% of equity at the invalidation level" % (100 * lim["risk_per_trade"]))
    gross_now = sum(abs(v) for v in book.positions.values())
    room = max(0.0, lim["max_gross_x"] - gross_now)
    size = min(want, room)
    if size < want - 1e-12:
        notes.append("shrunk from %.3fx to %.3fx to stay within %.2fx gross" % (want, size, lim["max_gross_x"]))
    if size <= 1e-9 and not reasons:
        reasons.append("OPERATIONAL excess exposure: no room under the %.2fx gross limit" % lim["max_gross_x"])
    return size, reasons, notes


def decide(c, view, book, cfg, prior_state=None, kill_on=False, approved_paper_rules=()):
    elig = eligibility(c, view, cfg, approved_paper_rules)
    state, info = derive_state(book, cfg["risk_limits"], prior_state, kill_on, view.now)
    size, rreasons, notes = risk(c, book, cfg, state, info)
    reasons = elig + rreasons
    if reasons:
        return Decision("BLOCKED", 0.0, reasons, state, notes)
    full = min(cfg["sizing"]["per_rule_max_x"], cfg["risk_limits"]["risk_per_trade"] / (abs(c.entry_ref - c.invalidation) / c.entry_ref))
    return Decision("SHRUNK" if size < full - 1e-12 else "APPROVED", size, [], state, notes)


def kill(registry, base, reason, now=None):
    """Kill switch: create the flag file, record HALTED and queue a HIGH alert. Idempotent per minute."""
    now = now or datetime.now(timezone.utc)
    f = kill_flag_path(base)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("%s %s\n" % (now.isoformat(timespec="seconds"), reason))
    key = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M")
    with registry.transaction():
        registry.append("kill_switch", {"on": True, "reason": reason}, idem_key="kill:%s" % key, now=now)
        registry.append("risk_state", {"state": "HALTED", "why": ["kill switch: " + reason],
                                       "ny_date": now.astimezone(NY).date().isoformat()}, now=now)
        registry.append("notification", {"status": "queued", "priority": "HIGH", "class": "RISK/SYSTEM ALERT",
                                         "title": "KILL SWITCH ON: all new paper entries halted",
                                         "body": "Reason: %s. Resume only manually." % reason,
                                         "event_time_utc": now.isoformat(timespec="seconds")},
                        idem_key="notif:kill:%s" % key, now=now)
    return f


def resume(registry, base, confirm, now=None):
    """Manual re-enable only: removes the flag and records ACTIVE."""
    if confirm != "RESUME":
        raise ValueError("resume needs confirm='RESUME'")
    now = now or datetime.now(timezone.utc)
    kill_flag_path(base).unlink(missing_ok=True)
    registry.append("risk_state", {"state": "ACTIVE", "why": ["manual resume"],
                                   "ny_date": now.astimezone(NY).date().isoformat()}, now=now)


def current_state(registry, ledger=None):
    """Latest trading state that applies: global records (no ledger) and, if given, this sub-ledger's own records."""
    recs = [r for r in registry.records("risk_state") if r["payload"].get("ledger") in (None, ledger)]
    return recs[-1]["payload"] if recs else None
