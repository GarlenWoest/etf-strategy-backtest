"""Notification engine for the USD/JPY forward system (master prompt step 6, 2026-10-29). Plain Python; no Claude
session involved; costs no Claude usage.

Outbox: `notification` records in the registry (status "queued"). Every delivery attempt is an append-only `delivery`
record: an "attempting" record is committed BEFORE the network call and a result record (sent / failed / rejected)
after it. After a crash between the two, the attempt is "unknown": NORMAL and LOW are NOT resent (avoids duplicates);
HIGH is resent (a duplicate is better than a lost risk alert).

Channels (adapters): LocalFile (test channel, writes live/usdjpy/outbox_local.jsonl), Pushover (primary), ntfy (fallback).
Credentials are read at send time from the macOS Keychain (`security find-generic-password -w -s <item>`) or from
environment variables of the same name in upper case; they are never written to files, logs, records or git, and are
never printed. A channel without credentials reports "not configured" and is skipped.

Priorities: HIGH / NORMAL / LOW. Quiet hours hold LOW and NORMAL until they end; HIGH and every RISK/SYSTEM ALERT are
never held. Retries use backoff and never duplicate a record or a sent message on the same channel. A daily digest
(LOW) confirms the system is alive; a missing digest or a scan gap beyond the configured limit raises a HIGH alert.
"""
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import lifecycle as LC

NY = ZoneInfo("America/New_York")
MAX_LEN = 1024                                   # Pushover message limit (UTF-8 characters); title 250


# ---------------------------------------------------------------- rendering

def render(payload):
    """Title and plain-text body. Every alert field appears; missing values read UNKNOWN; times are ET."""
    f = payload.get("fields") or {}
    title = payload.get("title", "")[:250]
    if f:
        lines = ["[%s] %s" % (payload.get("priority"), f.get("class", "UNKNOWN"))]
        order = ("market", "instrument", "setup_id", "rule_version", "event_time_et", "quote_time_et", "reference_price",
                 "price_label", "session", "direction", "trigger", "invalidation", "target_or_exit", "size",
                 "max_planned_loss", "estimated_costs", "relevant_events", "evidence_for", "evidence_against",
                 "validation_status", "expiry", "why_sent")
        for k in order:
            v = f.get(k, "UNKNOWN")
            lines.append("%s: %s" % (k.replace("_", " "), "%.3f" % v if isinstance(v, float) else v))
        body = "\n".join(lines)
    else:
        body = payload.get("body", "UNKNOWN")
    body += "\nNot financial advice. Paper/shadow only; no orders."
    if len(body) > MAX_LEN:
        body = body[: MAX_LEN - 40] + "\n[truncated; full record in registry]"
    return title, body


# ---------------------------------------------------------------- channels

