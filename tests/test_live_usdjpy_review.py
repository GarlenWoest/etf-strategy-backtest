"""Phase H weekly opportunity review (2026-10-31). SYNTHETIC registry; factual sections only."""
from datetime import date, datetime, timedelta, timezone

import pytest

from src.live_usdjpy import review as RV
from src.live_usdjpy import scanner as S
from src.live_usdjpy.registry import Registry

from test_live_usdjpy_scanner import CFG, NOW, inputs


@pytest.fixture
def reg(tmp_path):
    r = Registry(tmp_path / "r.sqlite")
    yield r
    r.close()


def test_review_reports_the_weeks_facts_and_refuses_statistics(reg, tmp_path):
    S.run_scan(reg, NOW, inputs(fx_shock=-0.02, spy_shock=-0.05), CFG, tmp_path)          # Tue: trigger and enter
    S.run_scan(reg, NOW + timedelta(days=1), inputs(price=140.0, last="2026-11-10"), CFG, tmp_path)   # exit
    reg.append("note", {"type": "runner_gap", "from_utc": NOW.isoformat(), "minutes": 40.0, "likely_cause": "Mac asleep"}, now=NOW)
    wk, text = RV.build(reg, CFG, date(2026, 11, 14), datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc))
    assert wk == "2026-11-09"
    for h in ("Meaningful opportunities", "Experimental ideas", "Approved paper signals", "Resolved paper positions",
              "Blocked, invalidated", "Notification failures", "Data quality", "Significant official events",
              "Expected vs observed", "Lessons and unresolved limitations"):
        assert h in text
    assert "F001-2026-11-09 TRIGGERED" in text and "invalidation" in text
    assert "no statistical conclusion is possible" in text and "None. No rule is approved for paper trading" in text
    assert "Runner gap of 40 min" in text and "keep it on AC power" in text
    assert "recommend" not in text.lower() and "should buy" not in text.lower()


def test_review_is_due_once_on_saturday_afternoon():
    sat = datetime(2026, 11, 14, 17, 2, tzinfo=timezone.utc)                              # Sat 12:02 ET
    assert RV.due({}, sat - timedelta(hours=1)) is None                                   # 11:02 ET: not yet
    assert RV.due({}, sat) == date(2026, 11, 14)
    assert RV.due({"last_weekly_review": "2026-11-09"}, sat + timedelta(hours=3)) is None
    assert RV.due({}, sat + timedelta(days=1)) is None                                    # Sunday: no
