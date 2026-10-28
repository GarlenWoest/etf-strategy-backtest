"""Paper books (PAPER, FICTIONAL MONEY): fills, costs, hold rule, journal rules and tamper detection. Offline data."""
import importlib.util
import shutil
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from src import PROJECT_ROOT

spec = importlib.util.spec_from_file_location("pb", PROJECT_ROOT / "tools" / "paper_books.py")
PB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PB)
DIR = PROJECT_ROOT / "tmp" / "test_paper"
START = date(2026, 10, 26)                                  # Monday
TICK = sorted(set(PB.A_INSTR) | set(PB.B_UNIVERSE) | {"^IRX"})


def fake(tickers, start):
    idx = pd.bdate_range("2026-10-12", "2026-12-31")
    rng = np.random.default_rng(1)
    c = pd.DataFrame({t: 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx)))) for t in TICK}, index=idx)
    c["^IRX"] = 5.04
    o = c * 0.995
    dv = pd.DataFrame(0.0, index=idx, columns=TICK)
    dv.loc[pd.Timestamp("2026-11-02"), "SPY"] = 1.0
    return pd.concat({"Open": o, "Close": c, "Dividends": dv}, axis=1)


@pytest.fixture
def paper(monkeypatch):
    shutil.rmtree(DIR, ignore_errors=True)
    monkeypatch.setattr(PB, "download", fake)
    monkeypatch.setattr(PB, "now_et", lambda: datetime(2026, 12, 31, 18, 0, tzinfo=PB.ET))   # after hours: updates allowed
    monkeypatch.setattr(PB, "live_targets", lambda: ("2026-09-30", {"V122": {"VTI": 0.25, "DBC": 0.25},
                                                                    "V074": {"UPRO": 0.25, "TQQQ": 0.25}}))
    p = PB.Paper(DIR)
    PB.init(p, START)
    yield p
    shutil.rmtree(DIR, ignore_errors=True)


def J(p, d, now=None, **kw):
    """Submit a journal entry; written at 18:00 ET on the decision Sunday unless `now` says otherwise."""
    e = {"decision_date": d, "entry_reason": "r", "wrong_if": "w", "planned_exit": "x", **kw}
    now = now or datetime.fromisoformat(d + "T18:00").replace(tzinfo=PB.ET)
    PB.journal(p, __import__("json").dumps(e), now)


def at(s):
    return datetime.fromisoformat(s).replace(tzinfo=PB.ET)


def test_fills_costs_and_mark_to_market(paper):
    J(paper, "2026-10-25", action="BUY", instrument="GLD", size_pct=50, exit_rule={"exit_on_or_after": "2026-11-06"})
    PB.update(paper, START)
    px = fake(None, None)
    o, c = px["Open"].loc["2026-10-26"], px["Close"].loc["2026-10-26"]
    v = paper.read_csv(paper.values).iloc[0]
    assert abs(v["SPY"] - 100 / (o["SPY"] * 1.0007) * c["SPY"]) < 1e-3
    gld = 50 / (o["GLD"] * 1.0007)
    assert abs(v["B"] - (50 + gld * c["GLD"])) < 1e-3
    # each sleeve is $50, so a 25% target is $12.50 per position; the other $25 per sleeve stays in cash
    assert abs(v["A"] - (12.5 / (o["VTI"] * 1.0007) * c["VTI"] + 12.5 / (o["DBC"] * 1.0007) * c["DBC"] + 50
                         + 12.5 / (o["UPRO"] * 1.001) * c["UPRO"] + 12.5 / (o["TQQQ"] * 1.001) * c["TQQQ"])) < 1e-3


