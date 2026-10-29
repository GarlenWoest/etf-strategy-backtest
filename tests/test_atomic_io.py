"""Crash-safe writes for the monitoring scripts (2026-10-29): atomic replace, torn-append repair, tolerant JSONL reads,
and a guard that no monitoring script goes back to plain in-place writes."""
import importlib.util
import json
import os
import re

import pytest

from src import PROJECT_ROOT

spec = importlib.util.spec_from_file_location("aio", PROJECT_ROOT / "tools" / "atomic_io.py")
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)


def test_write_text_replaces_atomically_and_leaves_no_temp_files(tmp_path):
    f = tmp_path / "state.json"
    A.write_text(f, "old")
    A.write_text(f, "new")
    assert f.read_text() == "new"
    assert os.listdir(tmp_path) == ["state.json"]


def test_interrupted_write_keeps_the_old_file(tmp_path, monkeypatch):
    f = tmp_path / "state.json"
    A.write_text(f, '{"v": 1}')

    def crash(*a, **k):
        raise OSError("simulated crash during rename")
    monkeypatch.setattr(A.os, "replace", crash)
    with pytest.raises(OSError):
        A.write_text(f, '{"v": 2}')
    monkeypatch.undo()
    assert json.loads(f.read_text()) == {"v": 1}
    assert os.listdir(tmp_path) == ["state.json"]


def test_torn_append_is_repaired_before_the_next_append(tmp_path):
    f = tmp_path / "log.jsonl"
    A.append_text(f, '{"a": 1}\n')
    A.append_text(f, '{"b": 2')                       # crash mid-line
    assert [r for r in A.read_jsonl(f)] == [{"a": 1}]  # reader skips the torn last line
    assert A.repair_tail(f) == len('{"b": 2')
    A.append_text(f, '{"c": 3}\n')
    assert A.read_jsonl(f) == [{"a": 1}, {"c": 3}]
    assert A.repair_tail(f) == 0


def test_corruption_in_the_middle_is_an_error(tmp_path):
    f = tmp_path / "log.jsonl"
    f.write_text('{"a": 1}\nnot json\n{"c": 3}\n')
    with pytest.raises(ValueError):
        A.read_jsonl(f)


def test_monitoring_scripts_use_atomic_writes_only():
    """State and report files in live/ and paper/ must be written through atomic_io, never with an in-place
    write_text() or open(..., "w"/"a")."""
    for name in ("paper_books.py", "heartbeat.py", "watchlist_signals.py", "events.py", "market_intel.py"):
        src = (PROJECT_ROOT / "tools" / name).read_text()
        code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
        assert not re.search(r"\.write_text\(", code), name
        assert not re.search(r"open\([^)]*['\"][wa]['\"]", code), name


def test_backup_excludes_temp_files():
    src = (PROJECT_ROOT / "tools" / "backup_private.py").read_text()
    assert ":(exclude)**/.*.tmp" in src
