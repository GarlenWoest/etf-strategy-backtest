"""Financing edge cases added after the outside review (audit item 3, owner approval 2026-11-02). TESTS ONLY: they
document the behaviour of the frozen v0.4 rules (17:00 ET roll, triple on Wednesday, per-roll rate resolution by
observation date); no code was changed. SYNTHETIC inputs; expected amounts come from the hand reference in
tests/test_live_usdjpy_financing.py."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from src.live_usdjpy import paper as PP
from tests.test_live_usdjpy_financing import CFG, enter, reference, reg  # noqa: F401  (fixture re-used)

NY = ZoneInfo("America/New_York")


def hist(usd, jpy):
    mk = lambda rows: {"history": [{"obs_date": d, "value": v, "raw": str(v * 100), "first_seen_utc": s} for d, v, s in rows]}
    return {"usd": mk(usd), "jpy": mk(jpy)}


BASE = hist([("2026-11-20", 0.04, "2026-11-21T00:00:00+00:00")], [("2026-10-01", 0.01, "2026-11-01T00:00:00+00:00")])


def fins(reg):
    return [r["payload"] for r in reg.records("fill") if r["payload"]["type"] == "financing"]


def test_holidays_do_not_move_rolls_under_the_frozen_v04_convention():
    """US Thanksgiving (Thu 2026-11-26) and a Japanese holiday (Mon 2026-11-23) are ordinary 1-day rolls; Wednesday
    is the 3-day roll. Brokers may shift value dates around holidays: changing that would need amendment v0.5."""
    a = datetime(2026, 11, 22, 22, 0, tzinfo=NY)                          # Sun evening
    b = datetime(2026, 11, 27, 18, 0, tzinfo=NY)                          # Fri after the roll
    got = [(t.date().isoformat(), d) for t, d in PP.rolls_between(a, b)]
    assert got == [("2026-11-23", 1), ("2026-11-24", 1), ("2026-11-25", 3), ("2026-11-26", 1), ("2026-11-27", 1)]


@pytest.mark.parametrize("direction", [1, -1])
def test_negative_jpy_rate_signs_match_the_reference(reg, direction):  # noqa: F811
    t0 = datetime(2026, 11, 23, 21, 0, tzinfo=timezone.utc)               # Mon 16:00 EST
    enter(reg, direction, 0.5, 150.0, t0)
    st0 = PP.state(reg, "F002", CFG)
    rates = hist([("2026-11-20", 0.04, "2026-11-21T00:00:00+00:00")], [("2026-10-01", -0.001, "2026-11-01T00:00:00+00:00")])
    PP.manage(reg, CFG, datetime(2026, 11, 23, 22, 2, tzinfo=timezone.utc), 150.0, rates, "s1")
    u, j, c = reference([("r", 1)], st0["usd_pos"], st0["jpy"], {"r": 0.04}, {"r": -0.001})
    st = PP.state(reg, "F002", CFG)
    assert st["jpy"] == pytest.approx(j, abs=1e-6) and st["usd_pos"] == pytest.approx(u, abs=1e-9)
    f = fins(reg)[0]
    # long USD = short JPY (jpy leg < 0): a negative JPY rate is EARNED on the borrowed yen; short USD pays it
    assert (f["jpy_interest"] > 0) if direction > 0 else (f["jpy_interest"] < 0)


def test_catch_up_after_four_missed_days_books_each_roll_once_with_its_own_rate(reg):  # noqa: F811
    """Mac off Mon 16:00 -> Fri 17:02: one run books Mon, Tue, Wed(3), Thu, Fri in order. v0.4 resolves each roll by
    OBSERVATION DATE (<= the roll's NY date) among observations fetched by the time of the run, so a rate dated Tue
    but first fetched later is used for Tue's roll on catch-up (live scanning would have used it from the next roll)."""
    t0 = datetime(2026, 11, 23, 21, 0, tzinfo=timezone.utc)
    enter(reg, 1, 0.5, 150.0, t0)
    st0 = PP.state(reg, "F002", CFG)
    rates = hist([("2026-11-20", 0.04, "2026-11-21T00:00:00+00:00"), ("2026-11-24", 0.05, "2026-11-26T00:00:00+00:00")],
                 [("2026-10-01", 0.01, "2026-11-01T00:00:00+00:00")])
    PP.manage(reg, CFG, datetime(2026, 11, 27, 22, 2, tzinfo=timezone.utc), 150.0, rates, "late")
    f = fins(reg)
    assert [x["days"] for x in f] == [1, 1, 3, 1, 1]
    assert [x["roll_et"][:10] for x in f] == ["2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26", "2026-11-27"]
    assert [x["r_usd"] for x in f] == [0.04, 0.05, 0.05, 0.05, 0.05]
    rolls = [(x["roll_et"], x["days"]) for x in f]
    u, j, c = reference(rolls, st0["usd_pos"], st0["jpy"], {t: r["r_usd"] for (t, _), r in zip(rolls, f)}, {t: 0.01 for t, _ in rolls})
    st = PP.state(reg, "F002", CFG)
    assert st["usd_pos"] == pytest.approx(u, abs=1e-9) and st["cash"] - st0["cash"] == pytest.approx(c, abs=1e-9)
    PP.manage(reg, CFG, datetime(2026, 11, 27, 22, 17, tzinfo=timezone.utc), 150.0, rates, "late2")
    assert len(fins(reg)) == 5                                            # the next run books nothing twice


def test_rolls_across_the_dst_change_are_at_17_ny_both_sides():
    a = datetime(2026, 10, 30, 20, 0, tzinfo=timezone.utc)                # Fri 16:00 EDT
    b = datetime(2026, 11, 2, 22, 30, tzinfo=timezone.utc)                # Mon 17:30 EST
    got = PP.rolls_between(a, b)
    assert [(t.astimezone(timezone.utc).isoformat(), d) for t, d in got] == [
        ("2026-10-30T21:00:00+00:00", 1), ("2026-11-02T22:00:00+00:00", 1)]   # 17:00 EDT = 21:00Z; 17:00 EST = 22:00Z


def test_scans_either_side_of_the_roll_book_exactly_one(reg):  # noqa: F811
    t0 = datetime(2026, 11, 23, 21, 0, tzinfo=timezone.utc)
    enter(reg, 1, 0.5, 150.0, t0)
    PP.manage(reg, CFG, datetime(2026, 11, 23, 21, 59, tzinfo=timezone.utc), 150.0, BASE, "a")   # 16:59 EST
    assert fins(reg) == []
    PP.manage(reg, CFG, datetime(2026, 11, 23, 22, 1, tzinfo=timezone.utc), 150.0, BASE, "b")    # 17:01 EST
    PP.manage(reg, CFG, datetime(2026, 11, 23, 22, 2, tzinfo=timezone.utc), 150.0, BASE, "c")
    assert len(fins(reg)) == 1 and fins(reg)[0]["roll_et"].startswith("2026-11-23T17:00")
