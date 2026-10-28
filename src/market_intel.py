"""Current-market intelligence (Phase B, 2026-10-28): pure logic, no network. READ-ONLY monitoring, not research.

Isolation: this module may be used only by tools/market_intel.py, which writes only live/intel/. No research module
may import it, and nothing it produces may enter data/, research_log.csv or any study (config market_intel.isolation;
enforced by tests/test_market_intel.py).

Every observation carries: source, source URL or symbol, quote type, source timestamp (UTC), retrieval timestamp
(UTC), the source's own time zone, age, expected update frequency and a freshness status:
  LIVE               market open, age within the live threshold (plus any delay the source declares)
  DELAYED            market open, older than live but within the delayed threshold, or a source with a declared delay
  CLOSED_LAST_PRICE  market closed and the last price is from within the tolerance before the close
  CURRENT            an official daily or weekly reference within its maximum age
  STALE              anything older; never treated as current
  UNAVAILABLE        no value, no timestamp, or a timestamp in the future
A specialist is "DATA OK" only if its primary price is LIVE, DELAYED, CLOSED_LAST_PRICE (or CURRENT) and its volatility
could be computed; "STALE MARKET DATA" if the primary price is stale; otherwise "INSUFFICIENT DATA".
"""
import math
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src import clock as K

UTC = timezone.utc
NY = K.ZONES["New York"]
CET = ZoneInfo("Europe/Berlin")          # Central European (Summer) Time
FRESH = ("LIVE", "DELAYED", "CLOSED_LAST_PRICE", "CURRENT")


# ---------------------------------------------------------------- market sessions

def nyse_open(at):
    """NYSE regular session 09:30-16:00 New York on NYSE trading days (early closes not modelled)."""
    n = at.astimezone(NY)
    return n.weekday() < 5 and n.date() not in K.us_nyse_holidays(n.year) and time(9, 30) <= n.time() < time(16)


def cme_metals_open(at):
    """CME Globex metals: Sunday 18:00 - Friday 17:00 New York with a daily 17:00-18:00 break (holidays not modelled)."""
    n = at.astimezone(NY)
    wd, t = n.weekday(), n.time()
    if wd == 5 or (wd == 6 and t < time(18)) or (wd == 4 and t >= time(17)):
        return False
    return not (time(17) <= t < time(18))


SESSIONS = {"fx": K.fx_market_open, "nyse": nyse_open, "cme_metals": cme_metals_open}


def last_close(session, now, horizon_days=6):
    """Most recent instant at which `session` went from open to closed, at or before `now` (minute resolution)."""
    is_open = SESSIONS[session]
    t = now.astimezone(UTC).replace(second=0, microsecond=0)
    prev = is_open(t)
    for _ in range(horizon_days * 24 * 60):
        earlier = t - timedelta(minutes=1)
        o = is_open(earlier)
        if o and not prev:
            return t
        t, prev = earlier, o
    return None


# ---------------------------------------------------------------- freshness

def freshness_intraday(source_ts, now, rule, session, declared_delay_s=0):
    """Status of an intraday price. source_ts/now: aware datetimes. rule: config freshness block."""
    if source_ts is None:
        return "UNAVAILABLE", None, "no timestamp"
    age = (now - source_ts).total_seconds()
    if age < -60:
        return "UNAVAILABLE", age, "timestamp in the future"
    if SESSIONS[session](now):
        if age <= rule["live_max_age_s"] + declared_delay_s:
            return ("LIVE" if declared_delay_s == 0 else "DELAYED"), age, "market open"
        if age <= rule["delayed_max_age_s"] + declared_delay_s:
            return "DELAYED", age, "market open"
        return "STALE", age, "market open; older than %d s" % (rule["delayed_max_age_s"] + declared_delay_s)
    lc = last_close(session, now)
    if lc is not None and source_ts >= lc - timedelta(seconds=rule["closed_tolerance_s"]):
        return "CLOSED_LAST_PRICE", age, "market closed since %s" % lc.astimezone(NY).strftime("%a %Y-%m-%d %H:%M ET")
    return "STALE", age, "market closed; last price is not from the last session's close"