def secret(item):
    """Credential from the environment (ITEM upper-cased, '-' -> '_') or the macOS Keychain. Never logged."""
    env = os.environ.get(item.upper().replace("-", "_"))
    if env:
        return env
    try:
        r = subprocess.run(["security", "find-generic-password", "-w", "-s", item], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
    except Exception:
        return None


class LocalFile:
    name = "local"

    def __init__(self, path):
        self.path = Path(path)

    def configured(self):
        return True

    def send(self, payload, title, body):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a") as fh:
            fh.write(json.dumps({"title": title, "body": body, "priority": payload.get("priority")}) + "\n")
        return {"result": "sent", "http_status": None, "info": "written to %s" % self.path.name}


class Pushover:
    name = "pushover"
    URL = "https://api.pushover.net/1/messages.json"

    def __init__(self, cfg, post=None):
        self.cfg, self.post = cfg, post

    def configured(self):
        return bool(secret("trading-research-pushover-token") and secret("trading-research-pushover-user"))

    def send(self, payload, title, body):
        import requests
        post = self.post or requests.post
        pr = self.cfg["priority"][payload.get("priority", "NORMAL")]
        data = {"token": secret("trading-research-pushover-token"), "user": secret("trading-research-pushover-user"),
                "title": title, "message": body, "priority": pr}
        if pr == 2:
            data.update(retry=self.cfg["emergency_retry_s"], expire=self.cfg["emergency_expire_s"])
        try:
            r = post(self.URL, data=data, timeout=20)
        except Exception as ex:                                   # network error: retryable (message only, no data)
            return {"result": "failed", "http_status": None, "info": type(ex).__name__}
        st = r.status_code
        if st == 200:
            j = r.json() if hasattr(r, "json") else {}
            return {"result": "sent", "http_status": 200, "info": "receipt %s" % j.get("receipt") if j.get("receipt") else "queued by Pushover"}
        if 400 <= st < 500:                                        # Pushover: repeating will not work
            return {"result": "rejected", "http_status": st, "info": "4xx from Pushover"}
        return {"result": "failed", "http_status": st, "info": "server error"}


class Ntfy:
    name = "ntfy"

    def __init__(self, cfg, post=None):
        self.cfg, self.post = cfg, post

    def configured(self):
        return bool(secret("trading-research-ntfy-topic"))

    def send(self, payload, title, body):
        import requests
        post = self.post or requests.post
        url = "%s/%s" % (self.cfg["server"].rstrip("/"), secret("trading-research-ntfy-topic"))
        try:
            r = post(url, data=body.encode(), headers={"Title": title, "Priority": str(self.cfg["priority"][payload.get("priority", "NORMAL")])},
                     timeout=20)
        except Exception as ex:
            return {"result": "failed", "http_status": None, "info": type(ex).__name__}
        st = r.status_code
        if 200 <= st < 300:
            return {"result": "sent", "http_status": st, "info": "accepted by ntfy server (no delivery receipt)"}
        return {"result": "rejected" if 400 <= st < 500 and st != 429 else "failed", "http_status": st, "info": "ntfy error"}


# ---------------------------------------------------------------- dispatch

def _hm(s):
    h, m = s.split(":")
    return int(h), int(m)


def in_quiet_hours(now, cfg):
    a, b = (_hm(x) for x in cfg["quiet_hours_et"])
    t = (now.astimezone(NY).hour, now.astimezone(NY).minute)
    return (a <= t or t < b) if a > b else (a <= t < b)


def deliveries(registry, notif_id):
    return [r["payload"] for r in registry.records("delivery") if r["payload"]["notification_id"] == notif_id]


def status_of(registry, notif_id):
    ds = deliveries(registry, notif_id)
    if any(d["result"] == "sent" for d in ds):
        return "delivered"
    return "pending"


def dispatch(registry, now, channels, cfg):
    """Send every undelivered notification that is due. `channels`: ordered list [primary, fallback, ...] of adapters.
    Returns a list of (notification_id, outcome)."""
    out = []
    quiet = in_quiet_hours(now, cfg)
    for rec in registry.records("notification"):
        p, nid = rec["payload"], rec["record_id"]
        if status_of(registry, nid) == "delivered":
            continue
        high = p.get("priority") == "HIGH" or (p.get("fields") or {}).get("class") == "RISK/SYSTEM ALERT"
        if quiet and not high:
            out.append((nid, "held (quiet hours)"))
            continue
        ds = deliveries(registry, nid)
        # an attempt with no result = crash between send and record: never resend NORMAL/LOW; resend HIGH
        dangling = [d for d in ds if d["result"] == "attempting" and not any(
            x["attempt_id"] == d["attempt_id"] and x["result"] != "attempting" for x in ds)]
        if dangling and not high:
            registry.append("delivery", {"notification_id": nid, "channel": dangling[0]["channel"], "attempt_id": dangling[0]["attempt_id"],
                                         "result": "unknown", "info": "interrupted after the send started; not resent (non-HIGH)"},
                            idem_key="delivery:%s:%s:unknown" % (nid, dangling[0]["attempt_id"]), now=now)
            out.append((nid, "unknown (not resent)"))
            continue
        if any(d["result"] == "unknown" for d in ds) and not high:
            continue
        title, body = render(p)
        sent = False
        for i, ch in enumerate(channels):
            if not ch.configured():
                out.append((nid, "%s not configured" % ch.name))
                continue
            mine = [d for d in ds if d["channel"] == ch.name and d["result"] in ("failed", "rejected")]
            if any(d["result"] == "rejected" for d in mine) or len(mine) >= cfg["max_attempts_per_channel"]:
                continue                                       # this channel gave up on this message; try the next
            if mine:
                wait = cfg["retry_backoff_minutes"][min(len(mine) - 1, len(cfg["retry_backoff_minutes"]) - 1)]
                if now < datetime.fromisoformat(mine[-1]["at_utc"]) + timedelta(minutes=wait):
                    if i == 0 and len(mine) < cfg["fallback_after_failed_primary"]:
                        break                                  # wait for the primary's backoff before falling back
                    continue
            att = "%s-%s-%d" % (nid, ch.name, len(mine) + 1)
            registry.append("delivery", {"notification_id": nid, "channel": ch.name, "attempt_id": att, "result": "attempting",
                                         "at_utc": now.isoformat()}, idem_key="delivery:%s:attempting" % att, now=now)
            res = ch.send(p, title, body)
            registry.append("delivery", {"notification_id": nid, "channel": ch.name, "attempt_id": att, "at_utc": now.isoformat(),
                                         "result": res["result"], "http_status": res["http_status"], "info": res["info"]},
                            idem_key="delivery:%s:%s" % (att, res["result"]), now=now)
            out.append((nid, "%s %s" % (ch.name, res["result"])))
            if res["result"] == "sent":
                sent = True
                break
            if i == 0 and res["result"] == "failed" and len(mine) + 1 < cfg["fallback_after_failed_primary"]:
                break                                          # retry the primary later before using the fallback
        if not sent and not any(ch.configured() for ch in channels):
            out.append((nid, "no channel configured"))
    return out


# ---------------------------------------------------------------- liveness: digest, gaps

def queue_digest(registry, now, cfg, snapshot=None):
    """Once per New York day at/after digest time: LOW 'system alive' message."""
    ny = now.astimezone(NY)
    if (ny.hour, ny.minute) < _hm(cfg["digest_time_et"]):
        return False
    runs = registry.records("scan_run")
    last = runs[-1]["payload"]["completed_utc"] if runs else None
    fresh = {o["specialist"]: "%s (%s)" % (o.get("freshness"), LC.et(o.get("source_ts_utc")))
             for o in (snapshot or {}).get("observations", []) if o.get("role") == "primary"}
    opens = LC.open_setups(registry)
    day = ny.date().isoformat()
    sent_today = [r for r in registry.records("notification") if LC.et(r["created_utc"]).startswith(day)]
    body = ("System alive. Last successful scan: %s. Data freshness: %s. Open setups: %s. Open paper positions: none "
            "(paper order manager not built yet). Alerts queued today: %d." % (
                LC.et(last), "; ".join("%s %s" % kv for kv in fresh.items()) or "UNKNOWN",
                ", ".join("%s %s" % (k, v["state"]) for k, v in opens.items()) or "none", len(sent_today)))
    r = registry.append("notification", {"status": "queued", "priority": "LOW", "title": "Daily digest %s" % day,
                                         "body": body, "kind": "digest", "ny_date": day}, idem_key="digest:%s" % day, now=now)
    return not r["duplicate"]


def check_liveness(registry, now, cfg, fx_open):
    """HIGH alerts for a scan gap beyond the limit (while the FX market is open) and for a digest that was due but
    has not been delivered. Each gap or missed digest alerts once."""
    alerts = []
    runs = registry.records("scan_run")
    last = datetime.fromisoformat(runs[-1]["payload"]["completed_utc"]) if runs else None
    if fx_open and (last is None or now - last > timedelta(hours=cfg["scan_gap_hours"])):
        key = "gap:%s" % (last.isoformat() if last else "never")
        r = registry.append("notification", LC.alert("HIGH", "NO SUCCESSFUL SCAN for more than %d h" % cfg["scan_gap_hours"],
                                                     **{"class": "RISK/SYSTEM ALERT", "event_time_et": LC.et(now),
                                                        "why_sent": "last successful scan %s" % LC.et(last)}),
                            idem_key=key, now=now)
        alerts.append(("scan_gap", not r["duplicate"]))
    ny = now.astimezone(NY)
    h, m = _hm(cfg["digest_time_et"])
    due = ny.replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(minutes=cfg["digest_grace_minutes"])
    if ny >= due:
        day = ny.date().isoformat()
        dig = registry.get_by_key("digest:%s" % day)
        if not dig or status_of(registry, dig["record_id"]) != "delivered":
            r = registry.append("notification", LC.alert("HIGH", "DAILY DIGEST MISSING for %s" % day,
                                                         **{"class": "RISK/SYSTEM ALERT", "event_time_et": LC.et(now),
                                                            "why_sent": "digest not delivered by %s" % due.strftime("%H:%M ET")}),
                                idem_key="digest-missing:%s" % day, now=now)
            alerts.append(("digest_missing", not r["duplicate"]))
    return alerts