def test_planned_exit_after_min_hold_and_dividends(paper):
    J(paper, "2026-10-25", action="BUY", instrument="GLD", size_pct=50, exit_rule={"exit_on_or_after": "2026-10-27"})
    PB.update(paper, date(2026, 11, 6))
    tr = paper.read_csv(paper.trades)
    sell = tr[(tr["book"] == "B") & (tr["side"] == "SELL")]
    assert list(sell["date"]) == ["2026-11-02"]                 # bought 10-26; 5 trading days later; rule hit earlier
    s = paper.load()
    assert s["books"]["SPY"]["cash"] > 0                        # $1 dividend on 11-02 paid in cash


def test_journal_rules(paper):
    with pytest.raises(SystemExit):
        J(paper, "2026-10-24", action="NO_TRADE")               # not a Sunday
    with pytest.raises(SystemExit):
        J(paper, "2026-10-25", action="BUY", instrument="XLE", size_pct=10, exit_rule={"stop_below": 1})
    with pytest.raises(SystemExit):
        J(paper, "2026-10-25", action="BUY", instrument="GLD", size_pct=10, exit_rule={})
    J(paper, "2026-10-25", action="BUY", instrument="GLD", size_pct=10, exit_rule={"stop_below": 1})
    with pytest.raises(SystemExit):
        J(paper, "2026-10-25", action="NO_TRADE")               # second decision in the same week
    PB.update(paper, date(2026, 10, 27))
    paper.load()
    with pytest.raises(SystemExit):                             # would sell after < 5 trading days? (fill 11-02 = 5: allowed)
        J(paper, "2026-11-01", action="SELL", instrument="SLV")  # not held
    J(paper, "2026-11-01", action="SELL", instrument="GLD")


def test_journal_tamper_detected(paper):
    J(paper, "2026-10-25", action="NO_TRADE")
    assert PB.verify_journal(paper) is None
    t = paper.journal_md.read_text().replace('"entry_reason": "r"', '"entry_reason": "rewritten"')
    paper.journal_md.write_text(t)
    assert "changed" in PB.verify_journal(paper)
    notes = PB.update(paper, START)
    assert any("journal check FAILED" in n for n in notes)


def test_min_hold_counter():
    assert PB.trading_days_between(date(2026, 10, 26), date(2026, 11, 2)) == 5
    assert PB.trading_days_between(date(2026, 11, 25), date(2026, 11, 30)) == 2   # Thanksgiving 11-26 closed


# ---------------------------------------------------------------- late Sundays and MISSED weeks

def test_late_monday_before_open_fills_same_day(paper):
    J(paper, "2026-11-01", now=at("2026-11-02T08:15"), action="NO_TRADE")
    e = PB.read_entries(paper)[-1]
    assert e["decision_date"] == "2026-11-01" and e["late"] is True and e["fill_planned"] == "2026-11-02"


def test_late_monday_after_open_fills_next_day_never_earlier(paper):
    J(paper, "2026-11-01", now=at("2026-11-02T10:05"), action="BUY", instrument="GLD", size_pct=20,
      exit_rule={"stop_below": 1})
    e = PB.read_entries(paper)[-1]
    assert e["late"] is True and e["fill_planned"] == "2026-11-03"   # Monday's open had passed
    assert e["fill_planned"] > e["written_at_et"][:10] or e["written_at_et"][11:16] < "09:30"
    pend = [o for o in paper.load()["pending"] if o["book"] == "B"]
    assert pend[0]["fill_date"] == "2026-11-03"


def test_on_time_sunday_is_not_late(paper):
    J(paper, "2026-10-25", action="NO_TRADE")
    e = PB.read_entries(paper)[-1]
    assert e["late"] is False and e["fill_planned"] == "2026-10-26"


def test_window_closes_after_saturday_and_week_is_missed_once(paper):
    with pytest.raises(SystemExit, match="MISSED"):
        J(paper, "2026-10-25", now=at("2026-11-01T18:00"), action="NO_TRADE")
    PB.update(paper, date(2026, 11, 2))
    PB.update(paper, date(2026, 11, 3))                         # second run must not record it again
    missed = [e for e in PB.read_entries(paper) if e["action"] == "MISSED"]
    assert [m["decision_date"] for m in missed] == ["2026-10-25"]
    assert PB.verify_journal(paper) is None
    J(paper, "2026-11-01", now=at("2026-11-04T12:00"), action="NO_TRADE")   # late but inside its own week
    with pytest.raises(SystemExit, match="already exists"):
        J(paper, "2026-11-01", now=at("2026-11-05T12:00"), action="NO_TRADE")
    nums = [e["entry"] for e in PB.read_entries(paper)]
    assert nums == list(range(1, len(nums) + 1))                # numbering stays consecutive


