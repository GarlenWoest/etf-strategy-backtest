"""Scanner for the USD/JPY forward system (master prompt step 5, 2026-10-29). Plain Python; no LLM; no orders.

One scan = one database transaction:
  verify the registry chain -> market_state digest -> rules F001/F002 (evaluation records, incl. NO TRADE)
  -> setup lifecycle (triggered / blocked / watching / invalidated / expired) -> gate decisions
  -> MARKET WATCH W001-W005 -> scan_run summary.
A scan is keyed by its 5-minute slot ("scan:<UTC slot>"): re-running the same slot writes nothing. An exception or a
killed process leaves no partial scan. Inputs are passed in (ScanInputs); network fetching lives in
tools/usdjpy_pipeline.py, so scans are replayable on fixtures.
DEMO runs use a separate registry and are labelled DEMO; the forward registry starts at activation (step 9).
"""
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from src import clock as K

from . import gate as G
from . import lifecycle as LC
from . import paper as PP
from . import rules as RL
from . import watch as W

NY = ZoneInfo("America/New_York")
EVIDENCE = {
    "F001": ("Deleveraging-overshoot mechanism: carry unwinds when funding liquidity falls (FX002 Brunnermeier, Nagel & "
             "Pedersen 2008 [L2]); BIS Bulletin 90 (2024) [L1]: leveraged unwinds amplified the move, markets stabilised quickly",
             "Crashes cluster and unwinds can last days (FX002); FX010 lagged JPY coefficient insignificant (t 1.26); "
             "low prior; about 1.2 signals a year (2004-2023 count)"),
    "F002": ("Time-series momentum in diversified multi-market portfolios (S01, S02 [L0])",
             "Single-asset evidence weak (S04 Huang et al. [L0]); FX trend profits decayed by the early 1990s (FX007 [L1]); "
             "LOW-PRIOR CONTROL, not a candidate edge"),
}


@dataclass
class ScanInputs:
    snapshot: dict                         # live/intel/latest.json content
    bars: dict                             # symbol -> pandas Series of daily closes (may include incomplete bars)
    events_store: dict                     # live/events/events.json content
    mode: str = "forward"                  # "forward" or "demo"
    rates: dict = field(default_factory=dict)   # {"usd": (annual rate or None, info), "jpy": (...)} for financing
    fx_prefiltered: bool = False                 # True for OANDA candles: already complete-only (v0.3)


def completed(series, kind, now):
    """Only bars complete at `now`: FX (Yahoo) bar for date d after 00:00 UTC of d+1; NYSE bar after 16:15 ET of d."""
    if series is None or len(series) == 0:
        return series
    s = series.dropna()
    if kind == "complete":
        return s
    if kind == "fx":
        cut = now.astimezone(timezone.utc).date()                     # bars dated before today's UTC date
        return s[s.index.date < cut]
    ny = now.astimezone(NY)
    last_ok = ny.date() if (ny.hour, ny.minute) >= (16, 15) else ny.date() - timedelta(days=1)
    return s[s.index.date <= last_ok]


def fx_days_between(a, b):
    """FX trading days (Mon-Fri) after date a up to and including date b."""
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def eval_plan(registry, mode, fx, cfg):
    """Which (rule, bar date) pairs this scan evaluates (v0.3 start and catch-up rule):
    F001: every completed bar after the last evaluated one (the latest bar only on the very first scan);
    F002: the latest bar (due or not), plus the most recent month-end on or after f002_first_month_end that has
    no evaluation yet. Each pair is evaluated once (the evaluation's idempotency key)."""
    if fx is None or len(fx) == 0:
        return []
    dates = [x.date() for x in fx.index]
    latest = dates[-1]
    have = lambda rid, d: registry.get_by_key("eval:%s:%s:%s" % (mode, rid, d.isoformat())) is not None
    done1 = sorted(r["payload"]["bar_date"] for r in registry.records("evaluation")
                   if r["payload"].get("type") == "rule_signal" and r["payload"].get("rule_id") == "F001" and r["payload"].get("bar_date"))
    f1 = [d for d in dates if d.isoformat() > done1[-1]][-30:] if done1 else [latest]
    plan = [("F001", d) for d in f1 if not have("F001", d)]
    first = date.fromisoformat(cfg.get("f002_first_month_end", "1900-01-01"))
    ends = [d for d in dates if d >= first and RL.last_fx_weekday_of_month(d) == d and not have("F002", d)]
    if ends and ends[-1] != latest:
        plan.append(("F002", ends[-1]))
    if not have("F002", latest):
        plan.append(("F002", latest))
    return plan


