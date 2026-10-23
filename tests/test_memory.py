"""Research memory: append-only hash chain; edits, deletions and reordering are detected; corrections are new records."""
import json

import pytest

from src import PROJECT_ROOT
from src.memory import Ledger

P = PROJECT_ROOT / "tmp" / "test_memory.jsonl"


@pytest.fixture
def led():
    P.unlink(missing_ok=True)
    yield Ledger(P)
    P.unlink(missing_ok=True)


def test_append_verify_find(led):
    led.append("research_question", {"market": "usdjpy", "text": "Does carry pay in USD/JPY?"})
    led.append("hypothesis", {"market": "usdjpy", "id": "UJ-H1", "text": "carry magnitude"})
    assert led.verify() is None
    assert [r["payload"]["id"] for r in led.find(kind="hypothesis")] == ["UJ-H1"]
    assert len(led.related(["carry"], market="usdjpy")) == 2


def test_edit_detected_and_append_refused(led):
    led.append("forecast", {"market": "usdjpy", "p_up": 0.55})
    led.append("outcome", {"market": "usdjpy", "up": False})
    lines = P.read_text().splitlines()
    rec = json.loads(lines[0])
    rec["payload"]["p_up"] = 0.10                                   # rewrite a past forecast after the outcome
    P.write_text(json.dumps(rec, sort_keys=True) + "\n" + lines[1] + "\n")
    assert "changed" in led.verify()
    with pytest.raises(RuntimeError):
        led.append("decision", {"market": "usdjpy"})


def test_deletion_detected(led):
    for i in range(3):
        led.append("result", {"market": "usdjpy", "i": i})
    lines = P.read_text().splitlines()
    P.write_text(lines[0] + "\n" + lines[2] + "\n")
    assert led.verify() is not None


def test_unknown_kind_rejected(led):
    with pytest.raises(ValueError):
        led.append("gossip", {})
