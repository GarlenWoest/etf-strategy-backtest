"""Replay proof for the REAL paper books (PAPER, FICTIONAL MONEY), using private local files only.

Skipped wherever paper/ is absent (the public repository has no paper data). The price frame
paper/replay/prices_as_used_2026-10-29.pkl is a Yahoo download from 2026-10-29 whose 10-26 opens were set back to the
opens recorded in paper/trades.csv, because Yahoo revised them after the fills. The current paper_books.py, replayed
from the start with Book B journal entry #1 as written, must reproduce the stored books through 2026-10-29:
values.csv byte for byte; trades.csv exactly, apart from fill prices that can differ in the 4th decimal (the 10-26
VTI open was stored with 4 decimals, so its exact value is unrecoverable).
"""
import importlib.util
import json
import shutil
from datetime import date, datetime

import pandas as pd
import pytest

from src import PROJECT_ROOT

REAL = PROJECT_ROOT / "paper"
FRAME = REAL / "replay" / "prices_as_used_2026-10-29.pkl"
OUT = PROJECT_ROOT / "tmp" / "test_paper_replay"
DAYS = [date(2026, 10, 26), date(2026, 10, 27), date(2026, 10, 28), date(2026, 10, 29)]
# Book A's targets as in force for these days (September month-end), from live/state.json in the private backup
# (commit 8d11673, 2026-10-28). Regression 2026-10-30: the test read the LIVE file, which the scheduled run updates at
# each month-end (10-30: October targets), so the replay silently used later targets.
TARGETS_USED = ("2026-09-30", {"V122": {"VTI": 0.25, "IEF": 0.0, "DBC": 0.25, "GLD": 0.0},
                               "V074": {"UGL": 0.0, "UPRO": 0.25, "TQQQ": 0.25, "TMF": 0.0}})
pytestmark = pytest.mark.skipif(not FRAME.exists(), reason="private paper data not present")


def test_current_code_reproduces_the_stored_books():
    spec = importlib.util.spec_from_file_location("pbr", PROJECT_ROOT / "tools" / "paper_books.py")
    PB = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(PB)
    PB.live_targets = lambda: TARGETS_USED                         # never the mutable live file
    frame = pd.read_pickle(FRAME)
    shutil.rmtree(OUT, ignore_errors=True)
    p = PB.Paper(OUT)
    PB.init(p, DAYS[0])
    shutil.copy(REAL / "book_b_journal.md", p.journal_md)
    shutil.copy(REAL / "journal_hashes.csv", p.hashes)
    e = PB.read_entries(p)[0]
    s = json.loads(p.state_p.read_text())
    s["journal_entries"] = 1
    s["pending"].append({"book": "B", "kind": "b_buy", "instrument": e["instrument"], "size_pct": float(e["size_pct"]),
                         "exit_rule": e["exit_rule"], "fill_date": e["fill_planned"], "entry": e["entry"]})
    p.save(s)
    for d in DAYS:
        PB.download = lambda tickers, start, d=d: frame[frame.index <= pd.Timestamp(d)]
        PB.now_et = lambda d=d: datetime(d.year, d.month, d.day, 18, 0, tzinfo=PB.ET)
        PB.update(PB.Paper(OUT), d)
    stored_v = pd.read_csv(REAL / "values.csv", comment="#")
    stored_v = stored_v[stored_v["date"] <= DAYS[-1].isoformat()]
    got_v = pd.read_csv(OUT / "values.csv", comment="#")
    pd.testing.assert_frame_equal(got_v, stored_v.reset_index(drop=True))
    st, gt = pd.read_csv(REAL / "trades.csv", comment="#"), pd.read_csv(OUT / "trades.csv", comment="#")
    st = st[st["date"] <= DAYS[-1].isoformat()].reset_index(drop=True)
    assert len(gt) == len(st)
    exact = ["date", "book", "side", "instrument", "shares", "open", "cost_rate"]
    pd.testing.assert_frame_equal(gt[exact], st[exact])
    assert (gt["price_incl_costs"] - st["price_incl_costs"]).abs().max() <= 0.0001 + 1e-9
    shutil.rmtree(OUT, ignore_errors=True)
