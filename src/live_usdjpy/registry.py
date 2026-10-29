"""Immutable registry for the USD/JPY forward system (master prompt step 3, 2026-10-29).

One SQLite database (standard-library sqlite3; WAL journal; synchronous=FULL). Every record is appended to `records`:
  seq          insertion order
  record_id    "<KIND>-<UTC timestamp>-<8 hex>" (unique)
  kind         one of KINDS
  created_utc  ISO timestamp (UTC)
  idem_key     optional idempotency key, UNIQUE: re-running the same scan, setup transition, order or notification
               returns the existing record instead of writing a second one
  payload      canonical JSON (sorted keys)
  prev_hash    hash of the previous record ("" for the first)
  hash         SHA-256 of record_id|kind|created_utc|idem_key|payload|prev_hash

Append-only is enforced twice: SQL triggers abort any UPDATE or DELETE, and verify() recomputes the whole chain
(detecting edits made by anyone who drops the triggers). Several appends can be committed atomically with
`with reg.transaction(): ...`; an exception or a killed process leaves none of them. snapshot() uses SQLite's backup
API (never copy a live WAL database); export_jsonl() writes a plain-text copy for audit.
"""
import hashlib
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

KINDS = ("scan_run", "market_state", "evaluation", "setup_transition", "risk_state", "order_event", "fill",
         "position_snapshot", "reconciliation", "outcome", "notification", "kill_switch", "preregistration", "note",
         "market_watch", "delivery")

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  record_id TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL,
  created_utc TEXT NOT NULL,
  idem_key TEXT UNIQUE,
  payload TEXT NOT NULL,
  prev_hash TEXT NOT NULL,
  hash TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS records_kind ON records(kind);
CREATE TRIGGER IF NOT EXISTS records_no_update BEFORE UPDATE ON records
  BEGIN SELECT RAISE(ABORT, 'registry is append-only'); END;
CREATE TRIGGER IF NOT EXISTS records_no_delete BEFORE DELETE ON records
  BEGIN SELECT RAISE(ABORT, 'registry is append-only'); END;
"""


class RegistryError(RuntimeError):
    pass


def canonical(payload):
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def record_hash(record_id, kind, created_utc, idem_key, payload_json, prev_hash):
    s = "|".join([record_id, kind, created_utc, idem_key or "", payload_json, prev_hash])
    return hashlib.sha256(s.encode()).hexdigest()


class Registry:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, isolation_level=None, timeout=30)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(SCHEMA)
        self._depth = 0

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        """All appends inside commit together or not at all (nested use joins the outer transaction)."""
        if self._depth == 0:
            self.db.execute("BEGIN IMMEDIATE")
        self._depth += 1
        try:
            yield self
        except BaseException:
            self._depth -= 1
            if self._depth == 0:
                self.db.execute("ROLLBACK")
            raise
        self._depth -= 1
        if self._depth == 0:
            self.db.execute("COMMIT")

    def _last_hash(self):
        row = self.db.execute("SELECT hash FROM records ORDER BY seq DESC LIMIT 1").fetchone()
        return row[0] if row else ""

    def append(self, kind, payload, idem_key=None, now=None):
        """Append one record and return it as a dict with `duplicate` False; if `idem_key` already exists, write
        nothing and return the existing record with `duplicate` True."""
        if kind not in KINDS:
            raise RegistryError("unknown kind %r" % kind)
        with self.transaction():
            if idem_key is not None:
                ex = self.get_by_key(idem_key)
                if ex:
                    return {**ex, "duplicate": True}
            now = now or datetime.now(timezone.utc)
            created = now.astimezone(timezone.utc).isoformat(timespec="microseconds")
            rid = "%s-%s-%s" % (kind.upper(), now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%f"),
                                secrets.token_hex(4))
            pj = canonical(payload)
            prev = self._last_hash()
            h = record_hash(rid, kind, created, idem_key, pj, prev)
            self.db.execute("INSERT INTO records(record_id, kind, created_utc, idem_key, payload, prev_hash, hash) "
                            "VALUES (?,?,?,?,?,?,?)", (rid, kind, created, idem_key, pj, prev, h))
        return {"record_id": rid, "kind": kind, "created_utc": created, "idem_key": idem_key,
                "payload": json.loads(pj), "prev_hash": prev, "hash": h, "duplicate": False}

    def _row(self, r):
        return {"seq": r[0], "record_id": r[1], "kind": r[2], "created_utc": r[3], "idem_key": r[4],
                "payload": json.loads(r[5]), "prev_hash": r[6], "hash": r[7]}

    def get_by_key(self, idem_key):
        r = self.db.execute("SELECT * FROM records WHERE idem_key=?", (idem_key,)).fetchone()
        return self._row(r) if r else None

    def records(self, kind=None):
        q, a = ("SELECT * FROM records WHERE kind=? ORDER BY seq", (kind,)) if kind else \
            ("SELECT * FROM records ORDER BY seq", ())
        return [self._row(r) for r in self.db.execute(q, a)]

    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM records").fetchone()[0]

    def verify(self):
        """None if the chain is intact, otherwise a description of the first broken record."""
        prev = ""
        for r in self.db.execute("SELECT seq, record_id, kind, created_utc, idem_key, payload, prev_hash, hash "
                                 "FROM records ORDER BY seq"):
            seq, rid, kind, created, key, pj, ph, h = r
            if ph != prev:
                return "record %d (%s): prev_hash does not match the previous record" % (seq, rid)
            if record_hash(rid, kind, created, key, pj, ph) != h:
                return "record %d (%s): content does not match its hash" % (seq, rid)
            prev = h
        return None

    def snapshot(self, dest):
        """Consistent copy via SQLite's online backup API (safe while the database is open)."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name("." + dest.name + ".tmp")
        out = sqlite3.connect(tmp)
        with out:
            self.db.backup(out)
        out.close()
        tmp.replace(dest)
        return dest

    def export_jsonl(self, dest):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name("." + dest.name + ".tmp")
        with open(tmp, "w") as fh:
            for r in self.records():
                fh.write(canonical(r) + "\n")
        tmp.replace(dest)
        return dest
