"""Paper books crash safety (2026-10-29): golden equivalence with the pre-change code, interruption at every write,
restart, duplicate runs, tamper handling, atomic state writes. Synthetic data only (labelled tests, not results)."""
import hashlib
import importlib.util
import json
import os
import shutil
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import PROJECT_ROOT

spec = importlib.util.spec_from_file_location("pbc", PROJECT_ROOT / "tools" / "paper_books.py")
PB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PB)
DIR = PROJECT_ROOT / "tmp" / "test_paper_crash"
TICK = sorted(set(PB.A_INSTR) | set(PB.B_UNIVERSE) | {"^IRX"})
DAYS = [d.date() for d in pd.bdate_range("2026-10-26", "2026-11-13")]
# SHA-256 of values.csv and trades.csv produced by the PRE-CHANGE paper_books.py (commit 1bb96a6) on this exact
# synthetic scenario (tmp/replay/golden.py, 2026-10-29). The new code must reproduce them byte for byte.
GOLDEN = {"values.csv": "223632d1b96f3f34c1660aab8c0fc2099b9f9eca057809d0755c5381a350dc52",
          "trades.csv": "040b4fc9961e723132c4b7d1ce454ea327480fd7bd5754d088821f77b2e0cbc9"}


def fake(tickers, start):
    idx = pd.bdate_range("2026-10-12", "2026-12-31")
    rng = np.random.default_rng(7)
    c = pd.DataFrame({t: 100 * np.exp(np.cumsum(rng.normal(0, 0.012, len(idx)))) for t in TICK}, index=idx)
    c["^IRX"] = 5.04
    o = c * 0.995
    dv = pd.DataFrame(0.0, index=idx, columns=TICK)
    dv.loc[pd.Timestamp("2026-11-02"), "SPY"] = 1.0
    return pd.concat({"Open": o, "Close": c, "Dividends": dv}, axis=1)


def evening(d):
    return lambda: datetime(d.year, d.month, d.day, 18, 0, tzinfo=PB.ET)


def setup_books(path, monkeypatch):
    shutil.rmtree(path, ignore_errors=True)
    monkeypatch.setattr(PB, "download", fake)
    monkeypatch.setattr(PB, "live_targets", lambda: ("2026-09-30", {"V122": {"VTI": 0.25, "DBC": 0.25},
                                                                    "V074": {"UPRO": 0.25, "TQQQ": 0.25}}))
    monkeypatch.setattr(PB, "now_et", evening(date(2026, 10, 25)))
    p = PB.Paper(path)
    PB.init(p, date(2026, 10, 26))
    PB.journal(p, json.dumps({"decision_date": "2026-10-25", "action": "BUY", "instrument": "GLD", "size_pct": 50,
                              "exit_rule": {"exit_on_or_after": "2026-11-04"}, "entry_reason": "r", "wrong_if": "w",
                              "planned_exit": "x"}), datetime(2026, 10, 25, 18, 0, tzinfo=PB.ET))
    return p


def run_days(p, monkeypatch, days=DAYS):
    for d in days:
        monkeypatch.setattr(PB, "now_et", evening(d))
        PB.update(PB.Paper(p.dir), d)                     # a fresh Paper object each day, as a new process would


def files(p):
    return {n: (p.dir / n).read_bytes() if (p.dir / n).exists() else b"" for n in PB.APPEND_FILES}   # files created on demand


def books(p):
    s = json.loads(p.state_p.read_text())
    return {k: s[k] for k in ("books", "pending", "last_update", "journal_entries", "a_applied_month_end", "exposure")}


@pytest.fixture
def reference(monkeypatch):
    p = setup_books(DIR / "ref", monkeypatch)
    run_days(p, monkeypatch)
    yield p
    shutil.rmtree(DIR, ignore_errors=True)


def test_new_code_reproduces_pre_change_outputs_exactly(reference):
    for f, h in GOLDEN.items():
        assert hashlib.sha256((reference.dir / f).read_bytes()).hexdigest() == h, f
    assert not (reference.dir / "recovery_log.csv").exists()          # a clean run never "recovers" anything