def holidays_for(years):
    out = set()
    for y in years:
        out |= set(K.jp_bank_holidays(y)) | set(K.us_fed_holidays(y))
    return out


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


INSTRUMENT_LABEL = "USD_JPY (OANDA practice, indicative)"
BAR_SOURCES = {"USD_JPY": "OANDA practice daily mid candles (17:00 New York, complete only)",
               "GBP_USD": "OANDA practice daily mid candles (17:00 New York, complete only)",
               "SPY": "Alpaca IEX daily bars (raw)", "GLD": "Alpaca IEX daily bars (raw)"}
SPREAD_NOTE = ("Observed bid/ask spreads are recorded descriptively only (v0.3 amendment, section 1). The frozen cost "
               "model (0.015% one-way base, 0.030% stress) is unchanged and observed spreads are never substituted.")
QUOTE_KEYS = ("source", "symbol", "bid", "ask", "spread", "spread_pips", "source_ts_utc", "retrieved_utc", "request_utc",
              "age_s", "freshness", "freshness_note", "clock_note", "server_clock_offset_s", "quote_problems", "tradeable",
              "quote_bid", "quote_ask", "quote_ts_utc")


def _bars(bars, key, legacy):
    """Bars by the v0.3 source symbol; the Yahoo-era key is still accepted from older callers and fixtures."""
    return bars.get(key) if bars.get(key) is not None else bars.get(legacy)


def quote_record(o):
    """The observed quote as stored in market_state: quote time, retrieval time, source, bid, ask, spread, freshness
    and every missing or invalid field named explicitly."""
    q = {k: o.get(k) for k in QUOTE_KEYS if k in o}
    q["missing"] = [k for k in ("bid", "ask", "source_ts_utc", "retrieved_utc") if o.get(k) is None]
    return q


