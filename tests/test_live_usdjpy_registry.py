"""Registry for the USD/JPY forward system: append-only, hash-chained, idempotent, atomic, restart-safe; and isolation
from research code. Synthetic payloads only (tests, not results)."""
import re
import sqlite3
import subprocess
import sys
import textwrap
from datetime import datetime, timezone

import pytest

from src import PROJECT_ROOT
from src.live_usdjpy.registry import Registry, RegistryError


@pytest.fixture
def reg(tmp_path):
    r = Registry(tmp_path / "registry.sqlite")
    yield r
    r.close()


def test_append_chain_and_verify(reg):
    a = reg.append("scan_run", {"n": 1})
    b = reg.append("evaluation", {"rule": "TEST", "result": "NO_TRADE"})
    assert b["prev_hash"] == a["hash"] and reg.verify() is None and reg.count() == 2
    with pytest.raises(RegistryError):
        reg.append("not_a_kind", {})


def test_update_and_delete_are_blocked(reg):
    reg.append("note", {"x": 1})
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        reg.db.execute("UPDATE records SET payload='{}'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        reg.db.execute("DELETE FROM records")


def test_edit_after_dropping_triggers_is_detected(reg):
    reg.append("note", {"x": 1})
    reg.append("note", {"x": 2})
    reg.db.execute("DROP TRIGGER records_no_update")
    reg.db.execute("""UPDATE records SET payload='{"x":3}' WHERE seq=1""")
    assert "content does not match its hash" in reg.verify()


def test_idempotency_key_prevents_duplicates(reg):
    first = reg.append("notification", {"setup": "S1", "state": "triggered"}, idem_key="notif:S1:triggered")
    again = reg.append("notification", {"setup": "S1", "state": "triggered"}, idem_key="notif:S1:triggered")
    assert again["duplicate"] is True and again["record_id"] == first["record_id"] and reg.count() == 1


def test_transaction_is_all_or_nothing(reg):
    reg.append("note", {"before": True})
    with pytest.raises(ValueError):
        with reg.transaction():
            reg.append("order_event", {"id": "O1", "state": "CREATED"})
            reg.append("fill", {"order": "O1"})
            raise ValueError("crash before commit")
    assert reg.count() == 1 and reg.verify() is None
    with reg.transaction():
        reg.append("order_event", {"id": "O2", "state": "CREATED"})
        reg.append("fill", {"order": "O2"})
    assert reg.count() == 3 and reg.verify() is None


def test_killed_process_mid_transaction_leaves_no_partial_records(tmp_path):
    db = tmp_path / "registry.sqlite"
    r = Registry(db)
    r.append("note", {"committed": True})
    r.close()
    code = textwrap.dedent("""
        import os, sys
        sys.path.insert(0, %r)
        from src.live_usdjpy.registry import Registry
        r = Registry(%r)
        with r.transaction():
            r.append("order_event", {"id": "O9", "state": "CREATED"})
            r.append("fill", {"order": "O9"})
            os._exit(9)                      # killed before COMMIT
        """ % (str(PROJECT_ROOT), str(db)))
    assert subprocess.run([sys.executable, "-c", code]).returncode == 9
    r = Registry(db)                         # restart
    assert r.count() == 1 and r.verify() is None
    assert [x["kind"] for x in r.records()] == ["note"]
    r.append("note", {"after_restart": True})
    assert r.verify() is None
    r.close()


def test_restart_keeps_chain_and_keys(tmp_path):
    db = tmp_path / "registry.sqlite"
    r = Registry(db)
    r.append("scan_run", {"n": 1}, idem_key="scan:2026-11-02T16:45")
    r.close()
    r = Registry(db)
    assert r.append("scan_run", {"n": 1}, idem_key="scan:2026-11-02T16:45")["duplicate"] is True
    assert r.verify() is None
    r.close()


def test_snapshot_and_export(reg, tmp_path):
    for i in range(5):
        reg.append("note", {"i": i}, now=datetime(2026, 11, 2, 16, 45, i, tzinfo=timezone.utc))
    snap = Registry(reg.snapshot(tmp_path / "snap" / "registry_snapshot.sqlite"))
    assert snap.count() == 5 and snap.verify() is None
    assert [x["hash"] for x in snap.records()] == [x["hash"] for x in reg.records()]
    snap.close()
    lines = (reg.export_jsonl(tmp_path / "export.jsonl")).read_text().splitlines()
    assert len(lines) == 5


def test_research_code_never_imports_the_forward_system():
    """Monitoring/forward code may use research utilities; research code must never import it."""
    allowed = ("src/live_usdjpy/", "tests/", "tools/usdjpy_")
    bad = []
    for f in list((PROJECT_ROOT / "src").rglob("*.py")) + list((PROJECT_ROOT / "tools").glob("*.py")):
        rel = str(f.relative_to(PROJECT_ROOT))
        if rel.startswith(allowed):
            continue
        if re.search(r"live_usdjpy", f.read_text()):
            bad.append(rel)
    assert bad == []
