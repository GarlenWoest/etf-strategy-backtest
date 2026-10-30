"""OFFICIAL RELEASE alerts (owner request 2026-10-30). Synthetic event store; nothing is sent."""
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from src import PROJECT_ROOT
from src.live_usdjpy import releases as RL
from src.live_usdjpy.registry import Registry

CFG = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text())["live_usdjpy"]["official_release_alerts"]
NOW = datetime(2026, 11, 6, 14, 0, tzinfo=timezone.utc)


def ev(eid, source, title, detected, markets=("usdjpy", "gold"), status="PUBLISHED"):
    return {"event_id": eid, "source": source, "title": title, "status": status, "markets_affected": list(markets),
            "published_time_source": (detected - timedelta(minutes=10)).isoformat(), "detected_time_utc": detected.isoformat(),
            "publication_url": "https://example.gov/%s" % eid, "facts": [{"fact": "a number that must not appear"}]}


@pytest.fixture
def reg(tmp_path):
    r = Registry(tmp_path / "r.sqlite")
    yield r
    r.close()


def test_only_new_relevant_publications_alert_once_without_interpretation(reg):
    store = {"events": {e["event_id"]: e for e in [
        ev("NFP", "US Bureau of Labor Statistics", "Employment Situation", NOW - timedelta(minutes=20)),
        ev("BOJ", "Bank of Japan", "BoJ Monetary Policy Meeting statement", NOW - timedelta(hours=3)),
        ev("ECI", "US Bureau of Labor Statistics", "Employment Cost Index", NOW - timedelta(minutes=20)),   # not a key title
        ev("OLD", "Federal Reserve", "FOMC statement", NOW - timedelta(days=3)),                           # history: no replay
        ev("UK", "UK Office for National Statistics", "GDP monthly estimate", NOW, markets=("gbpusd",)),   # not USD/JPY
        ev("SCHED", "Federal Reserve", "FOMC minutes", NOW, status="SCHEDULED")]}}
    assert sorted(RL.queue(reg, NOW, store, CFG)) == ["BOJ", "NFP"]
    assert RL.queue(reg, NOW + timedelta(minutes=15), store, CFG) == []          # once per event
    n = [r["payload"] for r in reg.records("notification")]
    assert all(p["priority"] == "NORMAL" and p["fields"]["class"] == "OFFICIAL RELEASE" for p in n)
    assert all("must not appear" not in str(p) for p in n)                       # no figures or interpretation
    assert n[0]["summary"].startswith("USD/JPY | OFFICIAL RELEASE |") and "https://example.gov/" in n[0]["fields"]["relevant_events"]
