"""Financing-rate integrity for the paper ledgers (2026-11-02; compliance fix + pre-registration amendment v0.4).

A missing rate is not 0%. A stale observation is not a current rate. A policy or money-market rate is not a broker
financing charge: everything booked here is the pre-registered PROXY model ("estimated, unverified").

Layers (kept separate):
  fetch       one read-only GET per series (FRED CSV), strict validation; returns observations or an error
  cache       per series: the history of SUCCESSFUL observations (each with the time it was first seen), the time of
              the last success, and the last attempt with its error. A failure is never cached as a value. After a
              failure the series is retried at most once per `retry_minutes`; a later success replaces the failure.
  resolve     the observation that applies to one 17:00 ET roll: the latest observation dated on or before the roll's
              New York date (never a later-dated one), with its ORIGINAL observation date, its age and a state:
                VALID / VALID_ZERO   within the valid age (a published 0% is valid; negative rates are valid)
                LATE                 carried forward within the approved band (flag CARRIED_FORWARD)
                STALE                older than the band            -> the roll is UNRESOLVED
                MISSING              no observation at all          -> the roll is UNRESOLVED
              (FETCH_FAILED describes a series whose last attempt failed; resolution still uses the last success.)
Thresholds (owner-approved 2026-11-01, amendment v0.4): DTB3 valid <= 3 US business days, carried 4-5, UNRESOLVED > 5;
IRSTCI01JPM156N (dated the 1st of the month) valid <= 95 days, carried 96-125, UNRESOLVED > 125.
"""
import math
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from src import clock as K

NY = ZoneInfo("America/New_York")
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s&cosd=%s"
BOOKABLE = ("VALID", "VALID_ZERO", "LATE")
BOUNDS = (-0.05, 0.25)                       # annual decimal; outside = invalid (units error or garbage)


def series_cfg(cfg):
    return cfg["financing"]["series"]


# ---------------------------------------------------------------- fetch (validation only; no state)

def fetch(series_id, now, http_get=None, lookback_days=400):
    """Observations [(obs_date, decimal, raw_text)] or an error string. Percent -> decimal exactly once."""
    import requests
    get = http_get or requests.get
    start = (now.astimezone(NY).date() - timedelta(days=lookback_days)).isoformat()
    try:
        r = get(FRED_CSV % (series_id, start), timeout=30)
    except Exception as ex:
        return None, "request failed: %s" % type(ex).__name__
    if getattr(r, "status_code", 200) != 200:
        return None, "HTTP %s" % r.status_code
    lines = (r.text or "").strip().splitlines()
    if not lines or "," not in lines[0] or series_id not in lines[0]:
        return None, "not a FRED CSV for %s (header %r)" % (series_id, lines[0][:40] if lines else "")
    obs, today = [], now.astimezone(NY).date()
    for ln in lines[1:]:
        parts = ln.split(",")
        if len(parts) != 2 or parts[1].strip() in (".", ""):
            continue                                     # FRED's own marker for no observation that day
        try:
            d = date.fromisoformat(parts[0].strip())
            pct = float(parts[1])
        except ValueError:
            return None, "malformed row %r" % ln[:40]
        if not math.isfinite(pct):
            return None, "non-finite value %r" % parts[1]
        v = pct / 100.0
        if not (BOUNDS[0] <= v <= BOUNDS[1]):
            return None, "value %s%% outside the plausible range (units?)" % parts[1]
        if d > today:
            return None, "observation dated in the future (%s)" % d
        obs.append((d, v, parts[1].strip()))
    if not obs:
        return None, "no observations in the response"
    return obs, None


# ---------------------------------------------------------------- cache

def refresh(fin_state, now, cfg, http_get=None):
    """Update the per-series cache in `fin_state` (a dict persisted in the runner state). Fetch when the last success
    is older than `refresh_hours`, except within `retry_minutes` of a failed attempt. Returns {key: action}."""
    fc = cfg["financing"]
    out = {}
    for key, sc in series_cfg(cfg).items():
        s = fin_state.setdefault(key, {"series": sc["id"], "history": [], "last_success_utc": None,
                                       "last_attempt_utc": None, "last_error": None})
        last_ok = datetime.fromisoformat(s["last_success_utc"]) if s["last_success_utc"] else None
        last_try = datetime.fromisoformat(s["last_attempt_utc"]) if s["last_attempt_utc"] else None
        if last_ok and now - last_ok < timedelta(hours=fc["refresh_hours"]):
            out[key] = "cached"
            continue
        if s["last_error"] and last_try and now - last_try < timedelta(minutes=fc["retry_minutes"]):
            out[key] = "waiting to retry"
            continue
        obs, err = fetch(sc["id"], now, http_get)
        s["last_attempt_utc"] = now.astimezone(timezone.utc).isoformat()
        if err:
            s["last_error"] = err
            out[key] = "FETCH_FAILED: %s" % err
            continue
        known = {h["obs_date"]: h for h in s["history"]}
        for d, v, raw in obs:
            h = known.get(d.isoformat())
            if h is None or h["value"] != v:                 # new or revised: first_seen = now (revisions are visible)
                known[d.isoformat()] = {"obs_date": d.isoformat(), "value": v, "raw": raw, "units": "percent per year",
                                        "first_seen_utc": now.astimezone(timezone.utc).isoformat(),
                                        "revised_from": h["value"] if h else None}
        hist = sorted(known.values(), key=lambda h: h["obs_date"])
        s["history"] = hist[-sc["keep"]:]
        s["last_success_utc"] = now.astimezone(timezone.utc).isoformat()
        s["last_error"] = None
        out[key] = "fetched %d observation(s), latest %s" % (len(obs), hist[-1]["obs_date"])
    return out


