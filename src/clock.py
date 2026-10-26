"""Global market clock (expansion plan step 2). Standard library only: IANA zones via zoneinfo, rule-based holidays.

All conversions use IANA zone names, never fixed offsets. London and New York change clocks on different dates,
so their gap is 5 hours most of the year and 4 hours for a few weeks in March and in October/November; Japan has no
DST, so Tokyo's offset from New York is 13 or 14 hours.

Conventions (labelled as conventions, not evidence):
  FX week:      opens Sunday 17:00 America/New_York, closes Friday 17:00 America/New_York
  FX day roll:  17:00 America/New_York (rollover/financing; Wednesday carries the weekend, i.e. 3 days)
  Sessions:     local business hours of each centre: Sydney 07:00-16:00, Tokyo 09:00-18:00, London 08:00-17:00,
                New York 08:00-17:00, each in its own zone. Which hours actually matter for a strategy is an
                empirical question (UNKNOWN until intraday data is approved).
Holidays (full-day closures, rule-based with explicit special days):
  us_nyse_holidays    NYSE (copied from tools/watchlist_signals.py, which stays unchanged)
  us_fed_holidays     Federal Reserve BANKS (Saturday holidays not observed)
  us_board_holidays   Federal Reserve BOARD, which publishes H.10/H.15: Saturday holidays are observed on the
                      preceding Friday (checked against every DEXJPUS gap 1990-2023; ad-hoc closures such as
                      2001-09-11, presidential funerals and inaugurations, and Dec 24/26 executive-order
                      closures are not rule-based and are listed in reports/infrastructure_audit.md)
  uk_bank_holidays    England and Wales, 1990+
  jp_national_holidays Japan national holidays 1990+, with substitute and citizens' holidays
  jp_bank_holidays    national holidays plus Dec 31 and Jan 2-3 (Tokyo bank closures)
"""
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

ZONES = {"UTC": ZoneInfo("UTC"), "New York": ZoneInfo("America/New_York"), "London": ZoneInfo("Europe/London"),
         "Tokyo": ZoneInfo("Asia/Tokyo"), "Sydney": ZoneInfo("Australia/Sydney")}
NY = ZONES["New York"]
SESSIONS = {"Sydney": ("Sydney", time(7), time(16)), "Tokyo": ("Tokyo", time(9), time(18)),
            "London": ("London", time(8), time(17)), "New York": ("New York", time(8), time(17))}
ROLL = time(17)


# ---------------------------------------------------------------- date helpers

def easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    return date(y, (h + l - 7 * m + 114) // 31, (h + l - 7 * m + 114) % 31 + 1)


def nth_weekday(y, mo, wd, n):
    d = date(y, mo, 1)
    return d + timedelta(days=(wd - d.weekday()) % 7, weeks=n - 1)


def last_weekday(y, mo, wd):
    d = (date(y, mo + 1, 1) if mo < 12 else date(y + 1, 1, 1)) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - wd) % 7)


# ---------------------------------------------------------------- US

@lru_cache(maxsize=None)
def us_nyse_holidays(y):
    obs = lambda d: d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d
    h = {nth_weekday(y, 1, 0, 3), nth_weekday(y, 2, 0, 3), easter(y) - timedelta(days=2), last_weekday(y, 5, 0),
         obs(date(y, 7, 4)), nth_weekday(y, 9, 0, 1), nth_weekday(y, 11, 3, 4), obs(date(y, 12, 25))}
    if y >= 2022:
        h.add(obs(date(y, 6, 19)))
    if date(y, 1, 1).weekday() != 5:
        h.add(obs(date(y, 1, 1)))
    return frozenset(h)


@lru_cache(maxsize=None)
def us_fed_holidays(y):
    """Federal Reserve holidays: Sunday holidays move to Monday; Saturday holidays are not observed."""
    sun = lambda d: d + timedelta(days=1) if d.weekday() == 6 else d
    h = {nth_weekday(y, 1, 0, 3), nth_weekday(y, 2, 0, 3), last_weekday(y, 5, 0), nth_weekday(y, 9, 0, 1),
         nth_weekday(y, 10, 0, 2), nth_weekday(y, 11, 3, 4)}
    for d in (date(y, 1, 1), date(y, 7, 4), date(y, 11, 11), date(y, 12, 25)) + ((date(y, 6, 19),) if y >= 2021 else ()):
        if d.weekday() != 5:
            h.add(sun(d))
    return frozenset(h)


