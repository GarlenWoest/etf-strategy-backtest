"""MARKET WATCH conditions v1.0 (informational only; never a paper entry). Master prompt step 5, 2026-10-29.

  W001 big daily move      |last completed daily log return| > big_move_sd x 20-day std of the prior returns
  W002 volatility regime   20-day vol crosses above regime_ratio_up x its 250-day median (HIGH-VOL), or back below
                           regime_ratio_down x (NORMAL); alerts only on a change of regime
  W003 official event      a scheduled high-impact official release within event_horizon_hours (one alert per event)
  W004 MoF publication     a new Japan MoF intervention release (monthly or quarterly) appears in the event store
  W005 data outage         the primary price of a market is STALE/UNAVAILABLE or its specialist status is not DATA OK
                           while its market is open; recovery alerts when it returns (system alert, never capped)
Markets: USD/JPY, gold (GLD reference) and GBP/USD. At most max_per_market_per_day W001-W004 alerts per market per New
York day (configurable); everything is still recorded in the registry. Never implies a closed instrument is tradable.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np

from .lifecycle import alert, et

NY = ZoneInfo("America/New_York")
VERSION = "1.0"
HIGH_IMPACT = ("FOMC", "Employment Situation", "Consumer Price Index", "GDP", "Personal Income", "BoJ Monetary Policy",
               "UK Labour Market", "Consumer price inflation", "GDP monthly estimate")
EVENT_MARKETS = {"usdjpy": "USDJPY", "gold": "GOLD", "gbpusd": "GBPUSD"}
INSTRUMENT = {"USDJPY": "USD_JPY (OANDA practice, indicative)", "GOLD": "GLD (Alpaca IEX; gold reference, not spot gold)",
              "GBPUSD": "GBP_USD (OANDA practice, indicative)"}
NA = "not applicable (information only)"
NOT_TRADE = dict(setup_id=NA, rule_version="MARKET WATCH v%s" % VERSION, direction=NA, invalidation=NA, target_or_exit=NA,
                 size=NA, max_planned_loss=NA, estimated_costs=NA, evidence_for=NA, evidence_against=NA, expiry=NA)


def _vol_series(closes, window):
    lr = np.log(closes.astype(float)).diff().dropna()
    return lr, lr.rolling(window).std()


def big_move(closes, cfg):
    lr, sd = _vol_series(closes, cfg["vol_window"])
    if len(lr) < cfg["vol_window"] + 1:
        return None
    prior_sd = float(sd.iloc[-2])
    r = float(lr.iloc[-1])
    if prior_sd > 0 and abs(r) > cfg["big_move_sd"] * prior_sd:
        return {"date": lr.index[-1].date().isoformat(), "log_return": r, "sd20": prior_sd, "multiple": abs(r) / prior_sd}
    return None


def vol_regime(closes, cfg):
    lr, sd = _vol_series(closes, cfg["vol_window"])
    sd = sd.dropna()
    if len(sd) < cfg["regime_lookback"]:
        return None
    med = float(sd.iloc[-cfg["regime_lookback"]:-1].median())
    ratio = float(sd.iloc[-1]) / med if med > 0 else None
    return {"date": sd.index[-1].date().isoformat(), "vol20_annual": float(sd.iloc[-1]) * np.sqrt(252),
            "ratio_to_median": ratio}


def last_regime(registry, market):
    recs = [r["payload"] for r in registry.records("market_watch")
            if r["payload"]["condition"] == "W002" and r["payload"]["market"] == market]
    return recs[-1]["regime"] if recs else "NORMAL"


def alerts_today(registry, market, now):
    day = now.astimezone(NY).date().isoformat()
    return sum(1 for r in registry.records("market_watch")
               if r["payload"]["market"] == market and r["payload"].get("alerted") and r["payload"]["ny_date"] == day)


def in_reopen_grace(now, cfg):
    """True within `reopen_grace_minutes` after the weekly FX reopen (Sunday 17:00 New York)."""
    ny = now.astimezone(NY)
    if ny.weekday() != 6:
        return False
    opened = ny.replace(hour=17, minute=0, second=0, microsecond=0)
    return opened <= ny < opened + timedelta(minutes=cfg.get("reopen_grace_minutes", 0))


def record(registry, cond, market, payload, idem, now, cfg, title, priority, fields, capped=True, quiet=False):
    """Record the trigger (always) and queue an alert unless the market's daily cap is reached (or `quiet`)."""
    if registry.get_by_key(idem):
        return False
    alerted = not quiet and (not capped or alerts_today(registry, market, now) < cfg["max_per_market_per_day"])
    registry.append("market_watch", {"condition": cond, "version": VERSION, "market": market, "alerted": alerted,
                                     "ny_date": now.astimezone(NY).date().isoformat(), **payload}, idem_key=idem, now=now)
    if alerted:
        registry.append("notification", alert(priority, title, **fields), idem_key="notif:" + idem, now=now)
    return True