def test_journal_command_records_missed_weeks_first(paper):
    J(paper, "2026-11-08", now=at("2026-11-08T18:00"), action="NO_TRADE")   # weeks of 10-25 and 11-01 were skipped
    ent = PB.read_entries(paper)
    assert [(e["decision_date"], e["action"]) for e in ent] == [("2026-10-25", "MISSED"), ("2026-11-01", "MISSED"),
                                                                 ("2026-11-08", "NO_TRADE")]
    assert PB.verify_journal(paper) is None


# ---------------------------------------------------------------- market-hours guard

def test_update_refused_during_market_hours_and_logged(paper, monkeypatch):
    before = paper.state_p.read_text()
    monkeypatch.setattr(PB, "now_et", lambda: datetime(2026, 10, 26, 11, 55, tzinfo=PB.ET))   # Monday, market open
    assert PB.update(paper, START) == []
    assert paper.state_p.read_text() == before                          # nothing changed
    assert not paper.values.exists()
    log = paper.read_csv(paper.dir / "update_refusals.csv")
    assert len(log) == 1 and "09:30-16:15" in log["reason"].iloc[0]


def test_market_hours_window_edges():
    at = lambda *a: datetime(*a, tzinfo=PB.ET)
    assert PB.market_hours_refusal(at(2026, 10, 26, 9, 29)) is None
    assert PB.market_hours_refusal(at(2026, 10, 26, 9, 30)) is not None
    assert PB.market_hours_refusal(at(2026, 10, 26, 16, 14)) is not None
    assert PB.market_hours_refusal(at(2026, 10, 26, 16, 15)) is None
    assert PB.market_hours_refusal(at(2026, 10, 31, 12, 0)) is None      # Saturday
    assert PB.market_hours_refusal(at(2026, 11, 26, 12, 0)) is None      # Thanksgiving: NYSE closed


def test_update_after_refusal_catches_up(paper, monkeypatch):
    J(paper, "2026-10-25", action="NO_TRADE")
    monkeypatch.setattr(PB, "now_et", lambda: datetime(2026, 10, 27, 10, 0, tzinfo=PB.ET))
    PB.update(paper, date(2026, 10, 27))
    monkeypatch.setattr(PB, "now_et", lambda: datetime(2026, 10, 27, 16, 45, tzinfo=PB.ET))
    PB.update(paper, date(2026, 10, 27))
    assert list(paper.read_csv(paper.values)["date"]) == ["2026-10-26", "2026-10-27"]


def test_no_bar_for_today_alerts_instead_of_silent_ok(paper, monkeypatch):
    """Fix P1: a trading day with no bar yet gives a notification (it used to do nothing and stay silent)."""
    monkeypatch.setattr(PB, "download", lambda t, s: fake(t, s).loc[:"2026-10-27"])
    notes = PB.update(paper, date(2026, 10, 28))
    assert any("no daily bar for 2026-10-28" in n for n in notes)
    assert paper.load()["last_update"] == "2026-10-27"


