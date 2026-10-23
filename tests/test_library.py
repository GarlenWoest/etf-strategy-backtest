"""Knowledge library: quality checks catch missing fields, bad classes, shifted columns and duplicates; FTS search."""
from src import PROJECT_ROOT
from src import library as LB


def row(**kw):
    base = {"source_id": "X1", "title": "A paper", "source_type": "journal", "evidence_class": "B", "evidence_strength": "strong",
            "decision": "keep", "provenance": "test", "url": "https://example.org", "year": "2010"}
    return {**base, **kw}


def test_quality_checks():
    assert LB.quality_problems([row()]) == []
    assert any("bad evidence_class" in p for p in LB.quality_problems([row(evidence_class="Z")]))
    assert any("implausible year" in p for p in LB.quality_problems([row(year="https://example.org")]))   # shifted columns
    assert any("url" in p for p in LB.quality_problems([row(url="journal (JF)")]))
    assert any("duplicate" in p for p in LB.quality_problems([row(), row(source_id="X2", title="A  PAPER!")]))
    assert LB.quality_problems([row(year="2009-2016")]) == []


def test_search_on_temporary_index():
    db = PROJECT_ROOT / "tmp" / "test_library.sqlite"
    LB.build_index([row(summary="carry trades crash when volatility rises", markets="usdjpy"),
                    row(source_id="X2", title="Gold note", summary="gold and real yields", markets="gold", decision="reject")], db)
    hits = LB.search("carry volatility", db=db)
    assert [h["source_id"] for h in hits] == ["X1"]
    assert LB.search("gold", db=db) == []                              # rejected sources hidden by default
    assert [h["source_id"] for h in LB.search("gold", db=db, include_rejected=True)] == ["X2"]
    db.unlink()