# ---------------------------------------------------------------- resolution

def _age(sc, obs_d, roll_d):
    if sc["age_unit"] == "us_business_days":
        hol = set(K.us_board_holidays(obs_d.year)) | set(K.us_board_holidays(roll_d.year))
        n, d = 0, obs_d
        while d < roll_d:
            d += timedelta(days=1)
            if d.weekday() < 5 and d not in hol:
                n += 1
        return n
    return (roll_d - obs_d).days


def resolve(fin_state, key, roll_t, cfg, now=None):
    """The observation that applies to the roll at `roll_t` (aware datetime), using only observations already fetched
    by `now` and dated on or before the roll's New York date. Returns a dict with state, value and provenance."""
    sc = series_cfg(cfg)[key]
    s = (fin_state or {}).get(key) or {}
    roll_d = roll_t.astimezone(NY).date()
    seen_by = now or roll_t
    cands = [h for h in s.get("history", []) if date.fromisoformat(h["obs_date"]) <= roll_d
             and datetime.fromisoformat(h["first_seen_utc"]) <= seen_by]
    base = {"series": sc["id"], "currency": sc["currency"], "type": sc["type"], "roll_ny_date": roll_d.isoformat(),
            "last_error": s.get("last_error"), "series_status": "FETCH_FAILED" if s.get("last_error") else "OK"}
    if not cands:
        return dict(base, state="MISSING", value=None, obs_date=None, age=None, age_unit=sc["age_unit"], carried_forward=False,
                    reason="no observation of %s dated on or before %s%s" % (
                        sc["id"], roll_d, " (last fetch failed: %s)" % s["last_error"] if s.get("last_error") else ""))
    h = cands[-1]
    age = _age(sc, date.fromisoformat(h["obs_date"]), roll_d)
    if age <= sc["valid_max"]:
        st = "VALID_ZERO" if h["value"] == 0 else "VALID"
    elif age <= sc["carry_max"]:
        st = "LATE"
    else:
        st = "STALE"
    return dict(base, state=st, value=h["value"], raw=h["raw"], obs_date=h["obs_date"], age=age, age_unit=sc["age_unit"],
                carried_forward=(st == "LATE"), first_seen_utc=h["first_seen_utc"],
                reason=None if st in BOOKABLE else "%s observation %s is %d %s old (limit %d)" % (
                    sc["id"], h["obs_date"], age, sc["age_unit"].replace("_", " "), sc["carry_max"]))


def info_line(res):
    if res["state"] in ("MISSING",):
        return "MISSING: %s" % res["reason"]
    tag = "CARRIED_FORWARD " if res.get("carried_forward") else ""
    return "%s%s %s %s (%s; age %s %s)" % (tag, "FRED", res["series"], res["obs_date"], res["state"], res["age"],
                                           res["age_unit"].replace("_", " "))


def from_legacy(rates, key, roll_t):
    """Adapter for callers that still pass {"usd": (rate or None, info)}: a None is MISSING, never 0%."""
    v, info = (rates or {}).get(key, (None, "UNKNOWN"))
    if v is None:
        return {"state": "MISSING", "value": None, "obs_date": None, "age": None, "age_unit": None, "carried_forward": False,
                "series": None, "reason": "rate not available (%s)" % info}
    return {"state": "VALID_ZERO" if v == 0 else "VALID", "value": v, "obs_date": None, "age": None, "age_unit": None,
            "carried_forward": False, "series": None, "reason": None, "legacy_info": info}


def series_status(fin_state, now, cfg):
    """Per series: state for a roll happening now, plus fetch health (for preflight and the digest)."""
    return {k: resolve(fin_state, k, now, cfg, now=now) for k in series_cfg(cfg)}
