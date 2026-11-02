"""OFFICIAL RELEASE alerts (owner request 2026-10-30; observation markets added 2026-11-01): one informational
notification when the event monitor confirms that a relevant official release is PUBLISHED. Source, title,
publication time and link only; no figures, no interpretation, no direction. MoF intervention releases are already
alerted by MARKET WATCH W004 and are not repeated here.

USD/JPY (forward-test market): Federal Reserve and Bank of Japan releases, and the key US releases (BLS/BEA titles);
NORMAL, to the phone, unchanged.
Observation markets (GBP/USD, gold): INFORMATION ONLY, no rules; the notification policy logs them for the daily
digest. GBP/USD: Bank of England MPC items and key ONS releases; gold: the key US releases and the Fed (a release that is
relevant to USD/JPY is alerted once, listing every affected market).
Only publications that were both published and detected within `lookback_hours` alert, so neither the monitor's history
nor a newly added feed's back-catalogue is replayed; each event alerts at most once (idempotency key).
"""
from datetime import datetime, timedelta

from . import lifecycle as LC

NAMES = {"usdjpy": "USD/JPY", "gbpusd": "GBP/USD", "gold": "Gold"}


def _rel(e, rules):
    if e.get("source") in rules.get("always_sources", []):
        return True
    return e.get("source") in rules.get("key_title_sources", []) and \
        any(k.lower() in (e.get("title") or "").lower() for k in rules.get("key_titles", []))


def relevant(e, cfg):
    """USD/JPY relevance (unchanged rule)."""
    return e.get("status") == "PUBLISHED" and "usdjpy" in (e.get("markets_affected") or []) and _rel(e, cfg)


def observation_markets(e, cfg):
    if e.get("status") != "PUBLISHED":
        return []
    return [m for m, rules in (cfg.get("observation") or {}).items()
            if m in (e.get("markets_affected") or []) and _rel(e, rules)]


def _recent(ts, now, hours):
    return ts is not None and now - datetime.fromisoformat(ts) <= timedelta(hours=hours)


def queue(registry, now, events_store, cfg):
    """Queue alerts for newly confirmed publications. Returns the event ids alerted in this call."""
    out = []
    for e in (events_store.get("events") or {}).values():
        usd = relevant(e, cfg)
        obs = observation_markets(e, cfg)
        if not usd and not obs:
            continue
        det, pub = e.get("detected_time_utc"), e.get("published_time_source")
        if not _recent(det, now, cfg["lookback_hours"]) or (pub and not _recent(pub, now, cfg["lookback_hours"])):
            continue
        affected = ", ".join(NAMES.get(m, m) for m in (e.get("markets_affected") or []))
        market = "USDJPY" if usd else {"gbpusd": "GBPUSD", "gold": "GOLD"}[obs[0]]
        lead = "USD/JPY" if usd else NAMES[obs[0]]
        status = "INFORMATION ONLY: no interpretation, no trade implication" if usd else \
            "INFORMATION ONLY (observation market: no rules, no paper entries)"
        r = registry.append("notification", LC.alert(
            "NORMAL", "%s: %s published" % (e["source"], e["title"]),
            summary="%s | OFFICIAL RELEASE | %s | published %s | information only" % (
                lead, e["title"][:60], LC.et(pub) if pub else "time not stated"),
            **{"class": "OFFICIAL RELEASE", "market": market, "event_time_et": LC.et(pub) if pub else "UNKNOWN (time not published)",
               "relevant_events": "%s (%s; %s); markets: %s" % (e["title"], e["source"], e.get("publication_url") or e.get("source_url") or "no link", affected),
               "validation_status": status,
               "why_sent": "official publication confirmed by the event monitor at %s" % LC.et(det)}),
            idem_key="release:%s" % e["event_id"], now=now)
        if not r["duplicate"]:
            out.append(e["event_id"])
    return out
