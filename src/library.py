"""Citation-backed knowledge library (expansion plan step 4). Standard library only (sqlite3 FTS5).

Canonical store: research/library/library.csv (public; citations plus our own summaries; never copyrighted full
texts). Search index: research/library/library.sqlite (derived, git-ignored, rebuilt by tools/build_library.py).

Evidence classes (the user's A-F, plus O for official facts):
  A financial theory            B academic empirical evidence      C professional opinion / industry research
  D anecdotal practitioner      E unverified strategy claims       F findings reproduced in our own experiments
  O official facts (rules, specifications, official data documentation)
Reading a source is not verifying its claims: `research_status` records how much was read (abstract, summary, full
text), and only class F records are our own verified findings.
"""
import csv
import re
import sqlite3
from pathlib import Path

from src import PROJECT_ROOT

LIB = PROJECT_ROOT / "research" / "library"
CSV_PATH = LIB / "library.csv"
DB_PATH = LIB / "library.sqlite"
FIELDS = ["source_id", "title", "author", "source_type", "year", "url", "markets", "topic", "evidence_strength",
          "evidence_class", "summary", "extracted_hypotheses", "methodology", "limitations", "contradicting",
          "reproducibility", "research_status", "last_verified", "decision", "notes", "provenance"]
CLASSES = set("ABCDEFO")
STRENGTHS = {"strong", "moderate", "weak", "n/a"}


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def quality_problems(rows):
    """Required fields, valid class/strength, URL form, plausible year, duplicates (normalized title + year)."""
    probs, seen = [], {}
    for r in rows:
        sid = r.get("source_id", "?")
        for f in ("source_id", "title", "source_type", "evidence_class", "evidence_strength", "decision", "provenance"):
            if not str(r.get(f, "")).strip():
                probs.append("%s: missing %s" % (sid, f))
        if r.get("evidence_class") and r["evidence_class"] not in CLASSES:
            probs.append("%s: bad evidence_class %r" % (sid, r["evidence_class"]))
        if r.get("evidence_strength") and r["evidence_strength"] not in STRENGTHS:
            probs.append("%s: bad evidence_strength %r" % (sid, r["evidence_strength"]))
        u = str(r.get("url", ""))
        if u and not (u.startswith("http") or u.startswith("UNVERIFIED") or u.startswith("reports/") or u.startswith("research/")):
            probs.append("%s: url is neither a link nor a project path nor marked UNVERIFIED" % sid)
        y = str(r.get("year", ""))
        if y and not (y.isdigit() and 1900 <= int(y) <= 2100) and not re.fullmatch(r"(19|20)\d\d-(19|20)\d\d", y):
            probs.append("%s: implausible year %r" % (sid, y))
        key = (norm_title(r.get("title")), y)
        if key in seen and r.get("decision") == "keep" and seen[key][1] == "keep":
            probs.append("%s: duplicate of %s (same normalized title and year)" % (sid, seen[key][0]))
        seen.setdefault(key, (sid, r.get("decision")))
    return probs


def read_rows(path=CSV_PATH):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build_index(rows, db=DB_PATH):
    db = Path(db)
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    con.execute("CREATE VIRTUAL TABLE lib USING fts5(%s, tokenize='porter unicode61')" % ", ".join(FIELDS))
    con.executemany("INSERT INTO lib VALUES (%s)" % ",".join("?" * len(FIELDS)), [[r.get(f, "") for f in FIELDS] for r in rows])
    con.commit()
    con.close()


def search(query, market=None, k=10, include_rejected=False, db=DB_PATH):
    """Full-text search (BM25 ranking) over titles, summaries, hypotheses, limitations, etc."""
    con = sqlite3.connect(db)
    q = " OR ".join('"%s"' % w.replace('"', "") for w in query.split()) if not any(c in query for c in '":*') else query
    sql = "SELECT source_id, title, author, year, evidence_class, evidence_strength, decision, markets, summary " \
          "FROM lib WHERE lib MATCH ? ORDER BY bm25(lib) LIMIT ?"
    rows = con.execute(sql, (q, k * 5)).fetchall()
    con.close()
    out = []
    for r in rows:
        d = dict(zip(["source_id", "title", "author", "year", "evidence_class", "evidence_strength", "decision", "markets", "summary"], r))
        if not include_rejected and d["decision"] != "keep":
            continue
        if market and market not in d["markets"].split(";") and "all" not in d["markets"]:
            continue
        out.append(d)
    return out[:k]