@lru_cache(maxsize=None)
def us_board_holidays(y):
    """Federal Reserve Board (H.10 / H.15 publication): Sunday holidays move to Monday; from 2010, Saturday holidays move
    to Friday. EMPIRICAL rule from the DEXJPUS gaps: H.10 was published on such Fridays up to 2009-07-03 and not from
    2010-12-24 on; 2021-06-18 (Juneteenth, enacted the day before) still had a rate."""
    shift = y >= 2010
    sat_sun = lambda d: d + timedelta(days=1) if d.weekday() == 6 else \
        (d - timedelta(days=1) if shift and d != date(2021, 6, 19) else None) if d.weekday() == 5 else d
    h = {nth_weekday(y, 1, 0, 3), nth_weekday(y, 2, 0, 3), last_weekday(y, 5, 0), nth_weekday(y, 9, 0, 1),
         nth_weekday(y, 10, 0, 2), nth_weekday(y, 11, 3, 4)}
    for d in (date(y, 7, 4), date(y, 11, 11), date(y, 12, 25)) + ((date(y, 6, 19),) if y >= 2021 else ()):
        h.add(sat_sun(d))
    if y + 1 >= 2011 and date(y + 1, 1, 1).weekday() == 5:          # next New Year's Day on a Saturday -> Dec 31
        h.add(date(y, 12, 31))
    if date(y, 1, 1).weekday() != 5:
        h.add(sat_sun(date(y, 1, 1)))
    return frozenset(x for x in h if x is not None)


# ---------------------------------------------------------------- UK (England and Wales)

UK_SPECIAL_ADD = {date(1999, 12, 31), date(2002, 6, 3), date(2011, 4, 29), date(2012, 6, 5), date(2022, 6, 3),
                  date(2022, 9, 19), date(2023, 5, 8)}
UK_MOVED = {(1995, "early_may"): date(1995, 5, 8), (2020, "early_may"): date(2020, 5, 8),
            (2002, "spring"): date(2002, 6, 4), (2012, "spring"): date(2012, 6, 4), (2022, "spring"): date(2022, 6, 2)}


@lru_cache(maxsize=None)
def uk_bank_holidays(y):
    h = set()
    nyd = date(y, 1, 1)
    h.add(nyd + timedelta(days={5: 2, 6: 1}.get(nyd.weekday(), 0)))
    e = easter(y)
    h |= {e - timedelta(days=2), e + timedelta(days=1)}
    h.add(UK_MOVED.get((y, "early_may"), nth_weekday(y, 5, 0, 1)))
    h.add(UK_MOVED.get((y, "spring"), last_weekday(y, 5, 0)))
    h.add(last_weekday(y, 8, 0))
    xmas, box = date(y, 12, 25), date(y, 12, 26)
    if xmas.weekday() == 5:                     # Sat: Christmas -> Mon 27, Boxing (Sun) -> Tue 28
        h |= {date(y, 12, 27), date(y, 12, 28)}
    elif xmas.weekday() == 6:                   # Sun: Boxing Mon 26, Christmas -> Tue 27
        h |= {date(y, 12, 26), date(y, 12, 27)}
    elif box.weekday() == 5:                    # Fri Christmas, Sat Boxing -> Mon 28
        h |= {xmas, date(y, 12, 28)}
    else:
        h |= {xmas, box}
    h |= {d for d in UK_SPECIAL_ADD if d.year == y}
    return frozenset(h)


# ---------------------------------------------------------------- Japan

