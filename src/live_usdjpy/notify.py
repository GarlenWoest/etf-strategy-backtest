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

ORDER = ("market", "instrument", "setup_id", "rule_version", "event_time_et", "quote_time_et", "reference_price",
         "price_label", "session", "direction", "trigger", "invalidation", "target_or_exit", "size",
         "max_planned_loss", "estimated_costs", "relevant_events", "evidence_for", "evidence_against",
         "validation_status", "expiry", "why_sent")
SHORT_CLASS = {"EXPERIMENTAL IDEA (shadow ledger)": "EXPERIMENTAL IDEA", "APPROVED PAPER CANDIDATE": "PAPER CANDIDATE",
               "RISK/SYSTEM ALERT": "SYSTEM", "MARKET WATCH": "WATCH", "PAPER POSITION UPDATE": "PAPER POSITION"}


def _v(v):
    return "%.3f" % v if isinstance(v, float) else str(v)


def summary_line(payload):
    """One line for the lock screen: priority, class, market, what happened, the key number, validation."""
    if payload.get("summary"):
        return payload["summary"][:200]
    f = payload.get("fields") or {}
    parts = ["%s %s" % (payload.get("priority", ""), SHORT_CLASS.get(f.get("class"), f.get("class") or "INFO"))]
    if f.get("market"):
        parts.append(f["market"])
    parts.append(payload.get("title", ""))
    if f.get("class") in ("EXPERIMENTAL IDEA (shadow ledger)", "APPROVED PAPER CANDIDATE"):
        if f.get("reference_price") not in (None, "UNKNOWN"):
            parts.append("ref %s" % _v(f["reference_price"]))
        if f.get("invalidation") not in (None, "UNKNOWN"):
            parts.append("inv %s" % _v(f["invalidation"]))
        parts.append("NOT VALIDATED")
    return " | ".join(p for p in parts if p)[:200]


