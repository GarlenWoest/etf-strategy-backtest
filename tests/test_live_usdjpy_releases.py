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
    assert sorted(RL.queue(reg, NOW, store, CFG)) == ["BOJ", "NFP", "UK"]          # UK: GBP/USD observation item
    assert RL.queue(reg, NOW + timedelta(minutes=15), store, CFG) == []          # once per event
    n = [r["payload"] for r in reg.records("notification")]
    uk = [p for p in n if p["fields"]["market"] == "GBPUSD"]
    assert len(uk) == 1 and "observation market" in uk[0]["fields"]["validation_status"]
    from src.live_usdjpy import alerts as AL
    assert AL.is_phone(uk[0])[0] is False and all(AL.is_phone(p)[0] for p in n if p["fields"]["market"] == "USDJPY")
    n = [p for p in n if p["fields"]["market"] == "USDJPY"]
    assert all(p["priority"] == "NORMAL" and p["fields"]["class"] == "OFFICIAL RELEASE" for p in n)
    assert all("must not appear" not in str(p) for p in n)                       # no figures or interpretation
    assert n[0]["summary"].startswith("USD/JPY | OFFICIAL RELEASE |") and "https://example.gov/" in n[0]["fields"]["relevant_events"]


def test_a_new_feeds_old_items_are_not_replayed(reg):
    old = ev("BOE-OLD", "Bank of England", "Monetary Policy Summary, September 2026", NOW - timedelta(minutes=5), markets=("gbpusd",))
    old["published_time_source"] = (NOW - timedelta(days=40)).isoformat()        # first poll of the feed today
    assert RL.queue(reg, NOW, {"events": {"BOE-OLD": old}}, CFG) == []
    new = ev("BOE-NEW", "Bank of England", "Bank Rate maintained at 4%", NOW - timedelta(minutes=5), markets=("gbpusd",))
    assert RL.queue(reg, NOW, {"events": {"BOE-NEW": new}}, CFG) == ["BOE-NEW"]


def test_gld_sip_minute_bar_is_delayed_and_labelled(monkeypatch):
    from datetime import datetime, timezone
    from src.live_usdjpy import sources as SR
    calls = []

    class Rp:
        status_code = 200

        def json(self):
            return {"bars": {"GLD": [{"t": "2026-11-04T15:00:00Z", "c": 360.0}, {"t": "2026-11-04T15:01:00Z", "c": 360.5}]}}
    monkeypatch.setattr(SR, "secret", lambda item: "101-001-1234567-001" if item.endswith("account") else "X")
    now = datetime(2026, 11, 4, 15, 18, tzinfo=timezone.utc)                    # Wed 10:18 EST, NYSE open

    class FixedDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return now
    monkeypatch.setattr(SR, "datetime", FixedDT)                                 # retrieval time = the test's clock
    al = SR.Alpaca(http_get=lambda url, headers=None, timeout=None: calls.append(url) or Rp())
    b = SR.sip_last_minute(al, "GLD", now)
    assert b["close"] == 360.5 and b["time_utc"] == datetime(2026, 11, 4, 15, 2, tzinfo=timezone.utc)
    assert "feed=sip" in calls[0] and "end=2026-11-04T15%3A02%3A00Z" in calls[0]          # >= 16 min before now
    class O:
        def pricing(self):
            return {}
    snap = SR.snapshot(now, oanda=O(), alpaca=al)
    g = [o for o in snap["observations"] if o["specialist"] == "gold"][0]
    assert g["freshness"] == "DELAYED" and "INFORMATION ONLY" in g["quote_type"] and g["spread"] is None