def freshness_reference(obs_date, today, max_age_calendar_days):
    """Official daily/weekly references: CURRENT if the observation date is within the maximum age."""
    if obs_date is None:
        return "UNAVAILABLE", None
    age_d = (today - obs_date).days
    return ("CURRENT" if age_d <= max_age_calendar_days else "STALE"), age_d


def business_days_between(a, b):
    """Weekdays in (a, b]."""
    return int(np.busday_count(a + timedelta(days=1), b + timedelta(days=1))) if b > a else 0


def freshness_daily_close(last_bar_date, today, max_age_business_days):
    if last_bar_date is None:
        return "UNAVAILABLE", None
    n = business_days_between(last_bar_date, today)
    return ("CURRENT" if n <= max_age_business_days else "STALE"), n


# ---------------------------------------------------------------- quantitative estimates

def realized_vol(closes, window, min_closes, annualisation_days=252):
    """Annualised standard deviation of the last `window` daily log returns; None if too few closes."""
    c = pd.Series(closes).dropna()
    if len(c) < min_closes or (c <= 0).any():
        return None
    r = np.log(c).diff().dropna().iloc[-window:]
    return float(r.std(ddof=1) * math.sqrt(annualisation_days))


def specialist_status(primary_status, vol, words):
    if primary_status == "STALE":
        return words["stale"]
    if primary_status not in FRESH or vol is None:
        return words["missing"]
    return words["ok"]


# ---------------------------------------------------------------- time alignment and accuracy

def value_at(bars, ref_ts, max_gap_s=120, bar_s=60):
    """Close of the last 1-minute bar that ENDS at or before ref_ts (bars indexed by bar START, aware). Returns
    (value, bar_end) or (None, None) if that bar ends more than max_gap_s before ref_ts. Never uses a later bar."""
    if bars is None or len(bars) == 0:
        return None, None
    ends = bars.index + pd.Timedelta(seconds=bar_s)
    ok = ends <= pd.Timestamp(ref_ts)
    if not ok.any():
        return None, None
    i = np.flatnonzero(ok)[-1]
    end = ends[i]
    if (pd.Timestamp(ref_ts) - end).total_seconds() > max_gap_s or pd.isna(bars.iloc[i]):
        return None, None
    return float(bars.iloc[i]), end.to_pydatetime()


def compare(value, ref, pip):
    d = value - ref
    return {"abs": abs(d), "diff": d, "pct": 100 * d / ref, "bp": 1e4 * d / ref, "pips": d / pip}


def decimals(rate_str):
    return max(0, -Decimal(rate_str).as_tuple().exponent)


def _rounding(rate_str, dp=None):
    """Half a unit in the last published decimal place, as a relative error. The ECB XML drops trailing zeros
    ('1.113' for 1.1130), so pass the currency's usual precision `dp` (the most decimals seen in the file)."""
    return 0.5 * 10 ** (-(decimals(rate_str) if dp is None else dp)) / float(Decimal(rate_str))


def ecb_cross(numerator_str, denominator_str, num_dp=None, den_dp=None):
    """Cross rate from two ECB euro rates (e.g. JPY per EUR / USD per EUR = JPY per USD) and the bound on its
    rounding error (relative), from the published precision."""
    v = float(Decimal(numerator_str) / Decimal(denominator_str))
    return v, _rounding(numerator_str, num_dp) + _rounding(denominator_str, den_dp)


def ecb_concertation_utc(d):
    """14:10 Central European time (CET/CEST) on date d, in UTC. The ECB says 'normally ... around 14:10 CET'."""
    return datetime.combine(d, time(14, 10), tzinfo=CET).astimezone(UTC)


def h10_noon_utc(d):
    """12:00 New York on date d, in UTC (H.10: 'noon buying rates in New York')."""
    return datetime.combine(d, time(12), tzinfo=NY).astimezone(UTC)