def test_missing_open_defers_order_and_missing_close_uses_last_close(paper, monkeypatch):
    """Fix P2: one missing price no longer fails the whole update."""
    def gappy(t, s):
        df = fake(t, s)
        df.loc[pd.Timestamp("2026-10-26"), ("Open", "GLD")] = np.nan        # no GLD open on the start day
        df.loc[pd.Timestamp("2026-10-28"), ("Close", "VTI")] = np.nan       # no VTI close (held by Book A) two days later
        return df
    monkeypatch.setattr(PB, "download", gappy)
    J(paper, "2026-10-25", action="BUY", instrument="GLD", size_pct=50, exit_rule={"exit_on_or_after": "2026-11-06"})
    notes = PB.update(paper, date(2026, 10, 26))
    assert any("deferred: no open price for GLD on 2026-10-26" in n for n in notes)
    s = paper.load()
    assert {o["book"] for o in s["pending"]} == {"MIX", "B"}             # GLD orders wait; SPY and Book A filled
    assert "SPY" in s["books"]["SPY"]["shares"]
    notes = PB.update(paper, date(2026, 10, 27))
    assert any("filled late on 2026-10-27" in n for n in notes) and not paper.load()["pending"]
    notes = PB.update(paper, date(2026, 10, 28))
    assert any("no close for VTI on 2026-10-28" in n for n in notes)
    v = paper.read_csv(paper.values)
    assert list(v["date"]) == ["2026-10-26", "2026-10-27", "2026-10-28"]
    px, a = fake(None, None)["Close"], paper.load()["books"]["A"]["V122"]
    assert abs(v["A_V122"].iloc[-1] - (a["cash"] + a["shares"]["VTI"] * px.loc["2026-10-27", "VTI"]
                                       + a["shares"]["DBC"] * px.loc["2026-10-28", "DBC"])) < 1e-4     # values.csv keeps 4 decimals


def _falling_gld(t, s):
    """GLD closes below the stop on day 2 (inside the 5-day minimum hold) and opens lower than the stop later."""
    df = fake(t, s)
    idx = df.index
    g = pd.Series(370.0, index=idx)
    g[idx >= pd.Timestamp("2026-10-28")] = 340.0                   # close below a 348 stop from Wed 10-28
    df[("Close", "GLD")] = g
    df[("Open", "GLD")] = g.shift(1).fillna(370.0) - 2.0            # each open gaps 2 below the prior close
    return df


def test_stop_is_checked_at_the_close_and_filled_at_the_next_open_not_the_stop(paper, monkeypatch):
    """Documents current behaviour (Phase H audit): a stop is evaluated once a day at the close, only after the 5-day
    minimum hold, and fills at the next open's price (gap risk), never at the stop price."""
    monkeypatch.setattr(PB, "download", _falling_gld)
    J(paper, "2026-10-25", action="BUY", instrument="GLD", size_pct=25, exit_rule={"stop_below": 348})
    PB.update(paper, date(2026, 11, 6))
    tr = paper.read_csv(paper.trades)
    sells = tr[(tr["book"] == "B") & (tr["side"] == "SELL")]
    assert list(sells["date"]) == ["2026-11-02"]                    # not 10-29: the stop waits for the minimum hold
    fill = float(sells["price_incl_costs"].iloc[0])
    assert fill < 348 and abs(fill - 338.0 * (1 - 0.0007)) < 1e-3     # next open (gapped) less costs, not 348


def test_economic_exposure_reported_in_summary(paper):
    """Reporting only (user 2026-10-28): leveraged ETFs count at their stated multiple; rules unchanged."""
    J(paper, "2026-10-25", action="BUY", instrument="TQQQ", size_pct=50, exit_rule={"exit_on_or_after": "2026-11-06"})
    PB.update(paper, START)
    ex = paper.load()["exposure"]
    assert ex["as_of"] == "2026-10-26"
    assert abs(ex["SPY"] - 1.0) < 1e-9 and abs(ex["MIX"] - 1.0) < 1e-9
    assert 1.40 < ex["B"] < 1.60                       # 50% in a 3x ETF (prices move between open and close)
    assert 0.90 < ex["A"] < 1.10                       # V122 0.5x of its sleeve, V074 1.5x of its sleeve
    t = PB.table(paper)
    assert "Economic exposure" in t and "~%.2fx" % ex["B"] in t and "applies to new FX research only" in t
