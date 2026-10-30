"""Scorer and status page (acceptance test I). SYNTHETIC values only; expected numbers computed by hand."""
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from src import PROJECT_ROOT
from src.live_usdjpy import lifecycle as LC
from src.live_usdjpy import paper as PP
from src.live_usdjpy import scorer as SC
from src.live_usdjpy.registry import Registry

CFG = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text())["live_usdjpy"]
C, CS = CFG["costs"]["base"]["one_way"], CFG["costs"]["stress"]["one_way"]
MON = datetime(2026, 11, 9, 21, 0, tzinfo=timezone.utc)


@pytest.fixture
def reg(tmp_path):
    r = Registry(tmp_path / "r.sqlite")
    yield r
    r.close()


def closed_trade(reg, s1=150.0, s2=151.6, size=0.25):
    reg.append("market_state", {"bars": {"JPY=X": {"last_date": "2026-11-06", "last_close": 149.0}}, "usdjpy_sma20": 148.0,
                                "usdjpy_sessions": ["New York"]}, now=MON - timedelta(minutes=1))
    ev = reg.append("evaluation", {"type": "rule_signal", "rule_id": "F001", "kind": "CANDIDATE", "bar_date": "2026-11-06",
                                   "setup_id": "F001-2026-11-06", "direction": 1}, now=MON - timedelta(seconds=30))
    LC.transition(reg, "F001-2026-11-06", "triggered", {"bar_date": "2026-11-06"}, None, MON)
    PP.enter(reg, CFG, "F001", "F001-2026-11-06", {"direction": 1, "invalidation": 147.0, "target": 151.5,
                                                    "bar_date": "2026-11-06", "version": "0.2"}, size, s1, MON, "s1", {})
    PP.manage(reg, CFG, MON + timedelta(minutes=30), s2, {}, "s2")              # before the roll: no financing
    return ev


def test_I_prediction_unchanged_and_scorecard_shows_result_costs_and_baselines(reg):
    ev = closed_trade(reg)
    before = reg.records("evaluation")[0]["hash"]
    new = SC.score_closed(reg, CFG, MON + timedelta(hours=1))
    assert len(new) == 1 and SC.score_closed(reg, CFG, MON + timedelta(hours=2)) == []          # scored once
    assert reg.records("evaluation")[0]["hash"] == before == ev["hash"] and reg.verify() is None   # prediction untouched
    sc = new[0]
    N, E = 2500.0, 10000.0
    hand = (-N * 150.0 * (1 + C) + N * 151.6 * (1 - C)) / 151.6 / E
    assert sc["net_return_base"] == pytest.approx(hand)
    assert sc["net_return_stress"] == pytest.approx(hand - (CS - C) * 2 * N / E)
    assert sc["baselines"]["cash"] == 0.0
    assert sc["baselines"]["always_long"] == pytest.approx(hand)                 # same window, same size, long
    assert sc["baselines"]["historical_sample_mean"] == pytest.approx(hand)      # frozen sign +1
    assert sc["baselines"]["simple_trend"] == pytest.approx(hand)                # 150 > SMA20 148 -> long
    assert sc["direction_correct"] and sc["calibration"].startswith("UNKNOWN")
    assert [t["payload"]["state"] for t in reg.records("setup_transition")][-1] == "resolved"
    rows, counts = SC.scorecard(reg, CFG)
    assert rows["F001"]["n"] == 1 and rows["F001"]["statistics"] == "not computed: n < 30"
    assert "Fewer than 30 resolved signals" in rows["F001"]["banner"]
    assert counts["entered"] == 1 and counts["resolved"] == 1


def test_status_page_has_all_sections_and_labels(reg, tmp_path):
    closed_trade(reg)
    SC.score_closed(reg, CFG, MON + timedelta(hours=1))
    page = SC.status_page(reg, CFG, MON + timedelta(hours=1), {"observations": [], "status": {}}, tmp_path)
    for s in ("## System", "## Markets", "## Open paper positions", "## Opportunity history", "## Scorecard",
              "EXPERIMENTAL SHADOW SYSTEM", "Fewer than 30 resolved signals", "LaunchAgent at :02", "Gold (GLD reference)",
              "observation alerts only", "GBP/USD", "monitoring only", "F001-2026-11-06"):
        assert s in page, s


def test_placebo_uses_only_recorded_non_trigger_days_before_the_signal(reg):
    for i, d in enumerate(["2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-11-02", "2026-11-03"]):
        reg.append("market_state", {"bars": {"JPY=X": {"last_date": d, "last_close": 150.0 + 0.1 * i}}},
                   now=MON - timedelta(days=10 - i))
    closed_trade(reg)
    sc = SC.score_closed(reg, CFG, MON + timedelta(hours=1))[0]
    assert 1 <= sc["baselines"]["placebo_n"] <= 10 and sc["baselines"]["placebo_F001"] is not None
