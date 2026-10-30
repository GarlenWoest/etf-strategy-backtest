"""Forward-registry backup (next phase, Phase B, 2026-10-30): consistent snapshot, verification, restore test,
health alerts and the private-backup path rules. Synthetic registries in tmp folders; nothing live is touched."""
import json
import shutil
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from src import PROJECT_ROOT
from src.live_usdjpy import backup as BK
from src.live_usdjpy.registry import Registry

CFG = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text())["live_usdjpy"]["backup"]
T0 = datetime(2026, 11, 2, 22, 40, tzinfo=timezone.utc)          # Mon 17:40 ET, after daily_after_et


@pytest.fixture
def env(tmp_path):
    reg = Registry(tmp_path / "live" / "usdjpy" / "registry.sqlite")
    for i in range(25):
        reg.append("note", {"i": i}, idem_key="n%d" % i, now=T0 - timedelta(minutes=30 - i))
    yield tmp_path, reg
    reg.close()


def test_snapshot_is_verified_published_and_matches_the_live_registry(env):
    root, reg = env
    res = BK.snapshot(reg, T0, CFG, root)
    assert res["ok"] and res["records"] == 25 and res["integrity"] == "ok" and res["chain"] == "intact"
    pub = root / CFG["publish_dir"]
    man = json.loads((pub / BK.MANIFEST).read_text())
    assert man["sha256"] == BK._sha(pub / BK.PUBLISHED) and man["last_hash"] == reg._last_hash()
    assert len((pub / BK.EXPORT).read_text().splitlines()) == 25
    assert len(list((root / CFG["local_dir"]).glob("registry-*.sqlite"))) == 1
    assert not list(pub.glob(".*.tmp")) and not list((root / CFG["local_dir"]).glob(".*"))
    side = [f.name for d in (pub, root / CFG["local_dir"]) for f in d.iterdir() if f.name.endswith(("-wal", "-shm"))]
    assert side == []                                               # single-file copies (journal_mode DELETE)


def test_snapshot_taken_while_wal_has_uncheckpointed_writes_contains_them(env):
    root, reg = env
    reg.append("note", {"late": True}, now=T0)                     # sits in the WAL, not yet checkpointed
    res = BK.snapshot(reg, T0, CFG, root)
    assert res["ok"] and res["records"] == 26


def test_inspect_detects_a_tampered_snapshot(env):
    root, reg = env
    BK.snapshot(reg, T0, CFG, root)
    bad = root / "bad.sqlite"
    shutil.copyfile(root / CFG["publish_dir"] / BK.PUBLISHED, bad)
    con = sqlite3.connect(bad)
    con.execute("DROP TRIGGER records_no_update")
    con.execute("UPDATE records SET payload='{\"i\":99}' WHERE seq=5")
    con.commit()
    con.close()
    chk = BK.inspect(bad)
    assert not chk["ok"] and "record 5" in chk["chain"]


def test_restore_test_passes_and_cleans_up(env):
    root, reg = env
    BK.snapshot(reg, T0, CFG, root)
    reg.append("note", {"after": 1}, now=T0 + timedelta(minutes=1))   # live registry moved on: prefix must still match
    res = BK.restore_test(root, CFG, reg)
    assert res["ok"] and res["matches_live_prefix"] and res["temp_folder_removed"]
    assert not list((root / "tmp").glob("restore_test_*"))


def test_restore_test_fails_when_the_published_copy_differs_from_its_manifest(env):
    root, reg = env
    BK.snapshot(reg, T0, CFG, root)
    man_p = root / CFG["publish_dir"] / BK.MANIFEST
    man = json.loads(man_p.read_text())
    man["sha256"] = "0" * 64
    man_p.write_text(json.dumps(man))
    res = BK.restore_test(root, CFG, reg)
    assert not res["ok"] and "manifest" in res["error"]


def test_due_once_a_day_after_the_bar_and_retry_after_failure(env):
    root, reg = env
    assert BK.due(reg, T0, CFG)                                     # nothing yet
    BK.record(reg, T0, BK.snapshot(reg, T0, CFG, root))
    assert not BK.due(reg, T0 + timedelta(hours=2), CFG)            # same New York day
    assert not BK.due(reg, T0 + timedelta(hours=14), CFG)           # next day 07:40 ET: before 17:30
    assert BK.due(reg, T0 + timedelta(hours=24), CFG)               # next day 17:40 ET
    BK.record(reg, T0 + timedelta(hours=24), {"type": "snapshot", "ok": False, "error": "x",
                                             "at_utc": (T0 + timedelta(hours=24)).isoformat()})
    assert not BK.due(reg, T0 + timedelta(hours=24, minutes=15), CFG)   # failed: retry at most hourly
    assert BK.due(reg, T0 + timedelta(hours=25), CFG)


