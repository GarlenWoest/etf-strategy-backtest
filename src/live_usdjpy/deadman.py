"""Dead-man switch (owner-approved 2026-11-01): after each run the runner pings external healthchecks.io checks, which
alert the owner's phone if the pings stop (Mac asleep, off, crashed, or the agent not running).

What leaves the Mac: one HTTPS GET with no body per check per run (the service sees the time, the public IP address
and the client's user agent). No market data, records or credentials. The ping URLs are secrets: read from the
Keychain at run time (items below), never printed, logged or written to records; only "ok / failed / not configured"
is kept. Hosts are restricted to healthchecks.io's ping hosts; anything else is refused before any request.
A ping never blocks or fails a run (short timeout, all errors swallowed into the status).

Checks (owner setup): B "always" (item trading-research-deadman-url), A "weekday" (trading-research-deadman-url-weekday).
After a run error the "/fail" variant is sent so the service can alert at once.
"""
from datetime import datetime, timezone
from urllib.parse import urlparse

from .notify import secret

ITEMS = {"always": "trading-research-deadman-url", "weekday": "trading-research-deadman-url-weekday"}
ALLOWED_HOSTS = ("hc-ping.com", "healthchecks.io")


def _valid(url):
    u = urlparse(url or "")
    return u.scheme == "https" and (u.hostname or "") in ALLOWED_HOSTS and len([p for p in u.path.split("/") if p]) >= 1


def ping(now, ok=True, http_get=None, read_secret=None):
    """Ping every configured check. Returns {check: status}; never raises, never returns a URL."""
    import requests
    get = http_get or requests.get
    rs = read_secret or secret
    out = {}
    for name, item in ITEMS.items():
        url = (rs(item) or "").strip()
        if not url:
            out[name] = "not configured"
            continue
        if not _valid(url):
            out[name] = "refused: not a healthchecks.io https ping URL"
            continue
        try:
            r = get(url.rstrip("/") + ("" if ok else "/fail"), timeout=10)
            body = (getattr(r, "text", "") or "").strip()[:20]
            out[name] = ("ok" if ok else "fail sent") if r.status_code == 200 and body.upper().startswith("OK") else \
                "failed: HTTP %s %s" % (r.status_code, "(check not found)" if "not found" in body.lower() else "")
        except Exception as ex:
            out[name] = "failed: %s" % type(ex).__name__
    out["at_utc"] = now.astimezone(timezone.utc).isoformat()
    return out
