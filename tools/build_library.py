"""Build the knowledge library: merge every graded source list into research/library/library.csv (canonical, public)
and rebuild the full-text index research/library/library.sqlite (derived, git-ignored).

Inputs (never modified): research/sources.csv (Study 1, S01-S49), research/sources_commodities.csv (Study 2,
C001-C153), research/library/usdjpy_sources.csv (USD/JPY specialist, FX001-FX021), research/library/sources_phaseF.csv
(sources added and verified in Phase F, FX022+), plus our own findings (F###, class F) written below from the project's
reports. Phase F (2026-10-28) overlays: research/library/corrections.csv (field corrections with reason and verifying
URL, applied here, so the historical inputs stay untouched) and research/library/verification.csv (what was actually
read: L1 abstract verified, L2 relevant full text reviewed). Rows without a verification record carry an honest
research_status: the earlier bulk labels "read (see ...)" did not record per-source reading depth. Evidence classes for migrated rows are assigned by a documented heuristic
from the source type and flagged for review in `notes`.
Usage: .venv/bin/python tools/build_library.py
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import PROJECT_ROOT
from src import library as LB

R = PROJECT_ROOT / "research"
VERIFIED = "2026-10-23"


def heuristic_class(stype, decision, reason):
    t = (stype or "").lower()
    if decision == "reject" and any(w in (reason or "").lower() for w in ("signal", "course", "marketing", "newsletter", "sells")):
        return "E"
    if any(w in t for w in ("journal", "academic", "working paper", "nber", "ssrn", "arxiv", "thesis", "seminar", "university")):
        return "B"
    if any(w in t for w in ("regulator", "statute", "exchange", "official", "central bank", "dataset", "regulatory", "government")):
        return "O"
    if t.strip() == "issuer" or "fund issuer page" in t:
        return "O"
    if any(w in t for w in ("industry", "asset manager", "index provider", "practitioner", "database", "research blog",
                            "book", "issuer", "tax firm", "professional")):
        return "C"
    return "D"


def strength(q):
    q = (q or "").strip().lower()
    return q if q in LB.STRENGTHS else "n/a"


def markets_for(text):
    t = (text or "").lower()
    m = []
    if "gold" in t or "gld" in t or "ugl" in t or "xau" in t:
        m.append("gold")
    if "yen" in t or "jpy" in t or "japan" in t:
        m.append("usdjpy")
    if "sterling" in t or "gbp" in t or "pound" in t or " uk " in " %s " % t:
        m.append("gbpusd")
    return ";".join(m) or "etf_or_commodities"


def rows():
    out = []
    for r in csv.DictReader(open(R / "sources.csv", newline="", encoding="utf-8")):
        out.append({"source_id": r["id"], "title": r["title"], "author": r["author"], "source_type": r["type"], "year": r["year"],
                    "url": r["link"], "markets": markets_for(r["title"] + " " + r["key_claim"]), "topic": "Study 1 literature",
                    "evidence_strength": strength(r["evidence_quality"]), "evidence_class": heuristic_class(r["type"], "keep", ""),
                    "summary": r["key_claim"], "extracted_hypotheses": "", "methodology": "", "limitations": r["notes"],
                    "contradicting": "", "reproducibility": "", "research_status": "listed in LITERATURE_REVIEW.md; per-source reading depth not recorded",
                    "last_verified": "2026-10-22", "decision": "keep", "notes": "class by heuristic from type; review",
                    "provenance": "research/sources.csv"})
    for r in csv.DictReader(open(R / "sources_commodities.csv", newline="", encoding="utf-8")):
        out.append({"source_id": r["id"], "title": r["title"], "author": r["author"], "source_type": r["type"], "year": r["year"],
                    "url": r["link"], "markets": markets_for(r["title"] + " " + r["topic"] + " " + r["key_claim"]),
                    "topic": r["topic"], "evidence_strength": strength(r["evidence_quality"]),
                    "evidence_class": heuristic_class(r["type"], r["decision"], r["reason"]), "summary": r["key_claim"],
                    "extracted_hypotheses": "", "methodology": "out-of-sample: %s; costs: %s; daily/ETF: %s" % (
                        r["out_of_sample"], r["costs_included"], r["works_daily_etf"]),
                    "limitations": r["grading_notes"], "contradicting": "", "reproducibility": "",
                    "research_status": "listed in IDEA_POOL_COMMODITIES.md; per-source reading depth not recorded", "last_verified": "2026-10-22",
                    "decision": r["decision"], "notes": "class by heuristic from type; review; reason: %s" % r["reason"],
                    "provenance": "research/sources_commodities.csv"})
    for r in csv.DictReader(open(R / "library" / "usdjpy_sources.csv", newline="", encoding="utf-8")):
        out.append({**{f: r.get(f, "") for f in LB.FIELDS}, "provenance": "research/library/usdjpy_sources.csv"})
    for r in csv.DictReader(open(R / "library" / "sources_phaseF.csv", newline="", encoding="utf-8")):
        out.append({**{f: r.get(f, "") for f in LB.FIELDS}, "provenance": "research/library/sources_phaseF.csv"})
    own = [
        ("F001", "Study 1: 92 pre-registered ETF strategies, 0 survive", "reports/FINAL_REPORT.md", "etf;gold",
         "Daily end-of-day rules on GLD/SPY/QQQ/TLT (+2x/3x), 2019-2023 validation: best Deflated Sharpe 0.73 (N=92); multi-asset trend near-misses had higher Sharpe but lower return than equal weight."),
        ("F002", "Study 2: 26 pre-registered commodity strategies, 0 survive", "reports/commodities_kill_table.md", "gold",
         "GLD/SLV/USO (+2x): best Deflated Sharpe 0.43 (N=118); gold real-yield and dollar filters, gold EWMAC trend all killed; best result carried by oil in 2021-2022."),
        ("F003", "Study 3: 16 long-history re-tests 1927-2018, 0 validated", "reports/study3_longhist.md", "gold;etf_or_commodities",
         "Multi-asset trend cut the worst fall from ~61% to ~22% but added no meaningful return; passes vanished at 2x/3x costs or a one-month lag."),
        ("F004", "GitHub survey: 20 most-starred trading-strategy repos", "reports/github_survey.md", "all",
         "0 of 20 READMEs clearly show out-of-sample results, 0 show live results, 2 show results with costs."),
        ("F005", "USD/JPY data quality: Yahoo daily FX bars fail cross-check against FRED H.10", "reports/specialists/usdjpy/data_quality.md", "usdjpy",
         "Levels agree but daily-return correlation is 0.39 (0.20 after 2011); DEXJPUS is the single price source; JGB 10Y matches OECD (corr 0.9995)."),
        ("F006", "USD/JPY study 1: 8 pre-registered rate-differential/carry/curve trials, 0 survive", "reports/specialists/usdjpy/study1_kill_table.md", "usdjpy",
         "Validation 2015-2023 at <=1x: best Deflated Sharpe 0.37 (N=142); always-long Sharpe 0.24; differential momentum and 63-day curve-slope rules lost to flat; the 126-day curve-slope rule had in-sample Sharpe -0.26 but validation 0.47 (unstable)."),
    ]
    for sid, title, path, mk, summ in own:
        out.append({"source_id": sid, "title": title, "author": "trading-research project", "source_type": "own study",
                    "year": "2026", "url": path, "markets": mk, "topic": "own findings", "evidence_strength": "n/a",
                    "evidence_class": "F", "summary": summ, "extracted_hypotheses": "", "methodology": "pre-registered; see report",
                    "limitations": "see report", "contradicting": "", "reproducibility": "code and logs in this repository",
                    "research_status": "own result", "last_verified": VERIFIED, "decision": "keep", "notes": "",
                    "provenance": path})
    return out


def apply_overlays(rs):
    """Phase F: apply field corrections and verification depth (never editing the historical input files)."""
    by = {r["source_id"]: r for r in rs}
    n = 0
    for c in csv.DictReader(open(R / "library" / "corrections.csv", newline="", encoding="utf-8")):
        r = by.get(c["source_id"])
        if r is None:
            raise SystemExit("correction for unknown source %s" % c["source_id"])
        r[c["field"]] = c["new_value"]
        tag = "corrected %s (%s): %s [%s]" % (c["verified_on"], c["field"], c["reason"], c["verified_url"])
        r["notes"] = (r["notes"] + "; " if r["notes"] else "") + tag
        n += 1
    for v in csv.DictReader(open(R / "library" / "verification.csv", newline="", encoding="utf-8")):
        r = by.get(v["source_id"])
        if r is None:
            raise SystemExit("verification for unknown source %s" % v["source_id"])
        r["research_status"] = "verified %s: %s (%s)" % (v["depth"], v["what_was_read"], v["verified_on"])
        r["last_verified"] = v["verified_on"]
    return n


def mark_duplicates(rs):
    """Later copies of a kept source (same normalized title and year) are kept for provenance but marked."""
    first = {}
    for r in rs:
        key = (LB.norm_title(r["title"]), r["year"])
        if r["decision"] == "keep" and key in first:
            r["decision"] = "duplicate"
            r["notes"] = ("duplicate of %s; " % first[key]) + r["notes"]
        elif r["decision"] == "keep":
            first[key] = r["source_id"]
    return rs


if __name__ == "__main__":
    rs = rows()
    n_corr = apply_overlays(rs)
    rs = mark_duplicates(rs)
    probs = LB.quality_problems(rs)
    with open(LB.CSV_PATH, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LB.FIELDS)
        w.writeheader()
        w.writerows(rs)
    LB.build_index(rs)
    from collections import Counter
    print("library rows:", len(rs), "| by class:", dict(sorted(Counter(r["evidence_class"] for r in rs).items())),
          "| keep:", sum(r["decision"] == "keep" for r in rs), "| corrections applied:", n_corr)
    print("quality problems (%d):" % len(probs))
    for p in probs[:40]:
        print("  -", p)