def _equinoxes(y):
    """Vernal and autumnal equinox days (formula valid 1980-2099, standard in Japanese calendar computation)."""
    k = y - 1980
    return date(y, 3, int(20.8431 + 0.242194 * k - k // 4)), date(y, 9, int(23.2488 + 0.242194 * k - k // 4))


JP_SPECIAL = {date(1990, 11, 12), date(1993, 6, 9), date(2019, 4, 30), date(2019, 5, 1), date(2019, 5, 2),
              date(2019, 10, 22)}


@lru_cache(maxsize=None)
def jp_national_holidays(y):
    if y < 1990:
        raise ValueError("Japanese calendar implemented from 1990")
    h = {date(y, 1, 1), date(y, 2, 11), date(y, 4, 29), date(y, 5, 3), date(y, 5, 5), date(y, 11, 3), date(y, 11, 23)}
    h.add(date(y, 1, 15) if y < 2000 else nth_weekday(y, 1, 0, 2))                       # Coming of Age
    if y <= 2018:
        h.add(date(y, 12, 23))                                                               # Emperor's Birthday
    elif y >= 2020:
        h.add(date(y, 2, 23))
    ve, ae = _equinoxes(y)
    h |= {ve, ae}
    if y >= 2007:
        h.add(date(y, 5, 4))                                                                 # Greenery Day (May 4)
    marine = {2020: date(2020, 7, 23), 2021: date(2021, 7, 22)}
    if 1996 <= y <= 2002:
        h.add(date(y, 7, 20))
    elif y >= 2003:
        h.add(marine.get(y, nth_weekday(y, 7, 0, 3)))
    mountain = {2020: date(2020, 8, 10), 2021: date(2021, 8, 8)}
    if y >= 2016:
        h.add(mountain.get(y, date(y, 8, 11)))
    h.add(date(y, 9, 15) if y <= 2002 else nth_weekday(y, 9, 0, 3))                       # Respect for the Aged
    sports = {2020: date(2020, 7, 24), 2021: date(2021, 7, 23)}
    h.add(date(y, 10, 10) if y < 2000 else sports.get(y, nth_weekday(y, 10, 0, 2)))         # Sports Day
    h |= {d for d in JP_SPECIAL if d.year == y}
    # citizens' holiday: a day sandwiched between two holidays (May 4 before 2007; some Septembers)
    for d in sorted(h):
        mid = d + timedelta(days=1)
        if mid not in h and (mid + timedelta(days=1)) in h and mid.weekday() != 6:
            h.add(mid)
    # substitute holiday for a holiday falling on Sunday: Monday (to 2006), the next non-holiday day (2007+)
    for d in sorted(h):
        if d.weekday() == 6:
            sub = d + timedelta(days=1)
            if y >= 2007:
                while sub in h:
                    sub += timedelta(days=1)
            if sub not in h:
                h.add(sub)
    return frozenset(x for x in h if x.year == y)


@lru_cache(maxsize=None)
def jp_bank_holidays(y):
    return frozenset(jp_national_holidays(y) | {date(y, 1, 2), date(y, 1, 3), date(y, 12, 31)})


def is_business_day(d, calendar):
    return d.weekday() < 5 and d not in calendar(d.year)


# ---------------------------------------------------------------- time and sessions

def to_zone(dt, zone):
    if dt.tzinfo is None:
        raise ValueError("naive datetime: attach a time zone first")
    return dt.astimezone(ZONES[zone])


def offset_hours(zone_a, zone_b, at):
    """Hours zone_a is ahead of zone_b at the instant `at` (aware datetime)."""
    a, b = to_zone(at, zone_a).utcoffset(), to_zone(at, zone_b).utcoffset()
    return (a - b).total_seconds() / 3600


def fx_market_open(at):
    """True between Sunday 17:00 and Friday 17:00 New York time (convention; holidays not modelled here)."""
    n = to_zone(at, "New York")
    wd, t = n.weekday(), n.time()
    if wd == 5:
        return False
    if wd == 6:
        return t >= ROLL
    if wd == 4:
        return t < ROLL
    return True


def fx_trade_date(at):
    """FX value/trade date: the New York date, rolled forward at 17:00 New York."""
    n = to_zone(at, "New York")
    d = n.date() + timedelta(days=1) if n.time() >= ROLL else n.date()
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def rollover_days(trade_date):
    """Days of financing charged at the roll ending this trade date: 3 on Wednesday (weekend), else 1."""
    return 3 if trade_date.weekday() == 2 else 1


def active_sessions(at, holiday_aware=True):
    out = []
    cal = {"Tokyo": jp_bank_holidays, "London": uk_bank_holidays, "New York": us_fed_holidays}
    for name, (zone, start, end) in SESSIONS.items():
        loc = to_zone(at, zone)
        if loc.weekday() >= 5 or not (start <= loc.time() < end):
            continue
        if holiday_aware and name in cal and loc.date() in cal[name](loc.year):
            continue
        out.append(name)
    return out


def next_dst_change(zone, after, horizon_days=400):
    """First instant after `after` at which the zone's UTC offset changes (None if none within the horizon)."""
    z = ZONES[zone]
    t = after.astimezone(z)
    off = t.utcoffset()
    for h in range(1, horizon_days * 24):
        u = (after + timedelta(hours=h)).astimezone(z)
        if u.utcoffset() != off:
            lo = after + timedelta(hours=h - 1)
            for m in range(0, 61):
                v = (lo + timedelta(minutes=m)).astimezone(z)
                if v.utcoffset() != off:
                    return lo + timedelta(minutes=m)
    return None


def snapshot(at):
    """Human-readable clock state for reports."""
    return {"utc": to_zone(at, "UTC").strftime("%Y-%m-%d %H:%M %Z"),
            **{z: to_zone(at, z).strftime("%a %H:%M %Z") for z in ("New York", "London", "Tokyo", "Sydney")},
            "fx_open": fx_market_open(at), "fx_trade_date": str(fx_trade_date(at)),
            "active_sessions": active_sessions(at),
            "london_minus_new_york_h": offset_hours("London", "New York", at),
            "tokyo_minus_new_york_h": offset_hours("Tokyo", "New York", at)}