def test_interruption_at_every_append_then_restart_gives_identical_books(reference, monkeypatch):
    """Crash at the k-th append (before it is written, or after the bytes but before the commit); a restart must
    produce books identical to the uninterrupted run: no lost day, no duplicate row or fill."""
    want_files, want_books = files(reference), books(reference)
    real_append = PB.append_text
    n_appends = len(want_files["values.csv"].splitlines()) + len(want_files["trades.csv"].splitlines())
    for k in range(1, n_appends + 1):
        for after in (False, True):
            p = setup_books(DIR / "crash", monkeypatch)
            calls = {"n": 0}

            def boom(path, text, **kw):
                calls["n"] += 1
                if calls["n"] == k:
                    if after:
                        real_append(path, text[: max(1, len(text) // 2)])     # a torn, half-written line
                    raise OSError("simulated crash")
                return real_append(path, text, **kw)
            monkeypatch.setattr(PB, "append_text", boom)
            try:
                run_days(p, monkeypatch)
            except OSError:
                pass
            monkeypatch.setattr(PB, "append_text", real_append)
            run_days(p, monkeypatch)                                       # restart: catches up
            assert files(p) == want_files, (k, after)
            assert books(p) == want_books, (k, after)
            if calls["n"] >= k:
                assert after is False or (p.dir / "recovery_log.csv").exists()


def test_crash_after_rows_before_state_commit_is_recovered(reference, monkeypatch):
    want = files(reference)
    p = setup_books(DIR / "crash2", monkeypatch)
    run_days(p, monkeypatch, DAYS[:3])
    real_save = PB.Paper.save

    def crash_save(self, s):
        if s.get("last_update") == DAYS[3].isoformat():
            raise OSError("simulated crash before commit")
        return real_save(self, s)
    monkeypatch.setattr(PB.Paper, "save", crash_save)
    with pytest.raises(OSError):
        run_days(p, monkeypatch, [DAYS[3]])
    assert (p.dir / "values.csv").stat().st_size > json.loads(p.state_p.read_text())["committed_bytes"]["values.csv"]
    monkeypatch.setattr(PB.Paper, "save", real_save)
    run_days(p, monkeypatch, DAYS[3:])
    assert files(p) == want
    log = pd.read_csv(p.dir / "recovery_log.csv", comment="#")
    assert set(log["file"]) <= {"values.csv", "trades.csv"} and len(log) >= 1
    assert all((p.dir / k).exists() for k in log["kept_as"])          # removed bytes are kept, not destroyed


def test_duplicate_run_same_day_changes_nothing(reference, monkeypatch):
    before = files(reference), books(reference)
    p = PB.Paper(reference.dir)
    monkeypatch.setattr(PB, "now_et", evening(DAYS[-1]))
    PB.update(p, DAYS[-1])
    assert (files(reference), books(reference)) == before
    assert p.last_summary.startswith("PAPER UPDATE OK: no new trading day to process")


def test_success_always_prints_a_status_line(monkeypatch):
    p = setup_books(DIR / "status", monkeypatch)
    monkeypatch.setattr(PB, "now_et", evening(DAYS[0]))
    PB.update(p, DAYS[0])
    assert p.last_summary.startswith("PAPER UPDATE OK: processed 1 new trading day(s) 2026-10-26")
    shutil.rmtree(DIR, ignore_errors=True)


def test_edited_committed_ledger_stops_the_update_and_touches_nothing(reference, monkeypatch):
    f = reference.dir / "values.csv"
    f.write_bytes(f.read_bytes().replace(b",100.", b",101.", 1))     # same length: an edit, not an append
    before = f.read_bytes()
    monkeypatch.setattr(PB, "now_et", evening(DAYS[-1]))
    with pytest.raises(RuntimeError, match="changed after it was written"):
        PB.update(PB.Paper(reference.dir), DAYS[-1])
    assert f.read_bytes() == before                                     # never "repaired" by truncation


def test_shorter_than_committed_file_is_an_error(reference, monkeypatch):
    f = reference.dir / "trades.csv"
    os.truncate(f, f.stat().st_size - 10)
    monkeypatch.setattr(PB, "now_et", evening(DAYS[-1]))
    with pytest.raises(RuntimeError, match="committed data is missing"):
        PB.update(PB.Paper(reference.dir), DAYS[-1])


def test_journal_edit_still_raises_the_tamper_alert_and_is_not_truncated(reference, monkeypatch):
    j = reference.dir / "book_b_journal.md"
    j.write_text(j.read_text().replace('"entry_reason": "r"', '"entry_reason": "rewritten"'))
    before = j.read_bytes()
    monkeypatch.setattr(PB, "now_et", evening(DAYS[-1]))
    notes = PB.update(PB.Paper(reference.dir), DAYS[-1])
    assert any("journal check FAILED" in n for n in notes)
    assert j.read_bytes() == before


def test_state_write_is_atomic(reference, monkeypatch):
    before = reference.state_p.read_bytes()

    def fail(*a, **k):
        raise OSError("simulated crash during rename")
    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        PB.Paper(reference.dir).save(json.loads(before))
    monkeypatch.undo()
    assert reference.state_p.read_bytes() == before
    assert not [x for x in os.listdir(reference.dir) if x.endswith(".tmp")]   # no temp files left behind


def test_legacy_state_without_commit_fields_loads_and_runs(reference, monkeypatch):
    s = json.loads(reference.state_p.read_text())
    s.pop("committed_bytes"), s.pop("committed_sha256")
    reference.state_p.write_text(json.dumps(s, indent=2))
    monkeypatch.setattr(PB, "now_et", evening(DAYS[-1]))
    p = PB.Paper(reference.dir)
    PB.update(p, DAYS[-1])
    assert not (reference.dir / "recovery_log.csv").exists()
    assert "committed_sha256" in json.loads(reference.state_p.read_text())


def test_inputs_are_kept_for_every_processed_day(reference):
    got = sorted(x.stem for x in (reference.dir / "inputs").glob("*.json"))
    assert got == [d.isoformat() for d in DAYS]
    rec = json.loads((reference.dir / "inputs" / "2026-10-26.json").read_text())
    px = fake(None, None)
    assert rec["open"]["GLD"] == pytest.approx(float(px["Open"].loc["2026-10-26", "GLD"]))