def run(registry, now, bars, snapshot, events_store, cfg):
    """Evaluate W001-W005 for all three markets. `bars`: market -> completed daily closes (Series)."""
    out = []
    obs = {o["specialist"]: o for o in snapshot.get("observations", []) if o.get("role") == "primary"}
    status = snapshot.get("status", {})
    for spec, market in EVENT_MARKETS.items():
        o = obs.get(spec, {})
        base = dict(NOT_TRADE, market=market, instrument=INSTRUMENT[market], quote_time_et=et(o.get("source_ts_utc")),
                    reference_price=o.get("last"), price_label="%s (indicative, not executable)" % o.get("freshness", "UNKNOWN"),
                    session=", ".join(snapshot.get("clock", {}).get("active_sessions", []) or []) or "none open",
                    validation_status="MARKET WATCH: informational only, never a paper entry", **{"class": "MARKET WATCH"})
        c = bars.get(market)
        if c is not None and len(c):
            m = big_move(c, cfg)
            if m:
                out.append(record(registry, "W001", market, m, "W001:%s:%s" % (market, m["date"]), now, cfg,
                                  "%s daily move %.1fx its 20-day volatility" % (market, m["multiple"]), "NORMAL",
                                  {**base, "event_time_et": m["date"], "trigger": "W001 v%s: |return| %.2f%% > %.1f x 20-day sd %.2f%%" % (
                                      VERSION, 100 * abs(m["log_return"]), cfg["big_move_sd"], 100 * m["sd20"]),
                                   "why_sent": "W001 big daily move"}))
            v = vol_regime(c, cfg)
            if v and v["ratio_to_median"]:
                prev = last_regime(registry, market)
                new = "HIGH-VOL" if v["ratio_to_median"] > cfg["regime_ratio_up"] else (
                    "NORMAL" if v["ratio_to_median"] < cfg["regime_ratio_down"] else prev)
                if new != prev:
                    out.append(record(registry, "W002", market, {**v, "regime": new, "previous": prev},
                                      "W002:%s:%s:%s" % (market, v["date"], new), now, cfg,
                                      "%s volatility regime %s -> %s" % (market, prev, new), "NORMAL",
                                      {**base, "event_time_et": v["date"], "trigger": "W002 v%s: 20-day vol %.1f%% = %.2fx its 250-day median" % (
                                          VERSION, 100 * v["vol20_annual"], v["ratio_to_median"]), "why_sent": "W002 regime change"}))
        fresh, st = o.get("freshness", "UNAVAILABLE"), status.get(spec, "UNKNOWN")
        down = (fresh in ("STALE", "UNAVAILABLE") and o.get("session_open")) or (st != "DATA OK" and o.get("session_open"))
        recs = [r["payload"] for r in registry.records("market_watch") if r["payload"]["condition"] == "W005" and r["payload"]["market"] == market]
        was_down = bool(recs) and recs[-1]["state"] == "OUTAGE"
        grace = in_reopen_grace(now, cfg) and spec != "gold"          # FX quotes restart after the Sunday 17:00 ET reopen
        fields5 = lambda state: {**base, "class": "RISK/SYSTEM ALERT", "event_time_et": et(now), "trigger": "W005 v%s" % VERSION,
                                 "why_sent": "data source %s" % state.lower()}
        if down != was_down:
            state = "OUTAGE" if down else "RECOVERED"
            # owner decision 2026-11-01: inside the reopen grace, a stale-price outage is recorded but not alerted; its
            # recovery is then silent too. Still down when the grace ends -> alerted then (below). HIGH alerts unaffected.
            quiet = (state == "OUTAGE" and grace and fresh in ("STALE", "UNAVAILABLE")) or \
                    (state == "RECOVERED" and recs and recs[-1].get("grace") and not recs[-1].get("alerted"))
            out.append(record(registry, "W005", market, {"state": state, "freshness": fresh, "specialist_status": st,
                                                          "grace": bool(quiet and state == "OUTAGE")},
                              "W005:%s:%s:%s" % (market, state, now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M")), now, cfg,
                              "%s data %s (%s, %s)" % (market, state.lower(), fresh, st), "NORMAL", fields5(state),
                              capped=False, quiet=quiet))
        elif down and recs and recs[-1].get("grace") and not recs[-1].get("alerted") and not grace:
            out.append(record(registry, "W005", market, {"state": "OUTAGE", "freshness": fresh, "specialist_status": st,
                                                          "after_grace": True},
                              "W005:%s:OUTAGE-after-grace:%s" % (market, now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M")), now, cfg,
                              "%s data outage continues after the reopen grace (%s, %s)" % (market, fresh, st), "NORMAL",
                              fields5("OUTAGE"), capped=False))
    horizon = now + timedelta(hours=cfg["event_horizon_hours"])
    for eid, e in (events_store.get("events") or {}).items():
        if e.get("status") != "SCHEDULED" or not any(k.lower() in e.get("title", "").lower() for k in HIGH_IMPACT):
            continue
        if e.get("scheduled_time_utc"):
            t = datetime.fromisoformat(e["scheduled_time_utc"])
            if not (now <= t <= horizon):
                continue
            when = et(t)
        else:                            # date only (e.g. BoJ statements: time not published in advance)
            if not e.get("scheduled_date") or not (now.date().isoformat() <= str(e["scheduled_date"]) <= horizon.date().isoformat()):
                continue
            t, when = None, "%s (time not published)" % e["scheduled_date"]
        for spec in e.get("markets_affected") or []:
            market = EVENT_MARKETS.get(spec)
            if not market:
                continue
            out.append(record(registry, "W003", market, {"event_id": eid, "title": e["title"], "time_utc": e.get("scheduled_time_utc"),
                                                         "date": e.get("scheduled_date"), "source": e.get("source")},
                              "W003:%s:%s" % (market, eid), now, cfg,
                              "%s within 24 h: %s at %s" % (market, e["title"], when), "LOW",
                              {**NOT_TRADE, "instrument": INSTRUMENT[market], "market": market, "class": "MARKET WATCH",
                               "event_time_et": when, "trigger": "W003 v%s" % VERSION,
                               "relevant_events": "%s (%s, official schedule)" % (e["title"], e.get("source")),
                               "validation_status": "MARKET WATCH: informational only, never a paper entry",
                               "why_sent": "high-impact official event within 24 h"}))
    first_mof = not any(r["payload"]["condition"] == "W004" for r in registry.records("market_watch"))
    for kind, rel in (events_store.get("mof_intervention") or {}).items():
        key = "W004:USDJPY:%s:%s" % (kind, rel.get("published"))
        if first_mof:                    # releases already known at the first scan are a baseline, not news
            if not registry.get_by_key(key):
                registry.append("market_watch", {"condition": "W004", "version": VERSION, "market": "USDJPY", "alerted": False,
                                                 "ny_date": now.astimezone(NY).date().isoformat(), "baseline": True,
                                                 "release": kind, **rel}, idem_key=key, now=now)
            continue
        out.append(record(registry, "W004", "USDJPY", {"release": kind, **rel}, key, now, cfg,
                          "MoF intervention release: %s (%s), published %s" % (kind, rel.get("period"), rel.get("published")),
                          "NORMAL", {**NOT_TRADE, "instrument": INSTRUMENT["USDJPY"], "market": "USDJPY", "class": "MARKET WATCH",
                                     "event_time_et": rel.get("published"),
                                     "trigger": "W004 v%s: new MoF release" % VERSION,
                                     "relevant_events": "Japan MoF %s, period %s (amounts not parsed: UNKNOWN)" % (kind, rel.get("period")),
                                     "validation_status": "MARKET WATCH: informational only, never a paper entry",
                                     "why_sent": "new official MoF intervention publication"}))
    return out
