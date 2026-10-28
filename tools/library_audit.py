"""Phase F library audit: what the library actually knows, per source, on the user's six questions.

  1 metadata/one-line summary only (reading depth not recorded)    2 abstract or summary read and verified (L1)
  3 relevant content reviewed (L2)                                  4 methods independently reproduced (L3)
  5 connected to a specific hypothesis or trial                     6 limitations / contradicting evidence recorded
Reads research/library/library.csv (built by tools/build_library.py), verification.csv and knowledge.csv; writes
research/library/audit.csv and prints the counts. Nothing is assumed: a source counts as read only if verification.csv
records what was read, and as reproduced only for our own (class F) findings.
Usage: .venv/bin/python tools/library_audit.py
"""
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import PROJECT_ROOT

LIB = PROJECT_ROOT / "research" / "library"
COLS = ["source_id", "evidence_class", "decision", "markets", "depth", "depth_basis", "bibliographic", "summary_check",
        "linked", "linked_to", "limitations_recorded", "contradictions_recorded", "corrected"]


def present(x):
    x = (x or "").strip().lower()
    return bool(x) and x not in ("—", "-", "see report", "n/a", "none")


def audit():
    lib = list(csv.DictReader(open(LIB / "library.csv", newline="", encoding="utf-8")))
    ver = {r["source_id"]: r for r in csv.DictReader(open(LIB / "verification.csv", newline="", encoding="utf-8"))}
    kn = {r["source_id"]: r for r in csv.DictReader(open(LIB / "knowledge.csv", newline="", encoding="utf-8"))}
    corr = Counter(r["source_id"] for r in csv.DictReader(open(LIB / "corrections.csv", newline="", encoding="utf-8")))
    out = []
    for r in lib:
        sid = r["source_id"]
        v = ver.get(sid)
        if r["evidence_class"] == "F":
            depth, basis = "L3", "own result: reproducible from code and logs in this repository"
        elif v:
            depth, basis = v["depth"], v["what_was_read"]
        else:
            depth, basis = "L0", "metadata and our one-line summary only; reading depth not recorded (%s)" % r["research_status"]
        k = kn.get(sid, {})
        linked_to = k.get("related_trials") or ""
        out.append({"source_id": sid, "evidence_class": r["evidence_class"], "decision": r["decision"], "markets": r["markets"],
                    "depth": depth, "depth_basis": basis,
                    "bibliographic": v["bibliographic"] if v else "not re-verified",
                    "summary_check": v["summary_check"] if v else "not checked",
                    "linked": "yes" if (present(linked_to) or present(r["extracted_hypotheses"])) else "no",
                    "linked_to": linked_to or (r["extracted_hypotheses"][:120] if present(r["extracted_hypotheses"]) else ""),
                    "limitations_recorded": "yes" if present(k.get("limitations") or r["limitations"]) else "no",
                    "contradictions_recorded": "yes" if present(k.get("contradicting_evidence") or r["contradicting"]) else "no",
                    "corrected": str(corr.get(sid, 0))})
    with open(LIB / "audit.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(out)
    return out


def summary(out):
    def tally(rows):
        c = Counter(r["depth"] for r in rows)
        return {"n": len(rows), "L0": c["L0"], "L1": c["L1"], "L2": c["L2"], "L3": c["L3"],
                "linked": sum(r["linked"] == "yes" for r in rows),
                "limitations": sum(r["limitations_recorded"] == "yes" for r in rows),
                "contradictions": sum(r["contradictions_recorded"] == "yes" for r in rows),
                "corrected": sum(int(r["corrected"]) > 0 for r in rows)}
    groups = {"all": out, "kept": [r for r in out if r["decision"] == "keep"],
              "usdjpy (kept)": [r for r in out if "usdjpy" in r["markets"] and r["decision"] == "keep"],
              "gold (kept)": [r for r in out if "gold" in r["markets"] and r["decision"] == "keep"],
              "gbpusd (kept)": [r for r in out if "gbpusd" in r["markets"] and r["decision"] == "keep"]}
    return {k: tally(v) for k, v in groups.items()}


if __name__ == "__main__":
    s = summary(audit())
    print("| Group | Sources | L0 depth not recorded | L1 abstract verified | L2 content reviewed | L3 reproduced (own) | "
          "Linked to a hypothesis | Limitations recorded | Contradictions recorded | Corrected in Phase F |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for k, t in s.items():
        print("| %s | %d | %d | %d | %d | %d | %d | %d | %d | %d |" % (k, t["n"], t["L0"], t["L1"], t["L2"], t["L3"], t["linked"],
                                                                 t["limitations"], t["contradictions"], t["corrected"]))
