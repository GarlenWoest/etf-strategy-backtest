"""Market clock: IANA conversions, DST edge cases, FX week, rollover, holiday calendars against known lists."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from src import clock as C

UTC = ZoneInfo("UTC")


def at(s):
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


def test_london_new_york_gap_changes_with_different_dst_dates():
    assert C.offset_hours("London", "New York", at("2026-01-15T12:00")) == 5
    assert C.offset_hours("London", "New York", at("2026-03-20T12:00")) == 4    # US on DST, UK not yet
    assert C.offset_hours("London", "New York", at("2026-07-01T12:00")) == 5
    assert C.offset_hours("London", "New York", at("2026-10-30T12:00")) == 4    # UK back on GMT, US not yet


def test_tokyo_has_no_dst():
    assert C.offset_hours("Tokyo", "New York", at("2026-07-01T12:00")) == 13
    assert C.offset_hours("Tokyo", "New York", at("2026-01-15T12:00")) == 14
    assert C.next_dst_change("Tokyo", at("2026-01-01T00:00")) is None


def test_next_dst_change_new_york_2026():
    assert C.next_dst_change("New York", at("2026-01-01T00:00")) == at("2026-03-08T07:00")


def test_fx_week_and_roll():
    ny = ZoneInfo("America/New_York")
    assert not C.fx_market_open(datetime(2026, 10, 24, 12, tzinfo=ny))              # Saturday
    assert not C.fx_market_open(datetime(2026, 10, 25, 16, 59, tzinfo=ny))          # Sunday before 17:00
    assert C.fx_market_open(datetime(2026, 10, 25, 17, 0, tzinfo=ny))
    assert not C.fx_market_open(datetime(2026, 10, 23, 17, 0, tzinfo=ny))           # Friday 17:00 close
    assert C.fx_trade_date(datetime(2026, 10, 23, 18, tzinfo=ny)) == date(2026, 10, 26)
    assert C.rollover_days(date(2026, 10, 28)) == 3 and C.rollover_days(date(2026, 10, 27)) == 1


def test_naive_datetime_rejected():
    with pytest.raises(ValueError):
        C.to_zone(datetime(2026, 1, 1, 12), "Tokyo")


def test_japan_holidays_2019_and_2020():
    j19 = sorted(C.jp_national_holidays(2019))
    exp19 = [date(2019, 1, 1), date(2019, 1, 14), date(2019, 2, 11), date(2019, 3, 21), date(2019, 4, 29), date(2019, 4, 30),
             date(2019, 5, 1), date(2019, 5, 2), date(2019, 5, 3), date(2019, 5, 4), date(2019, 5, 5), date(2019, 5, 6),
             date(2019, 7, 15), date(2019, 8, 11), date(2019, 8, 12), date(2019, 9, 16), date(2019, 9, 23), date(2019, 10, 14),
             date(2019, 10, 22), date(2019, 11, 3), date(2019, 11, 4), date(2019, 11, 23)]
    assert j19 == exp19
    exp20 = [date(2020, 1, 1), date(2020, 1, 13), date(2020, 2, 11), date(2020, 2, 23), date(2020, 2, 24), date(2020, 3, 20),
             date(2020, 4, 29), date(2020, 5, 3), date(2020, 5, 4), date(2020, 5, 5), date(2020, 5, 6), date(2020, 7, 23),
             date(2020, 7, 24), date(2020, 8, 10), date(2020, 9, 21), date(2020, 9, 22), date(2020, 11, 3), date(2020, 11, 23)]
    assert sorted(C.jp_national_holidays(2020)) == exp20


def test_japan_historical_rules():
    assert date(1999, 1, 15) in C.jp_national_holidays(1999)          # fixed Coming of Age before 2000
    assert date(1999, 10, 11) in C.jp_national_holidays(1999)         # Sports Day Oct 10 was a Sunday -> Monday
    assert date(2009, 9, 22) in C.jp_national_holidays(2009)          # citizens' holiday
    assert date(2005, 5, 4) in C.jp_national_holidays(2005)           # citizens' holiday before Greenery Day moved
    assert date(1998, 12, 23) in C.jp_national_holidays(1998) and date(2019, 12, 23) not in C.jp_national_holidays(2019)
    assert date(2026, 1, 2) in C.jp_bank_holidays(2026) and date(2026, 1, 2) not in C.jp_national_holidays(2026)


def test_uk_bank_holidays_2020_and_2022():
    assert sorted(C.uk_bank_holidays(2020)) == [date(2020, 1, 1), date(2020, 4, 10), date(2020, 4, 13), date(2020, 5, 8),
                                                 date(2020, 5, 25), date(2020, 8, 31), date(2020, 12, 25), date(2020, 12, 28)]
    assert sorted(C.uk_bank_holidays(2022)) == [date(2022, 1, 3), date(2022, 4, 15), date(2022, 4, 18), date(2022, 5, 2),
                                                 date(2022, 6, 2), date(2022, 6, 3), date(2022, 8, 29), date(2022, 9, 19),
                                                 date(2022, 12, 26), date(2022, 12, 27)]


def test_us_fed_holidays_2022_saturday_not_observed():
    assert sorted(C.us_fed_holidays(2022)) == [date(2022, 1, 17), date(2022, 2, 21), date(2022, 5, 30), date(2022, 6, 20),
                                                date(2022, 7, 4), date(2022, 9, 5), date(2022, 10, 10), date(2022, 11, 11),
                                                date(2022, 11, 24), date(2022, 12, 26)]
    assert date(2021, 12, 31) not in C.us_fed_holidays(2021)          # New Year 2022 fell on a Saturday


def test_active_sessions_overlap_and_holiday():
    s = C.active_sessions(at("2026-10-21T13:00"))                     # 09:00 NY, 14:00 London (both on DST)
    assert "London" in s and "New York" in s and "Tokyo" not in s
    assert "London" not in C.active_sessions(at("2026-12-25T12:00"))  # Christmas
