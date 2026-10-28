"""Ask the research library the five Phase F questions about a hypothesis tag or keyword (read-only).
Usage: .venv/bin/python tools/knowledge.py carry        (tags include: carry, uip, zlb, yield_curve, relative_slope,
       risk_off, safe_haven, intervention, macro_announcements, session, fixings, trend, momentum, gold)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import knowledge as K

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    a = K.ask(" ".join(sys.argv[1:]))
    print("## Evidence for (depth: L0 unverified, L1 abstract verified, L2 content reviewed, L3 reproduced)")
    for e in a["evidence_for"]:
        print("- [%s] %s: %s" % (e["depth"], e["source_id"], e["claim"][:220]))
    print("\n## Contradicting")
    for c in a["contradicting"]:
        print("- %s: %s" % (c["source_id"], c["contradicting"]))
    print("\n## Observed before or after publication")
    for p in a["publication_vs_sample"]:
        print("- %s (published %s; sample %s): %s" % (p["source_id"], p["publication_year"], p["sample"], p["note"]))
    print("\n## Did our experiments reject a similar idea?")
    for t, v in a["rejected_similar"]["trials"].items():
        print("- %s %s" % (t, v))
    if not a["rejected_similar"]["trials"]:
        print("- no linked trial")
    print("\n## Data a fair test needs")
    for d in a["data_needed"]:
        print("- %s: %s" % (d["source_id"], d["data_needed"]))
