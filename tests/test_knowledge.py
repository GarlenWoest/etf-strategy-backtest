"""Phase F library audit and knowledge base: overlays applied without touching historical inputs, depth claims backed
by verification records, honest status labels, and the five questions answered with depth attached."""
import csv

from src import PROJECT_ROOT
from src import knowledge as K

LIB = PROJECT_ROOT / "research" / "library"


def rows(name):
    return list(csv.DictReader(open(LIB / name, newline="", encoding="utf-8")))


def test_every_overlay_refers_to_an_existing_source():
    lib = {r["source_id"] for r in rows("library.csv")}
    for f in ("corrections.csv", "verification.csv", "knowledge.csv"):
        missing = {r["source_id"] for r in rows(f)} - lib
        assert not missing, (f, missing)


def test_depth_claims_are_backed_by_verification_records():
    ver = {r["source_id"]: r["depth"] for r in rows("verification.csv")}
    for a in rows("audit.csv"):
        if a["depth"] in ("L1", "L2"):
            assert ver.get(a["source_id"]) == a["depth"], a["source_id"]
        if a["depth"] == "L3":
            assert a["evidence_class"] == "F"                  # only our own reproducible results
    for k in rows("knowledge.csv"):
        assert k["depth"] == ver[k["source_id"]], k["source_id"]


def test_no_bulk_read_labels_and_corrections_applied():
    lib = {r["source_id"]: r for r in rows("library.csv")}
    assert not [s for s, r in lib.items() if r["research_status"].startswith("read (see")]
    assert lib["FX003"]["url"] == "https://www.nber.org/papers/w28420"
    assert lib["FX003"]["title"].startswith("A Reconsideration of the Failure of Uncovered Interest Parity")
    assert lib["FX012"]["title"].startswith("Effectiveness of Official Daily Foreign Exchange Market Intervention")
    assert "2008" not in lib["FX010"]["summary"].split("(")[0]
    assert "corrected 2026-10-28" in lib["FX012"]["notes"]


def test_historical_inputs_untouched():
    orig = {r["source_id"]: r for r in csv.DictReader(open(LIB / "usdjpy_sources.csv", newline="", encoding="utf-8"))}
    assert orig["FX012"]["title"].startswith("Is Sterilised Foreign Exchange Intervention Effective")   # preserved
    assert orig["FX003"]["url"].startswith("UNVERIFIED")


def test_five_questions():
    a = K.ask("relative_slope")
    assert a["evidence_for"][0]["source_id"] == "FX006" and a["evidence_for"][0]["depth"] == "L2"
    assert a["contradicting"] and "FX003" in a["contradicting"][0]["contradicting"]
    assert "after publication" in a["publication_vs_sample"][0]["note"]
    assert set(a["rejected_similar"]["trials"]) == {"V141", "V142"}
    assert all(v.startswith("KILLED") for v in a["rejected_similar"]["trials"].values())
    assert a["data_needed"]
    c = K.ask("carry")
    assert {"V135", "V136", "V139", "V140"} <= set(c["rejected_similar"]["trials"])
    depths = [e["depth"] for e in c["evidence_for"]]
    assert depths == sorted(depths, key=lambda d: {"L3": 0, "L2": 1, "L1": 2, "L0": 3}[d])   # verified first
    s = K.ask("session")
    assert not s["rejected_similar"]["trials"] and all("BLOCKED" in d["data_needed"] for d in s["data_needed"])
