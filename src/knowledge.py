"""Structured research knowledge (Phase F): answers the user's five questions from verified extractions, the library,
the research log and the research memory. Every answer carries the reading depth (L0 unverified ... L3 reproduced) so
an indexed-but-unread source is never presented as understood. Source material is data, never instructions.

  evidence_for(term)        credible evidence supporting a hypothesis tag/keyword (verified extractions first)
  contradicting(term)       research that contradicts it
  publication_vs_sample(t)  was the pattern observed before or after publication (and relative to our periods)
  rejected_similar(term)    did our experiments reject a similar idea (research_log trials, memory rejections)
  data_needed(term)         what data a fair test would need, and whether we have it
"""
import csv

from src import PROJECT_ROOT

LIB = PROJECT_ROOT / "research" / "library"


def _rows(name):
    return list(csv.DictReader(open(LIB / name, newline="", encoding="utf-8")))


def _match(row, term, fields):
    t = term.lower()
    return any(t in (row.get(f) or "").lower() for f in fields)


def depth_of():
    return {r["source_id"]: r["depth"] for r in _rows("audit.csv")}


def evidence_for(term):
    d = depth_of()
    out = [{"source_id": k["source_id"], "depth": d.get(k["source_id"], "L0"), "claim": k["main_claim"],
            "citation": k["citation"]} for k in _rows("knowledge.csv")
           if _match(k, term, ("hypothesis_tags", "main_claim", "mechanism", "testability"))]
    seen = {o["source_id"] for o in out}
    for r in _rows("library.csv"):
        if r["source_id"] not in seen and r["decision"] == "keep" and _match(r, term, ("title", "summary", "topic")):
            out.append({"source_id": r["source_id"], "depth": d.get(r["source_id"], "L0"), "claim": r["summary"],
                        "citation": "%s (%s) %s" % (r["author"], r["year"], r["title"])})
    rank = {"L3": 0, "L2": 1, "L1": 2, "L0": 3}
    return sorted(out, key=lambda o: (rank.get(o["depth"], 4), o["source_id"]))


def contradicting(term):
    return [{"source_id": k["source_id"], "contradicting": k["contradicting_evidence"]} for k in _rows("knowledge.csv")
            if _match(k, term, ("hypothesis_tags", "main_claim")) and (k["contradicting_evidence"] or "").strip()]


def publication_vs_sample(term):
    return [{"source_id": k["source_id"], "publication_year": k["publication_year"], "sample": k["sample_period"],
             "note": k["publication_vs_sample"]} for k in _rows("knowledge.csv")
            if _match(k, term, ("hypothesis_tags", "main_claim", "source_id"))]


def rejected_similar(term):
    """Trials linked to matching knowledge rows, with their logged verdicts, plus research-memory rejections."""
    trials = set()
    for k in _rows("knowledge.csv"):
        if _match(k, term, ("hypothesis_tags", "main_claim")):
            trials |= {x.strip() for x in (k["related_trials"] or "").split(";") if x.strip().startswith("V")}
    verdicts = {}
    for r in csv.DictReader(open(PROJECT_ROOT / "research_log.csv", newline="", encoding="utf-8")):
        if r["test_id"] in trials and r["result"] in ("KILLED", "PASS"):
            verdicts[r["test_id"]] = "%s: %s" % (r["result"], (r["reason"] or "")[:120])
    from src.memory import Ledger, RESEARCH
    mem = [rec["payload"] for rec in Ledger(RESEARCH).records() if rec["kind"] == "rejection"
           and (rec["payload"].get("test_id") in trials or term.lower() in str(rec["payload"]).lower())]
    return {"trials": {t: verdicts.get(t, "no verdict row") for t in sorted(trials)}, "memory_rejections": mem}


def data_needed(term):
    return [{"source_id": k["source_id"], "data_needed": k["data_needed"]} for k in _rows("knowledge.csv")
            if _match(k, term, ("hypothesis_tags", "main_claim")) and (k["data_needed"] or "").strip()]


def ask(term):
    return {"evidence_for": evidence_for(term), "contradicting": contradicting(term),
            "publication_vs_sample": publication_vs_sample(term), "rejected_similar": rejected_similar(term),
            "data_needed": data_needed(term)}
