"""Persistent research memory: append-only, hash-chained JSON-lines ledgers (expansion plan step 3).

Each record = {seq, ts_utc, kind, payload, prev_hash, hash}; hash = SHA-256 of the canonical JSON of everything except
`hash`. Records are never edited or deleted: a correction is a new record of kind "correction" that references the
seq it corrects. `verify()` recomputes the whole chain, so any edit, deletion, insertion or reordering is detected.

Two ledgers, by privacy:
  research/memory/research.jsonl   public research memory (questions, hypotheses, experiments, results, decisions,
                                   errors, data incidents, open questions); nothing from 2024+ markets
  live/memory/forecasts.jsonl      private (forecasts made from current data and their outcomes; git-ignored)
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from src import PROJECT_ROOT

KINDS = {"research_question", "source_read", "hypothesis", "preregistration", "experiment", "result", "rejection",
         "promising_unconfirmed", "forecast", "outcome", "error", "correction", "model_update", "regime_change",
         "data_incident", "open_question", "decision"}
RESEARCH = PROJECT_ROOT / "research" / "memory" / "research.jsonl"
FORECASTS = PROJECT_ROOT / "live" / "memory" / "forecasts.jsonl"
GENESIS = "0" * 64


def _hash(rec):
    body = {k: rec[k] for k in ("seq", "ts_utc", "kind", "payload", "prev_hash")}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


class Ledger:
    def __init__(self, path):
        self.path = Path(path)

    def records(self):
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def verify(self):
        """Return None if the chain is intact, else a description of the first problem."""
        prev = GENESIS
        for i, r in enumerate(self.records()):
            if r.get("seq") != i:
                return "record %d has seq %s (deleted, inserted or reordered record)" % (i, r.get("seq"))
            if r.get("prev_hash") != prev:
                return "record %d does not chain to the previous record" % i
            if _hash(r) != r.get("hash"):
                return "record %d was changed after it was written" % i
            prev = r["hash"]
        return None

    def append(self, kind, payload, now=None):
        if kind not in KINDS:
            raise ValueError("unknown record kind %r" % kind)
        problem = self.verify()
        if problem:
            raise RuntimeError("refusing to append: ledger integrity check failed: %s" % problem)
        recs = self.records()
        rec = {"seq": len(recs), "ts_utc": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "kind": kind, "payload": payload, "prev_hash": recs[-1]["hash"] if recs else GENESIS}
        rec["hash"] = _hash(rec)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n")
        return rec

    def find(self, kind=None, text=None, market=None):
        """Records filtered by kind, market (payload['market']) and a case-insensitive text match on the payload."""
        out = []
        for r in self.records():
            if kind and r["kind"] != kind:
                continue
            if market and r["payload"].get("market") not in (market, "all"):
                continue
            if text and text.lower() not in json.dumps(r["payload"], ensure_ascii=False).lower():
                continue
            out.append(r)
        return out

    def related(self, terms, market=None):
        """Retrieval before a new experiment: records mentioning any of the terms, newest first."""
        hits = {}
        for t in terms:
            for r in self.find(text=t, market=market):
                hits[r["seq"]] = r
        return sorted(hits.values(), key=lambda r: -r["seq"])
