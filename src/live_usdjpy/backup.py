"""Forward-registry backup: consistent snapshots, integrity verification, restore test and backup-health alerts
(next phase, Phase B, 2026-10-30). Plain Python, standard library only.

Why: the live SQLite registry (WAL) is excluded from the private backup on purpose (copying a live WAL database is
unsafe), but until now no snapshot was ever taken, so the forward record existed only on this Mac.

What happens:
  snapshot      SQLite's online backup API (Connection.backup) writes a consistent copy while the registry is open,
                inside the runner's file lock (no concurrent writer). The copy is fsynced, then verified on a READ-ONLY
                connection: PRAGMA integrity_check = ok, the whole hash chain recomputes, and its record count and
                last hash equal the live registry's at snapshot time. A JSONL export (one canonical record per line)
                is written and its line count checked. Only a verified snapshot is published to
                live/usdjpy_backup/ (registry_snapshot.sqlite, registry_export.jsonl, manifest.json), which the
                existing private backup (tools/backup_private.py, allow-list paper/ live/ briefs/) picks up; no
                allow-list or exclude rule changes. Dated local copies go to live/usdjpy/local_snapshots/ (covered by
                the existing exclude rule, so they never enter the private repository) and the newest `keep_local`
                are kept.
  record        every attempt (ok or failed) is a `backup` record in the registry itself.
  health        HIGH alert (once per New York day per reason) when the last `fail_alert_after` attempts failed, when the
                newest verified snapshot is older than `max_age_hours`, or when the newest off-site copy (the private
                repository's origin/main, read from the local .backup.git without network access) is older than
                `offsite_max_age_days`.
  restore_test  restores a snapshot (the published file, or the copy committed in .backup.git) into a fresh folder
                under tmp/, verifies it as above, checks that every restored record equals the live registry's record
                with the same seq, then deletes the folder. Nothing in live/ is touched.

Recovery procedure: reports/forward_reliability_2026-10-30.md, section B.
"""
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import lifecycle as LC
from .registry import canonical, verify_chain