def run_scan(registry, now, inp, cfg, base_dir, slot=None):
    slot = slot or now.astimezone(timezone.utc).replace(minute=now.minute - now.minute % 5, second=0, microsecond=0)
    key = "scan:%s:%s" % (inp.mode, slot.strftime("%Y%m%dT%H%MZ"))
    if registry.get_by_key(key):
        return {"duplicate": True, "key": key}
    broken = registry.verify()
    if broken:
        with registry.transaction():
            registry.append("risk_state", {"state": "HALTED", "why": ["registry chain broken: " + broken],
                                           "ny_date": now.astimezone(NY).date().isoformat()}, now=now)
            registry.append("notification", LC.alert("HIGH", "REGISTRY INTEGRITY FAILURE: scanning halted",
                                                     **{"class": "RISK/SYSTEM ALERT", "event_time_et": LC.et(now),
                                                        "why_sent": broken}), now=now)
        return {"halted": broken}
    rules_cfg = cfg["rules"]
    obs = {o["specialist"]: o for o in inp.snapshot.get("observations", []) if o.get("role") == "primary"}
    uj = obs.get("usdjpy", {})
    fxk = "complete" if inp.fx_prefiltered else "fx"
    fx = completed(_bars(inp.bars, "USD_JPY", "JPY=X"), fxk, now)
    spy = completed(inp.bars.get("SPY"), "nyse", now)
    watch_bars = {"USDJPY": fx, "GOLD": completed(inp.bars.get("GLD"), "nyse", now),
                  "GBPUSD": completed(_bars(inp.bars, "GBP_USD", "GBPUSD=X"), fxk, now)}
    events = list((inp.events_store.get("events") or {}).values())
    hol = holidays_for({now.year - 1, now.year})
    view = G.MarketView(now=now, price_freshness=uj.get("freshness", "UNAVAILABLE"), price_age_s=uj.get("age_s") or -1,
                        specialist_status=(inp.snapshot.get("status") or {}).get("usdjpy", "UNKNOWN"), events=events,
                        mof_intervention_recent=None)
    summary = {"mode": inp.mode, "evaluations": [], "transitions": [], "gate": [], "watch": 0}
    with registry.transaction():
        state_rec = {"label": "DEMO" if inp.mode == "demo" else "FORWARD", "snapshot_generated_utc": inp.snapshot.get("generated_utc"),
                     "usdjpy": {k: uj.get(k) for k in ("last", "source_ts_utc", "retrieved_utc", "freshness", "age_s", "session_open")},
                     "status": inp.snapshot.get("status"),
                     "bars": {s: {"last_date": (b.index[-1].date().isoformat() if b is not None and len(b) else None),
                                  "last_close": (float(b.iloc[-1]) if b is not None and len(b) else None), "n": (len(b) if b is not None else 0)}
                              for s, b in (("USD_JPY", fx), ("SPY", spy), ("GLD", watch_bars["GOLD"]), ("GBP_USD", watch_bars["GBPUSD"]))},
                     "bar_sources": BAR_SOURCES,
                     "quotes": {spec: quote_record(o) for spec, o in obs.items()},
                     "spread_note": SPREAD_NOTE,
                     "events_generated_utc": inp.events_store.get("generated_utc"),
                     "usdjpy_sma20": (float(fx.iloc[-20:].mean()) if fx is not None and len(fx) >= 20 else None),
                     "usdjpy_sessions": (inp.snapshot.get("clock") or {}).get("active_sessions")}
        state_rec["inputs_sha256"] = digest(state_rec)
        registry.append("market_state", state_rec, now=now)
        kill_on = G.kill_flag_path(base_dir).exists()
        slot_s = slot.strftime("%Y%m%dT%H%MZ")
        evals = []                                                   # (rule, signal, detected_late)
        for rid, d in eval_plan(registry, inp.mode, fx, cfg):
            fx_d = fx.loc[:pd.Timestamp(d)] if fx is not None else pd.Series(dtype=float)
            spy_d = spy.loc[:pd.Timestamp(d)] if spy is not None else pd.Series(dtype=float)
            sig = RL.RULES[rid](RL.RuleInputs(fx=fx_d, spy=spy_d, live_price=uj.get("last"), events=events, holidays=hol), rules_cfg[rid])
            done_at = datetime.combine(d, time(17, 0), tzinfo=NY)
            evals.append((rid, sig, (now - done_at) > timedelta(minutes=cfg.get("late_detection_minutes", 30))))
        S_mark = uj.get("last")
        f2m = [s_ for r_, s_, _ in evals if r_ == "F002" and s_.kind in ("CANDIDATE", "NO_TRADE") and s_.setup_id]
        new_f002_bar = f2m[-1].bar_date if f2m else None
        ledger_risk = PP.manage(registry, cfg, now, S_mark, inp.rates, slot_s, new_f002_bar) if S_mark else {}
        summary["paper"] = {r: v[0] for r, v in ledger_risk.items()}
        for rid, (st_, info) in ledger_risk.items():
            if st_ == "HALTED" and (G.current_state(registry, rid) or {}).get("state") != "HALTED":
                registry.append("risk_state", {"state": "HALTED", "ledger": rid, "why": info["why"],
                                               "ny_date": now.astimezone(NY).date().isoformat()}, now=now)
                registry.append("notification", LC.alert("HIGH", "%s sub-ledger HALTED: %s" % (rid, "; ".join(info["why"])),
                                                         **{"class": "RISK/SYSTEM ALERT", "event_time_et": LC.et(now),
                                                            "why_sent": "pre-registered risk limit"}), now=now)
        for rid, sig, late in evals:
            p = rules_cfg[rid]
            late_txt = " | DETECTED LATE (system was not running at bar completion %s 17:00 ET)" % sig.bar_date if late else ""
            ev = registry.append("evaluation", {"type": "rule_signal", **sig.as_dict(), "inputs_sha256": state_rec["inputs_sha256"],
                                                "detected_late": late, "detected_utc": now.astimezone(timezone.utc).isoformat()},
                                 idem_key="eval:%s:%s:%s" % (inp.mode, rid, sig.bar_date), now=now)
            summary["evaluations"].append((rid, sig.kind, ev["duplicate"]))
            fields = dict(market="USDJPY", instrument=INSTRUMENT_LABEL, setup_id=sig.setup_id, rule_version="%s v%s" % (rid, sig.version),
                          event_time_et="bar %s" % sig.bar_date, quote_time_et=LC.et(uj.get("source_ts_utc")),
                          reference_price=sig.entry_ref, price_label="%s (indicative, not executable)" % uj.get("freshness", "UNKNOWN"),
                          session=", ".join((inp.snapshot.get("clock") or {}).get("active_sessions", []) or []) or "none open",
                          direction={1: "LONG USD/JPY", -1: "SHORT USD/JPY"}.get(sig.direction, "none"), trigger=sig.reason + late_txt,
                          invalidation=sig.invalidation, target_or_exit="target %s; %s" % (sig.target if sig.target else "none", sig.expiry_rule),
                          estimated_costs="round trip %.3f%% of notional (base, unverified) + financing (estimated, unverified)"
                                          % (200 * cfg["costs"]["base"]["one_way"]),
                          relevant_events="; ".join("%s %s" % (e["title"], LC.et(e.get("scheduled_time_utc")) if e.get("scheduled_time_utc") else e.get("scheduled_date"))
                                                    for e in sorted(events, key=lambda e: e.get("scheduled_time_utc") or str(e.get("scheduled_date")))
                                                    if e.get("status") == "SCHEDULED" and str(e.get("scheduled_date")) <= (now + timedelta(days=4)).date().isoformat()) or "none scheduled",
                          evidence_for=EVIDENCE[rid][0], evidence_against=EVIDENCE[rid][1],
                          validation_status="FORWARD TEST %s: EXPERIMENTAL, NOT VALIDATED%s" % (rid, " (DEMO RUN)" if inp.mode == "demo" else ""),
                          expiry=sig.expiry_rule, **{"class": "EXPERIMENTAL IDEA (shadow ledger)"})
            if sig.kind == "WATCHING" and LC.current(registry, sig.setup_id) is None:
                if LC.transition(registry, sig.setup_id, "watching", {"bar_date": sig.bar_date, "reason": sig.reason}, fields, now):
                    summary["transitions"].append((sig.setup_id, "watching"))
            if sig.kind == "CANDIDATE" and LC.current(registry, sig.setup_id) in (None, "detected", "watching"):
                LC.transition(registry, sig.setup_id, "triggered", {"bar_date": sig.bar_date, "signal": sig.as_dict(), "detected_late": late,
                              "detected_ny_date": now.astimezone(NY).date().isoformat()}, fields, now,
                              title=("DETECTED LATE: %s TRIGGERED" if late else "%s TRIGGERED") % sig.setup_id)
                summary["transitions"].append((sig.setup_id, "triggered"))
        # pending setups: gate them (entries need the paper order manager, step 7), expire or invalidate them
        for sid, st in LC.open_setups(registry).items():
            rid = sid.split("-")[0]
            if st["state"] == "watching":
                if st.get("bar_date") and fx is not None and len(fx) and fx.index[-1].date().isoformat() > st["bar_date"]:
                    LC.transition(registry, sid, "expired", {"reason": "watching ended without a trigger"}, None, now)
                    summary["transitions"].append((sid, "expired"))
                continue
            if st["state"] not in ("triggered", "blocked"):
                continue
            first = [r["payload"] for r in registry.records("setup_transition")
                     if r["payload"]["setup_id"] == sid and r["payload"]["state"] == "triggered"][0]
            sig = first["signal"]
            det = date.fromisoformat(first["detected_ny_date"])
            if fx_days_between(det, now.astimezone(NY).date()) > cfg["entry_window_fx_days"][rid]:
                LC.transition(registry, sid, "expired", {"reason": "entry window of %d FX day(s) passed without entry" % cfg["entry_window_fx_days"][rid]},
                              {"setup_id": sid, "market": "USDJPY", "class": "EXPERIMENTAL IDEA (shadow ledger)"}, now)
                summary["transitions"].append((sid, "expired"))
                continue
            px = uj.get("last")
            if px and (sig["direction"] == 1 and px <= sig["invalidation"] or sig["direction"] == -1 and px >= sig["invalidation"]):
                LC.transition(registry, sid, "invalidated", {"reason": "price %.3f beyond invalidation %.3f before entry" % (px, sig["invalidation"])},
                              {"setup_id": sid, "market": "USDJPY", "class": "EXPERIMENTAL IDEA (shadow ledger)"}, now)
                summary["transitions"].append((sid, "invalidated"))
                continue
            c = G.Candidate(rule_id=rid, version=sig["version"], instrument="USDJPY", direction=sig["direction"],
                            entry_ref=px or sig["entry_ref"], invalidation=sig["invalidation"], target=sig["target"],
                            setup_id=sid, mode="shadow")
            led = PP.state(registry, rid, cfg)
            S_now = px or sig["entry_ref"]
            book = G.Book(equity=PP.equity(led, S_now), peak_equity=led["peak_equity"], day_start_equity=led["day_start_equity"],
                          positions={r: PP.exposure_x(PP.state(registry, r, cfg), S_now) for r in rules_cfg
                                     if PP.state(registry, r, cfg)["position"]})
            d = G.decide(c, view, book, cfg, prior_state=G.current_state(registry, rid), kill_on=kill_on)
            if led["experiment_stopped"]:
                d = G.Decision("BLOCKED", 0.0, ["OPERATIONAL %s experiment stopped (drawdown <= -5%%); owner decision needed" % rid], "HALTED")
            oid = None
            if d.status in ("APPROVED", "SHRUNK"):
                f = dict(market="USDJPY", instrument=INSTRUMENT_LABEL, setup_id=sid, rule_version="%s v%s" % (rid, sig["version"]),
                         reference_price=S_now, price_label="%s (indicative, not executable)" % uj.get("freshness", "UNKNOWN"),
                         quote_time_et=LC.et(uj.get("source_ts_utc")), direction={1: "LONG USD/JPY", -1: "SHORT USD/JPY"}[sig["direction"]],
                         invalidation=sig["invalidation"], target_or_exit="target %s; %s" % (sig["target"] or "none", sig["expiry_rule"]),
                         estimated_costs="round trip %.3f%% of notional (base, unverified) + financing (estimated, unverified)" % (200 * cfg["costs"]["base"]["one_way"]),
                         evidence_for=EVIDENCE[rid][0], evidence_against=EVIDENCE[rid][1], expiry=sig["expiry_rule"],
                         validation_status="FORWARD TEST %s: EXPERIMENTAL, NOT VALIDATED%s" % (rid, " (DEMO RUN)" if inp.mode == "demo" else ""),
                         why_sent="gate approved; fictional entry in the shadow ledger (internal simulator)", **{"class": "EXPERIMENTAL IDEA (shadow ledger)"})
                oid = PP.enter(registry, cfg, rid, sid, sig, d.size_x, S_now, now, slot_s, f)
            registry.append("evaluation", {"type": "gate_decision", "setup_id": sid, **d.as_dict(),
                                           "entry_status": ("entered: order %s" % oid) if oid else ("not entered" if d.status == "BLOCKED" else "not entered (position or order already exists)")},
                            idem_key="gate:%s:%s:%s" % (inp.mode, sid, key), now=now)
            summary["gate"].append((sid, d.status))
            if d.status == "BLOCKED" and st["state"] == "triggered":
                LC.transition(registry, sid, "blocked", {"reasons": d.reasons},
                              {"setup_id": sid, "market": "USDJPY", "class": "EXPERIMENTAL IDEA (shadow ledger)",
                               "trigger": "; ".join(d.reasons)}, now)
                summary["transitions"].append((sid, "blocked"))
        summary["watch"] = sum(1 for x in W.run(registry, now, watch_bars, inp.snapshot, inp.events_store, cfg["market_watch"]) if x)
        if S_mark:
            ok, _ = PP.reconcile(registry, cfg, now, S_mark)
            summary["reconciled"] = ok
        registry.append("scan_run", {"mode": inp.mode, "slot_utc": slot.isoformat(), "completed_utc": now.astimezone(timezone.utc).isoformat(),
                                     "summary": summary, "state": (G.current_state(registry) or {}).get("state", "ACTIVE"), "kill_switch": kill_on},
                        idem_key=key, now=now)
    return summary