def _high(reg):
    return [r for r in reg.records("notification") if r["payload"]["priority"] == "HIGH"]


def test_health_alerts_repeated_failures_once_per_day(env):
    root, reg = env
    for k in range(2):
        t = T0 + timedelta(hours=k)
        BK.record(reg, t, {"type": "snapshot", "ok": False, "error": "disk full", "at_utc": t.isoformat()})
    probs = BK.health(reg, T0 + timedelta(hours=2), CFG, root, offsite={"state": "OK", "age_days": 1})
    assert [p[0] for p in probs] == ["failing", "none"]
    BK.health(reg, T0 + timedelta(hours=3), CFG, root, offsite={"state": "OK", "age_days": 1})
    assert len(_high(reg)) == 2                                     # deduplicated within the New York day


def test_health_alerts_a_stale_snapshot_and_a_stale_offsite_copy(env):
    root, reg = env
    BK.record(reg, T0, BK.snapshot(reg, T0, CFG, root))
    later = T0 + timedelta(hours=CFG["max_age_hours"] + 1)
    probs = dict(BK.health(reg, later, CFG, root, offsite={"state": "OK", "age_days": CFG["offsite_max_age_days"] + 1}))
    assert set(probs) == {"stale", "offsite"}
    assert all(r["payload"]["fields"]["class"] == "RISK/SYSTEM ALERT" for r in _high(reg))


def test_no_offsite_alert_inside_the_grace_period(env):
    root, reg = env
    BK.record(reg, T0, BK.snapshot(reg, T0, CFG, root))
    assert BK.health(reg, T0, CFG, root, offsite={"state": "NONE YET"}) == []   # 2026-11-02: within 9 days of the start


def test_private_backup_rules_include_the_published_snapshot_and_exclude_live_databases(tmp_path):
    """The existing tools/backup_private.py pathspecs, unchanged: only live/usdjpy_backup/ reaches the private repo."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("bp", PROJECT_ROOT / "tools" / "backup_private.py")
    bp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bp)
    for f in ("live/usdjpy/registry.sqlite", "live/usdjpy/registry.sqlite-wal", "live/usdjpy/demo_registry.sqlite",
              "live/usdjpy/local_snapshots/registry-20261102T224000Z.sqlite",
              "live/usdjpy_backup/registry_snapshot.sqlite", "live/usdjpy_backup/registry_export.jsonl",
              "live/usdjpy_backup/manifest.json", "live/usdjpy_backup/.manifest.json.tmp", "src/x.py"):
        p = tmp_path / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    out = subprocess.run(["git", "-C", str(tmp_path), "add", "-n", "-A", "-f", "--", "live", *bp.EXCLUDE],
                         capture_output=True, text=True, check=True).stdout
    added = sorted(l.split("'")[1] for l in out.splitlines())
    assert added == ["live/usdjpy_backup/manifest.json", "live/usdjpy_backup/registry_export.jsonl",
                     "live/usdjpy_backup/registry_snapshot.sqlite"]


def test_offsite_push_failures_alert_and_the_push_records_only_the_tool_result(env, monkeypatch):
    root, reg = env
    BK.record(reg, T0, BK.snapshot(reg, T0, CFG, root))
    calls = []

    class R:
        returncode, stdout = 1, "BACKUP FAILED: git push: remote rejected\n"
    monkeypatch.setattr(BK.subprocess, "run", lambda *a, **k: calls.append(k["env"]) or R())
    for k in range(2):
        t = T0 + timedelta(hours=k)
        res = BK.offsite_push(root, t)
        assert res == {"type": "offsite_push", "at_utc": t.isoformat(), "ok": False,
                       "result": "BACKUP FAILED: git push: remote rejected"}
        BK.record(reg, t, res)
    assert set(calls[0]) == {"PATH", "HOME"}                       # no other environment (no secrets) passed on
    probs = dict(BK.health(reg, T0 + timedelta(hours=2), CFG, root, offsite={"state": "OK", "age_days": 0.5}))
    assert "push" in probs and len(_high(reg)) == 1


def test_a_snapshot_earlier_the_same_day_does_not_cancel_the_evening_snapshot(env):
    """Regression 2026-10-30: a manual 09:47 ET snapshot made the 17:32 ET run skip the evening snapshot and push."""
    root, reg = env
    morning = datetime(2026, 11, 2, 14, 47, tzinfo=timezone.utc)      # Mon 09:47 ET
    BK.record(reg, morning, BK.snapshot(reg, morning, CFG, root))
    assert not BK.due(reg, datetime(2026, 11, 2, 22, 17, tzinfo=timezone.utc), CFG)    # 17:17 ET: before the cutoff
    assert BK.due(reg, datetime(2026, 11, 2, 22, 32, tzinfo=timezone.utc), CFG)        # 17:32 ET: evening snapshot due