def render(payload):
    """Title and plain-text body. Line 1 is a one-line summary (lock screen). Then the alert's fields: the full list
    for EXPERIMENTAL IDEA / APPROVED PAPER CANDIDATE, only the applicable ones otherwise. Times are ET."""
    f = payload.get("fields") or {}
    title = payload.get("title", "")[:250]
    lines = [summary_line(payload)]
    if f:
        lines.append("class: %s" % f.get("class", "UNKNOWN"))
        lines += ["%s: %s" % (k.replace("_", " "), _v(f[k])) for k in ORDER if k in f]
    else:
        lines.append(payload.get("body", "UNKNOWN"))
    body = "\n".join(lines)
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


    RECEIPT_URL = "https://api.pushover.net/1/receipts/%s.json"

    def receipt(self, receipt_id, get=None):
        """Pushover's official receipt for an EMERGENCY-priority (HIGH) message: whether it reached a device
        (last_delivered_at), was acknowledged (acknowledged, acknowledged_at) or expired. Read-only GET; the token is
        sent as a query parameter as Pushover documents and is never recorded."""
        import re
        import requests
        if not re.fullmatch(r"[A-Za-z0-9]{20,40}", receipt_id or ""):
            return {"error": "invalid receipt id"}
        get = get or requests.get
        try:
            r = get(self.RECEIPT_URL % receipt_id, params={"token": secret("trading-research-pushover-token")}, timeout=20)
        except Exception as ex:
            return {"error": type(ex).__name__}
        if r.status_code != 200:
            return {"error": "HTTP %d" % r.status_code}
        j = r.json()
        return {k: j.get(k) for k in ("acknowledged", "acknowledged_at", "last_delivered_at", "expired", "expires_at", "called_back")}


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
            r = post(url, data=body.encode(), headers={"Title": title.encode("ascii", "replace").decode(),   # headers must be ASCII
                                                       "Priority": str(self.cfg["priority"][payload.get("priority", "NORMAL")])},
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


HANDLED = ("routed_to_digest", "expired_unsent")             # policy decisions (Phase E): final, not a phone delivery


def status_of(registry, notif_id):
    """Internal state: "delivered" = a provider accepted it (or the owner confirmed it), "digest" / "expired" = the
    notification policy kept it off the phone, "pending" otherwise. See provider_status() for the owner-facing label."""
    ds = deliveries(registry, notif_id)
    if any(d["result"] in ("sent", "delivered_confirmed_by_owner", "acknowledged") for d in ds):
        return "delivered"
    if any(d["result"] == "routed_to_digest" for d in ds):
        return "digest"
    if any(d["result"] == "expired_unsent" for d in ds):
        return "expired"
    return "pending"


PROVIDER_LABEL = ("QUEUED", "ACCEPTED BY PROVIDER", "DELIVERED (provider receipt)", "DELIVERED (owner-confirmed)",
                  "ACKNOWLEDGED", "NOT ACKNOWLEDGED (expired)", "FAILED",
                  "LOGGED FOR DIGEST", "EXPIRED UNSENT", "UNKNOWN (interrupted)")


def provider_status(registry, notif_id, ds=None):
    """Owner-facing status. HTTP 200 from a provider is only ACCEPTED BY PROVIDER: it does not prove the phone
    showed it or that anyone saw it. DELIVERED needs the owner's confirmation; ACKNOWLEDGED needs a Pushover
    emergency-priority receipt (HIGH alerts only)."""
    ds = deliveries(registry, notif_id) if ds is None else ds
    res = [d["result"] for d in ds]
    if "acknowledged" in res:
        return "ACKNOWLEDGED"
    if "delivered_confirmed_by_owner" in res:
        return "DELIVERED (owner-confirmed)"
    if "emergency_expired_unacknowledged" in res:
        return "DELIVERED, NOT ACKNOWLEDGED (expired)" if "delivered_confirmed_by_provider" in res else "NOT ACKNOWLEDGED (expired)"
    if "delivered_confirmed_by_provider" in res:
        return "DELIVERED (provider receipt)"
    if "sent" in res:
        return "ACCEPTED BY PROVIDER"
    if "routed_to_digest" in res:
        return "LOGGED FOR DIGEST"
    if "expired_unsent" in res:
        return "EXPIRED UNSENT"
    if any(r in ("failed", "rejected") for r in res):
        return "FAILED"
    if "unknown" in res:
        return "UNKNOWN (interrupted)"
    return "QUEUED"


def dispatch(registry, now, channels, cfg):
    """Send every undelivered notification that is due. `channels`: ordered list [primary, fallback, ...] of adapters.
    Returns a list of (notification_id, outcome)."""
    from . import alerts as AL
    out = []
    quiet = in_quiet_hours(now, cfg)
    notifs = registry.records("notification")
    titles = {r["record_id"]: r["payload"].get("title") for r in notifs}
    delivered_today = [(datetime.fromisoformat(d["payload"]["at_utc"]), titles.get(d["payload"]["notification_id"]))
                       for d in registry.records("delivery") if d["payload"]["result"] == "sent" and d["payload"].get("at_utc")
                       and registry_priority(notifs, d["payload"]["notification_id"]) != "HIGH"]
    for rec in notifs:
        p, nid = rec["payload"], rec["record_id"]
        if status_of(registry, nid) != "pending":
            continue
        high = p.get("priority") == "HIGH" or (p.get("fields") or {}).get("class") == "RISK/SYSTEM ALERT"
        if cfg.get("policy"):
            dest, why = AL.route(registry, rec, now, cfg["policy"], delivered_today)
            if dest != "phone":
                res = "routed_to_digest" if dest == "digest" else "expired_unsent"
                registry.append("delivery", {"notification_id": nid, "channel": "policy", "attempt_id": "%s-policy" % nid,
                                             "result": res, "info": why, "at_utc": now.isoformat()},
                                idem_key="delivery:%s:policy" % nid, now=now)
                out.append((nid, "%s (%s)" % (res, why)))
                continue
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
        if cfg.get("policy"):
            sid = (p.get("fields") or {}).get("setup_id")
            tk = AL.latest_ticket(registry, sid) if sid and sid not in ("UNKNOWN",) else None
            title, body = AL.phone_text(p, "%s v%d" % (sid, tk["version"]) if tk else None)
        else:
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
                if not high:
                    delivered_today.append((now, p.get("title")))
                break
            if i == 0 and res["result"] == "failed" and len(mine) + 1 < cfg["fallback_after_failed_primary"]:
                break                                          # retry the primary later before using the fallback
        if not sent and not any(ch.configured() for ch in channels):
            out.append((nid, "no channel configured"))
    return out


def poll_receipts(registry, now, pushover, max_age_hours=26, get=None):
    """Check Pushover receipts of HIGH alerts sent at emergency priority and record what the provider confirms:
    'delivered_confirmed_by_provider' (reached a device), 'acknowledged' (someone tapped Acknowledge) or
    'emergency_expired_unacknowledged'. Each fact is recorded once; polling stops at acknowledgement or expiry.
    Non-emergency messages have no receipt and stay ACCEPTED BY PROVIDER."""
    out = []
    dl = registry.records("delivery")
    done = {}
    for d in dl:
        done.setdefault(d["payload"]["notification_id"], set()).add(d["payload"]["result"])
    for d in dl:
        p = d["payload"]
        info = p.get("info") or ""
        if p["result"] != "sent" or p.get("channel") != "pushover" or not info.startswith("receipt "):
            continue
        nid, rid = p["notification_id"], info.split()[1]
        have = done.get(nid, set())
        if "acknowledged" in have or "emergency_expired_unacknowledged" in have:
            continue
        if now - datetime.fromisoformat(d["created_utc"]) > timedelta(hours=max_age_hours):
            continue
        rc = pushover.receipt(rid, get=get)
        if rc.get("error"):
            out.append((nid, "receipt check failed: %s" % rc["error"]))
            continue
        for res, cond, when in (("delivered_confirmed_by_provider", rc.get("last_delivered_at"), rc.get("last_delivered_at")),
                                ("acknowledged", rc.get("acknowledged"), rc.get("acknowledged_at")),
                                ("emergency_expired_unacknowledged", rc.get("expired") and not rc.get("acknowledged"), rc.get("expires_at"))):
            if cond and res not in have:
                registry.append("delivery", {"notification_id": nid, "channel": "pushover", "attempt_id": "%s-receipt" % nid,
                                             "result": res, "at_utc": now.isoformat(),
                                             "provider_time_utc": datetime.fromtimestamp(when, timezone.utc).isoformat() if when else None,
                                             "info": "Pushover receipt"}, idem_key="delivery:%s:%s" % (nid, res), now=now)
                out.append((nid, res))
    return out


def registry_priority(notifs, nid):
    for r in notifs:
        if r["record_id"] == nid:
            return r["payload"].get("priority")
    return None


# ---------------------------------------------------------------- liveness: digest, gaps

def queue_digest(registry, now, cfg, snapshot=None, extra=None, positions=None):
    """Once per New York day at/after digest time: a short LOW 'system status' message (Phase E format).
    Operating status, data currency, new setups, paper positions, what needs attention, what was logged without a
    phone alert. It is never a trading signal."""
    ny = now.astimezone(NY)
    if (ny.hour, ny.minute) < _hm(cfg["digest_time_et"]):
        return False
    day = ny.date().isoformat()
    today = lambda ts: LC.et(ts).startswith(day)
    runs = registry.records("scan_run")
    last = runs[-1]["payload"]["completed_utc"] if runs else None
    pfs = registry.records("preflight")
    pf = pfs[-1]["payload"] if pfs else None
    if pf:
        bad = [c for c in pf["checks"] if c["status"] in ("DEGRADED", "BLOCKED")]
        system = "%s%s" % (pf["verdict"], ": " + "; ".join("%s %s" % (c["check"], c["status"]) for c in bad) if bad else "")
    elif runs:
        system = "running; readiness not checked yet (no scan since the readiness check was installed)"
    else:
        system = "no scan recorded yet"
    names = {"usdjpy": "USD/JPY", "gold": "Gold", "gbpusd": "GBP/USD"}
    data = " | ".join("%s %s %s" % (names.get(o["specialist"], o["specialist"]), o.get("freshness", "UNKNOWN"),
                                      LC.et(o.get("source_ts_utc"))[11:] if o.get("source_ts_utc") else "")
                      for o in (snapshot or {}).get("observations", []) if o.get("role") == "primary") or "UNKNOWN"
    new = []
    for r in registry.records("setup_transition"):
        if today(r["created_utc"]) and r["payload"]["state"] in ("triggered", "blocked", "entered", "exited", "invalidated"):
            new.append("%s %s" % (r["payload"]["setup_id"], r["payload"]["state"].upper()))
    notifs = {r["record_id"]: r["payload"] for r in registry.records("notification")}
    dl = registry.records("delivery")
    logged = [notifs.get(d["payload"]["notification_id"], {}).get("title", "?") for d in dl
              if d["payload"]["result"] in ("routed_to_digest", "expired_unsent") and today(d["created_utc"])]
    failed = sorted({d["payload"]["notification_id"] for d in dl if d["payload"]["result"] in ("failed", "rejected", "unknown")
                     and today(d["created_utc"])} - {d["payload"]["notification_id"] for d in dl if d["payload"]["result"] == "sent"})
    attention = []
    if pf and pf["verdict"] != "READY":
        attention.append("preflight %s" % pf["verdict"])
    if failed:
        attention.append("%d notification(s) not delivered" % len(failed))
    unack = [d for d in dl if d["payload"]["result"] == "emergency_expired_unacknowledged" and today(d["created_utc"])]
    if unack:
        attention.append("%d HIGH alert(s) expired without acknowledgement" % len(unack))
    if extra and "no verified snapshot" in extra:
        attention.append("backup")
    lines = ["System: %s. Last scan %s." % (system, LC.et(last)),
             "Data: %s." % data,
             "New setups today: %s." % (", ".join(new) or "none"),
             "Paper positions: %s." % (positions if positions is not None else "UNKNOWN"),
             "Attention: %s." % (", ".join(attention) or "nothing"),
             "Logged without phone alert today: %s." % ("%d (%s)" % (len(logged), "; ".join(t[:50] for t in logged[:3]) + ("; ..." if len(logged) > 3 else ""))
                                                        if logged else "none")]
    if extra:
        lines.append(extra)
    lines.append("Status only. NOT A TRADING SIGNAL.")
    r = registry.append("notification", {"status": "queued", "priority": "LOW", "title": "Daily digest %s" % day,
                                         "body": "\n".join(lines), "kind": "digest", "ny_date": day}, idem_key="digest:%s" % day, now=now)
    return not r["duplicate"]


def check_liveness(registry, now, cfg, fx_open, position_open=False):
    """HIGH alerts for a scan gap beyond the limit (while the FX market is open) and for a digest that was due but
    has not been delivered. Each gap or missed digest alerts once."""
    alerts = []
    runs = registry.records("scan_run")
    last = datetime.fromisoformat(runs[-1]["payload"]["completed_utc"]) if runs else None
    limit = cfg.get("scan_gap_hours_with_position", cfg["scan_gap_hours"]) if position_open else cfg["scan_gap_hours"]
    if fx_open and (last is None or now - last > timedelta(hours=limit)):
        key = "gap:%s" % (last.isoformat() if last else "never")
        r = registry.append("notification", LC.alert("HIGH", "NO SUCCESSFUL SCAN for more than %s h%s" % (
                                                         limit, " WITH A PAPER POSITION OPEN" if position_open else ""),
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
