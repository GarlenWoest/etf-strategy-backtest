"""Eligibility gate, risk gate and kill switch (acceptance tests D and K). Synthetic fixtures only."""
from datetime import datetime, timezone

import pytest
import yaml

from src import PROJECT_ROOT
from src.live_usdjpy import gate as G
from src.live_usdjpy.registry import Registry

CFG = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text())["live_usdjpy"]
TUE = datetime(2026, 11, 10, 21, 0, tzinfo=timezone.utc)           # Tue 16:00 ET: FX open, no guard window (11-03 is a JP holiday)


def cand(**kw):
    base = dict(rule_id="F001", version="0.2", instrument="USDJPY", direction=1, entry_ref=150.0, invalidation=148.5,
                target=150.75, setup_id="F001-2026-11-02")
    base.update(kw)
    return G.Candidate(**base)


def view(**kw):
    base = dict(now=TUE, price_freshness="LIVE", price_age_s=5, specialist_status="DATA OK", events=[])
    base.update(kw)
    return G.MarketView(**base)


def book(**kw):
    base = dict(equity=10000.0, peak_equity=10000.0, day_start_equity=10000.0, positions={})
    base.update(kw)
    return G.Book(**base)


def test_clean_candidate_is_sized_by_risk():
    d = G.decide(cand(), view(), book(), CFG)
    assert d.status == "APPROVED" and d.reasons == []
    assert d.size_x == pytest.approx(0.5)                         # 0.5% / 1% distance = 0.5x, at the per-rule cap
    d2 = G.decide(cand(invalidation=145.5), view(), book(), CFG)     # 3% away -> 0.5%/3% = 0.1667x
    assert d2.size_x == pytest.approx(0.005 / 0.03)


@pytest.mark.parametrize("kw,needle", [
    (dict(price_freshness="STALE", price_age_s=4000), "stale data"),
    (dict(specialist_status="STALE MARKET DATA"), "specialist status"),
    (dict(now=datetime(2026, 11, 7, 15, 0, tzinfo=timezone.utc)), "market closed"),         # Saturday
    (dict(events=[{"title": "Employment Situation", "scheduled_time_utc": "2026-11-10T20:30:00+00:00",
                   "status": "SCHEDULED"}]), "event blackout"),
])
def test_market_view_problems_block_with_reasons(kw, needle):
    d = G.decide(cand(), view(**kw), book(), CFG)
    assert d.status == "BLOCKED" and any(needle in r for r in d.reasons)


def test_invalid_instrument_and_unapproved_paper_rule_are_rejected():
    d = G.decide(cand(instrument="XAUUSD"), view(), book(), CFG)
    assert d.status == "BLOCKED" and any("invalid instrument" in r for r in d.reasons)
    d = G.decide(cand(mode="approved_paper"), view(), book(), CFG, approved_paper_rules=())
    assert any("not an approved paper rule" in r for r in d.reasons)
    assert G.decide(cand(mode="shadow"), view(), book(), CFG).status == "APPROVED"     # recorded as a shadow signal


def test_all_reasons_are_returned_not_just_the_first():
    d = G.decide(cand(instrument="GBPUSD", invalidation=151.0), view(price_freshness="STALE", price_age_s=999,
                 specialist_status="INSUFFICIENT DATA"), book(), CFG)
    assert len(d.reasons) >= 4


def test_excess_exposure_shrinks_then_blocks():
    d = G.decide(cand(rule_id="F002"), view(), book(positions={"F001": 0.8}), CFG)
    assert d.status == "SHRUNK" and d.size_x == pytest.approx(0.2)
    d = G.decide(cand(rule_id="F002"), view(), book(positions={"F001": 1.0}), CFG)
    assert d.status == "BLOCKED" and any("excess exposure" in r for r in d.reasons)
    d = G.decide(cand(), view(), book(positions={"F001": 0.3}), CFG)
    assert any("already has an open position" in r for r in d.reasons)


def test_trading_states_daily_loss_drawdown_and_close_all():
    d = G.decide(cand(), view(), book(equity=9890, day_start_equity=10000, peak_equity=10000), CFG)
    assert d.state == "REDUCING" and d.status == "BLOCKED"
    d = G.decide(cand(), view(), book(equity=9690, day_start_equity=9700, peak_equity=10000), CFG)
    assert d.state == "HALTED"
    st, info = G.derive_state(book(equity=9490, day_start_equity=9500, peak_equity=10000), CFG["risk_limits"], None, False, TUE)
    assert st == "HALTED" and info["close_all"] and info["experiment_stopped"]


def test_halted_is_sticky_until_manual_resume():
    prior = {"state": "HALTED", "why": ["drawdown"]}
    d = G.decide(cand(), view(), book(), CFG, prior_state=prior)
    assert d.state == "HALTED" and d.status == "BLOCKED"


def test_guards_are_labelled_conservative_temporary():
    fri = datetime(2026, 11, 6, 19, 0, tzinfo=timezone.utc)
    d = G.decide(cand(), view(now=fri), book(), CFG)
    assert any(r.startswith("GUARD") and "conservative temporary guard" in r for r in d.reasons)
    rollover = datetime(2026, 11, 10, 22, 30, tzinfo=timezone.utc)          # Tue 17:30 ET
    assert any("thin hours" in r for r in G.decide(cand(), view(now=rollover), book(), CFG).reasons)


def test_unknown_intervention_status_does_not_block_but_true_does():
    assert G.decide(cand(), view(mof_intervention_recent=None), book(), CFG).status == "APPROVED"
    assert G.decide(cand(), view(mof_intervention_recent=True), book(), CFG).status == "BLOCKED"


def test_kill_switch_halts_immediately_and_queues_a_high_alert(tmp_path):
    reg = Registry(tmp_path / "registry.sqlite")
    G.kill(reg, tmp_path, "test drill", now=TUE)
    assert G.kill_flag_path(tmp_path).exists()
    assert G.current_state(reg)["state"] == "HALTED"
    alerts = [r["payload"] for r in reg.records("notification")]
    assert alerts and alerts[0]["priority"] == "HIGH" and alerts[0]["status"] == "queued"
    G.kill(reg, tmp_path, "test drill", now=TUE)                                  # same minute: no duplicate alert
    assert len(reg.records("notification")) == 1
    d = G.decide(cand(), view(), book(), CFG, prior_state=G.current_state(reg), kill_on=G.kill_flag_path(tmp_path).exists())
    assert d.status == "BLOCKED" and d.state == "HALTED"
    with pytest.raises(ValueError):
        G.resume(reg, tmp_path, "yes")
    G.resume(reg, tmp_path, "RESUME", now=TUE)
    assert not G.kill_flag_path(tmp_path).exists() and G.current_state(reg)["state"] == "ACTIVE"
    assert reg.verify() is None
    reg.close()
