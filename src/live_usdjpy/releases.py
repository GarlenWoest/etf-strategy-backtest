"""OFFICIAL RELEASE alerts (owner request 2026-10-30): one informational NORMAL notification when the event monitor
confirms that an official release relevant to USD/JPY is PUBLISHED. Source, title, publication time and link only;
no figures, no interpretation, no direction. MoF intervention releases are already alerted by MARKET WATCH W004 and
are not repeated here.

Relevant = the event lists USD/JPY among its markets and is either a Federal Reserve or Bank of Japan release, or its
title matches one of the configured key US releases (BLS/BEA). Only publications detected within `lookback_hours`
alert, so the monitor's history is never replayed; each event alerts at most once (idempotency key).
"""
from datetime import datetime, timedelta

from . import lifecycle as LC


def relevant(e, cfg):
    if e.get("status") != "PUBLISHED" or "usdjpy" not in (e.get("markets_affected") or []):
        return False
    if e.get("source") in cfg["always_sources"]:
        return True
    return e.get("source") in cfg["key_title_sources"] and any(k.lower() in (e.get("title") or "").lower() for k in cfg["key_titles"])


def queue(registry, now, events_store, cfg):
    """Queue alerts for newly confirmed publications. Returns the event ids alerted in this call."""
    out = []
    for e in (events_store.get("events") or {}).values():
        if not relevant(e, cfg):
            continue
        det = e.get("detected_time_utc")
        if not det or now - datetime.fromisoformat(det) > timedelta(hours=cfg["lookback_hours"]):
            continue
        pub = e.get("published_time_source")
        r = registry.append("notification", LC.alert(
            "NORMAL", "%s: %s published" % (e["source"], e["title"]),
            summary="USD/JPY | OFFICIAL RELEASE | %s | published %s | information only" % (e["title"][:60], LC.et(pub) if pub else "time not stated"),
            **{"class": "OFFICIAL RELEASE", "market": "USDJPY", "event_time_et": LC.et(pub) if pub else "UNKNOWN (time not published)",
               "relevant_events": "%s (%s; %s)" % (e["title"], e["source"], e.get("publication_url") or e.get("source_url") or "no link"),
               "validation_status": "INFORMATION ONLY: no interpretation, no trade implication",
               "why_sent": "official publication confirmed by the event monitor at %s" % LC.et(det)}),
            idem_key="release:%s" % e["event_id"], now=now)
        if not r["duplicate"]:
            out.append(e["event_id"])
    return out