NY = ZoneInfo("America/New_York")
PUBLISHED = "registry_snapshot.sqlite"
EXPORT = "registry_export.jsonl"
MANIFEST = "manifest.json"


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fsync(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_copy(src, dest):
    tmp = dest.with_name("." + dest.name + ".tmp")
    shutil.copyfile(src, tmp)
    _fsync(tmp)
    tmp.replace(dest)
    _fsync(dest.parent)


def inspect(path):
    """Verify a snapshot file on a read-only connection. Returns a dict; 'ok' is True only if every check passes."""
    out = {"file": str(path), "ok": False}
    if not Path(path).exists():
        out["error"] = "file missing"
        return out
    con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    try:
        ic = con.execute("PRAGMA integrity_check").fetchone()[0]
        chain = verify_chain(con)
        n, last_seq = con.execute("SELECT COUNT(*), COALESCE(MAX(seq), 0) FROM records").fetchone()
        row = con.execute("SELECT hash FROM records ORDER BY seq DESC LIMIT 1").fetchone()
        out.update(integrity=ic, chain="intact" if chain is None else chain, records=n, last_seq=last_seq,
                   last_hash=row[0] if row else "", sha256=_sha(path), bytes=Path(path).stat().st_size)
        out["ok"] = ic == "ok" and chain is None
    except Exception as ex:
        out["error"] = "%s: %s" % (type(ex).__name__, str(ex)[:200])
    finally:
        con.close()
    return out


def snapshot(registry, now, cfg, root):
    """Take, verify and publish one snapshot. Returns the result dict (also on failure: ok False with the reason)."""
    root = Path(root)
    local, pub = root / cfg["local_dir"], root / cfg["publish_dir"]
    local.mkdir(parents=True, exist_ok=True)
    pub.mkdir(parents=True, exist_ok=True)
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    res = {"type": "snapshot", "at_utc": now.astimezone(timezone.utc).isoformat(), "ok": False}
    try:
        expect_n = registry.count()
        expect_hash = registry._last_hash()
        dest = local / ("registry-%s.sqlite" % stamp)
        registry.snapshot(dest)
        con = sqlite3.connect(dest)                  # self-contained single file: no WAL/SHM side files when read
        con.execute("PRAGMA journal_mode=DELETE")
        con.close()
        _fsync(dest)
        chk = inspect(dest)
        res.update(records=chk.get("records"), last_seq=chk.get("last_seq"), last_hash=chk.get("last_hash"),
                   sha256=chk.get("sha256"), bytes=chk.get("bytes"), integrity=chk.get("integrity"), chain=chk.get("chain"))
        problems = []
        if not chk["ok"]:
            problems.append("snapshot failed verification: %s" % (chk.get("error") or "integrity %s, chain %s" % (
                chk.get("integrity"), chk.get("chain"))))
        if chk.get("records") != expect_n or chk.get("last_hash") != expect_hash:
            problems.append("snapshot does not match the live registry (records %s vs %s)" % (chk.get("records"), expect_n))
        exp_tmp = local / (".export-%s.jsonl" % stamp)
        registry.export_jsonl(exp_tmp)
        lines = sum(1 for _ in open(exp_tmp))
        if lines != expect_n:
            problems.append("JSONL export has %d lines, expected %d" % (lines, expect_n))
        if problems:
            exp_tmp.unlink(missing_ok=True)
            res["error"] = "; ".join(problems)
            return res
        _atomic_copy(dest, pub / PUBLISHED)
        _atomic_copy(exp_tmp, pub / EXPORT)
        exp_tmp.unlink()
        res.update(ok=True, export_sha256=_sha(pub / EXPORT), local_copy=str(dest.relative_to(root)),
                   published=str((pub / PUBLISHED).relative_to(root)))
        man = dict(res, label="FORWARD REGISTRY SNAPSHOT (private; never published)")
        tmp = pub / ("." + MANIFEST + ".tmp")
        tmp.write_text(json.dumps(man, indent=1, sort_keys=True))
        _fsync(tmp)
        tmp.replace(pub / MANIFEST)
        copies = sorted(local.glob("registry-*.sqlite"))
        for old in copies[:-int(cfg["keep_local"])]:
            old.unlink()
        return res
    except Exception as ex:
        res["error"] = "%s: %s" % (type(ex).__name__, str(ex)[:200])
        return res


def record(registry, now, res):
    key = "backup:%s:%s" % (res.get("type"), now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S"))
    return registry.append("backup", res, idem_key=key, now=now)


def _attempts(registry, typ="snapshot"):
    return [r["payload"] for r in registry.records("backup") if r["payload"].get("type") == typ]


def due(registry, now, cfg):
    """A snapshot is due once per New York day after `daily_after_et`, or whenever the newest verified one is older
    than `max_age_hours`, or if none exists. A failed attempt is retried at the next run, at most hourly."""
    att = _attempts(registry)
    oks = [a for a in att if a.get("ok")]
    if att and not att[-1].get("ok"):
        if now - datetime.fromisoformat(att[-1]["at_utc"]) < timedelta(minutes=55):
            return False
    if not oks:
        return True
    last = datetime.fromisoformat(oks[-1]["at_utc"])
    if now - last > timedelta(hours=cfg["max_age_hours"]):
        return True
    ny = now.astimezone(NY)
    h, m = (int(x) for x in cfg["daily_after_et"].split(":"))
    return (ny.hour, ny.minute) >= (h, m) and last.astimezone(NY).date() < ny.date()


def offsite_status(root, cfg):
    """Newest copy of the published snapshot in the private repository as last pushed (local .backup.git refs; no
    network). Returns dict(state, committed_et, age_days)."""
    gd = Path(root) / ".backup.git"
    if not gd.exists():
        return {"state": "NOT CONFIGURED"}
    path = "%s/%s" % (cfg["publish_dir"], PUBLISHED)
    r = subprocess.run(["git", "--git-dir", str(gd), "log", "-1", "--format=%cI", "refs/remotes/origin/main", "--", path],
                       capture_output=True, text=True, timeout=30)
    t = r.stdout.strip()
    if r.returncode != 0:
        return {"state": "UNKNOWN", "error": (r.stderr or "").strip()[:150]}
    if not t:
        return {"state": "NONE YET"}
    when = datetime.fromisoformat(t)
    return {"state": "OK", "committed_et": LC.et(when), "age_days": round((datetime.now(timezone.utc) - when).total_seconds() / 86400, 2)}


def health(registry, now, cfg, root, offsite=None):
    """Problems as (reason_key, text). Also queues one HIGH RISK/SYSTEM alert per reason per New York day."""
    probs = []
    att = _attempts(registry)
    oks = [a for a in att if a.get("ok")]
    n = int(cfg["fail_alert_after"])
    if len(att) >= n and not any(a.get("ok") for a in att[-n:]):
        probs.append(("failing", "the last %d registry snapshot attempts failed (latest: %s)" % (n, att[-1].get("error", "?"))))
    if oks:
        age = (now - datetime.fromisoformat(oks[-1]["at_utc"])).total_seconds() / 3600
        if age > cfg["max_age_hours"]:
            probs.append(("stale", "newest verified registry snapshot is %.0f h old (limit %d h)" % (age, cfg["max_age_hours"])))
    elif att:
        probs.append(("none", "no verified registry snapshot exists"))
    off = offsite if offsite is not None else offsite_status(root, cfg)
    start = datetime.fromisoformat(cfg["offsite_required_from"]).replace(tzinfo=NY)
    grace_over = now.astimezone(NY) - start > timedelta(days=cfg["offsite_max_age_days"])
    if off.get("state") == "OK" and off.get("age_days", 0) > cfg["offsite_max_age_days"]:
        probs.append(("offsite", "off-site copy of the registry is %.1f days old (limit %d days)" % (
            off["age_days"], cfg["offsite_max_age_days"])))
    elif off.get("state") != "OK" and grace_over:           # missing copies are excused only during the start-up grace
        probs.append(("offsite", "off-site copy of the registry is %s (limit %d days)" % (
            off.get("state", "UNKNOWN").lower(), cfg["offsite_max_age_days"])))
    day = now.astimezone(NY).date().isoformat()
    for key, text in probs:
        registry.append("notification", LC.alert(
            "HIGH", "BACKUP PROBLEM: %s" % text.split(" (")[0],
            summary="SYSTEM | BACKUP PROBLEM | %s | action: check the registry backup" % key.upper(),
            **{"class": "RISK/SYSTEM ALERT", "event_time_et": LC.et(now), "why_sent": text}),
            idem_key="backup-alert:%s:%s" % (key, day), now=now)
    return probs


def restore_test(root, cfg, live_registry, source="published"):
    """Restore into a fresh tmp/ folder, verify, compare with the live registry, delete the folder."""
    root = Path(root)
    work = root / "tmp" / ("restore_test_%s" % datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    work.mkdir(parents=True)
    res = {"type": "restore_test", "source": source, "at_utc": datetime.now(timezone.utc).isoformat(), "ok": False}
    try:
        target = work / "restored.sqlite"
        if source == "published":
            shutil.copyfile(root / cfg["publish_dir"] / PUBLISHED, target)
            man = json.loads((root / cfg["publish_dir"] / MANIFEST).read_text())
        else:                                        # the copy committed in the private backup's local git database
            gd = root / ".backup.git"
            ref = "refs/remotes/origin/main" if source == "offsite" else "HEAD"
            for name, dest in ((PUBLISHED, target), (MANIFEST, work / MANIFEST)):
                blob = subprocess.run(["git", "--git-dir", str(gd), "show", "%s:%s/%s" % (ref, cfg["publish_dir"], name)],
                                      capture_output=True, timeout=60)
                if blob.returncode != 0:
                    raise RuntimeError("%s not in %s of the private backup" % (name, ref))
                dest.write_bytes(blob.stdout)
            man = json.loads((work / MANIFEST).read_text())
        chk = inspect(target)
        res.update(records=chk.get("records"), integrity=chk.get("integrity"), chain=chk.get("chain"),
                   sha256=chk.get("sha256"), snapshot_at_utc=man.get("at_utc"))
        problems = []
        if not chk["ok"]:
            problems.append("restored copy fails verification")
        if chk.get("sha256") != man.get("sha256") or chk.get("records") != man.get("records") or chk.get("last_hash") != man.get("last_hash"):
            problems.append("restored copy differs from its manifest")
        con = sqlite3.connect("file:%s?mode=ro" % target, uri=True)
        try:
            restored = con.execute("SELECT seq, hash FROM records ORDER BY seq").fetchall()
        finally:
            con.close()
        live = dict(live_registry.db.execute("SELECT seq, hash FROM records WHERE seq <= ?", (chk.get("last_seq") or 0,)).fetchall())
        mism = [s for s, h in restored if live.get(s) != h]
        if mism or len(live) != len(restored):
            problems.append("restored records differ from the live registry (first seq %s)" % (mism[:1] or "count"))
        res["matches_live_prefix"] = not mism and len(live) == len(restored)
        if problems:
            res["error"] = "; ".join(problems)
        else:
            res["ok"] = True
    except Exception as ex:
        res["error"] = "%s: %s" % (type(ex).__name__, str(ex)[:200])
    finally:
        shutil.rmtree(work, ignore_errors=True)
        res["temp_folder_removed"] = not work.exists()
    return res


def summary_line(registry, now, cfg, root, offsite=None):
    """One line for the digest and status page."""
    oks = [a for a in _attempts(registry) if a.get("ok")]
    off = offsite if offsite is not None else offsite_status(root, cfg)
    local = "last verified snapshot %s (%s records)" % (LC.et(oks[-1]["at_utc"]), oks[-1]["records"]) if oks else "no verified snapshot yet"
    o = {"OK": "off-site copy pushed %s" % off.get("committed_et"), "NONE YET": "no off-site copy yet (next Sunday backup)"}.get(
        off.get("state"), "off-site status %s" % off.get("state"))
    return "Backup: %s; %s." % (local, o)
