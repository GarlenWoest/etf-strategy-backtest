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
    monkeypatch.setattr(PB, "live_targets", lambda: ("2026-09-30", {"V122": {"VTI": 0.25, "DBC": 0.25},
                                                                    "V074": {"UPRO": 0.25, "TQQQ": 0.25}}))
    p = PB.Paper(DIR)
    PB.init(p, START)
    yield p
    shutil.rmtree(DIR, ignore_errors=True)


def J(p, d, **kw):
    e = {"decision_date": d, "entry_reason": "r", "wrong_if": "w", "planned_exit": "x", **kw}
    PB.journal(p, __import__("json").dumps(e), datetime(2026, 12, 31, 18, 0))


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
