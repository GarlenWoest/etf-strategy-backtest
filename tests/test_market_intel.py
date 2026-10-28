"""Current-market intelligence (Phase B): freshness, sessions, alignment, ECB cross precision, status words, and
isolation from the research code. Offline (no network)."""
import ast
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import PROJECT_ROOT, load_config
from src import market_intel as M

UTC = timezone.utc
CFG = load_config()["market_intel"]
FX = CFG["freshness"]["fx_indicative_1m"]
EX = CFG["freshness"]["exchange_delayed_1m"]


def u(s):
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


def test_fx_freshness_open_market():
    now = u("2026-10-28T17:55:00")                                        # Wednesday, FX open
    assert M.freshness_intraday(now - timedelta(seconds=30), now, FX, "fx")[0] == "LIVE"
    assert M.freshness_intraday(now - timedelta(seconds=600), now, FX, "fx")[0] == "DELAYED"
    assert M.freshness_intraday(now - timedelta(hours=2), now, FX, "fx")[0] == "STALE"
    assert M.freshness_intraday(None, now, FX, "fx")[0] == "UNAVAILABLE"
    assert M.freshness_intraday(now + timedelta(minutes=5), now, FX, "fx")[0] == "UNAVAILABLE"


def test_fx_freshness_weekend_uses_friday_close():
    sat = u("2026-10-31T15:00:00")                                        # Saturday; FX closed since Fri 17:00 NY
    fri_close = u("2026-10-30T21:00:00")                                  # 17:00 EDT
    assert M.last_close("fx", sat) == fri_close
    assert M.freshness_intraday(fri_close - timedelta(minutes=2), sat, FX, "fx")[0] == "CLOSED_LAST_PRICE"
    assert M.freshness_intraday(fri_close - timedelta(hours=3), sat, FX, "fx")[0] == "STALE"


def test_declared_delay_is_delayed_not_live():
    now = u("2026-10-28T17:55:00")
    st, age, _ = M.freshness_intraday(now - timedelta(seconds=605), now, EX, "cme_metals", declared_delay_s=600)
    assert st == "DELAYED" and age == 605
    assert M.freshness_intraday(now - timedelta(seconds=10), now, EX, "nyse")[0] == "LIVE"


def test_sessions():
    assert M.nyse_open(u("2026-10-28T17:55:00")) and not M.nyse_open(u("2026-10-28T21:00:00"))   # 13:55 / 17:00 ET
    assert not M.nyse_open(u("2026-11-26T17:00:00"))                                          # Thanksgiving
    assert M.cme_metals_open(u("2026-10-28T17:55:00"))
    assert not M.cme_metals_open(u("2026-10-28T21:30:00"))                                    # 17:30 ET daily break
    assert not M.cme_metals_open(u("2026-11-01T21:00:00"))                                    # Sunday 16:00 EST
    assert M.cme_metals_open(u("2026-11-01T23:30:00"))                                        # Sunday 18:30 EST


def test_nyse_closed_last_price_after_close():
    now = u("2026-10-28T22:30:00")                                        # 18:30 ET
    close = u("2026-10-28T20:00:00")                                      # 16:00 ET
    assert M.last_close("nyse", now) == close
    assert M.freshness_intraday(close - timedelta(seconds=30), now, EX, "nyse")[0] == "CLOSED_LAST_PRICE"


def test_reference_freshness():
    assert M.freshness_reference(date(2026, 10, 23), date(2026, 10, 28), 12) == ("CURRENT", 5)
    assert M.freshness_reference(date(2026, 10, 1), date(2026, 10, 28), 12) == ("STALE", 27)
    assert M.freshness_reference(None, date(2026, 10, 28), 12) == ("UNAVAILABLE", None)
    assert M.freshness_daily_close(date(2026, 10, 23), date(2026, 10, 27), 2) == ("CURRENT", 2)
    assert M.freshness_daily_close(date(2026, 10, 22), date(2026, 10, 27), 2)[0] == "STALE"


def test_value_at_never_uses_a_later_bar():
    idx = pd.date_range("2026-10-28T13:05", periods=10, freq="1min", tz="UTC")
    bars = pd.Series(np.arange(10, dtype=float), index=idx)
    v, end = M.value_at(bars, u("2026-10-28T13:10:00"))
    assert v == 4.0 and end == u("2026-10-28T13:10:00")                  # bar 13:09-13:10, not 13:10-13:11
    v, end = M.value_at(bars, u("2026-10-28T13:10:30"))
    assert v == 4.0                                                      # the 13:10 bar has not ended yet
    gappy = bars.drop(idx[2:6])
    assert M.value_at(gappy, u("2026-10-28T13:10:30"), max_gap_s=120) == (None, None)
    assert M.value_at(bars, u("2026-10-28T13:00:00")) == (None, None)


def test_ecb_cross_and_precision():
    v, rel = M.ecb_cross("175.86", "1.1133")
    assert abs(v - 175.86 / 1.1133) < 1e-12
    assert abs(rel - (0.005 / 175.86 + 0.00005 / 1.1133)) < 1e-15
    _, rel_stripped = M.ecb_cross("175.86", "1.113")                     # XML dropped a trailing zero
    _, rel_fixed = M.ecb_cross("175.86", "1.113", 2, 4)
    assert rel_stripped > rel_fixed and abs(rel_fixed - (0.005 / 175.86 + 0.00005 / 1.113)) < 1e-15


def test_documented_reference_times():
    assert M.ecb_concertation_utc(date(2026, 10, 28)) == u("2026-10-28T13:10:00")   # CET (winter)
    assert M.ecb_concertation_utc(date(2026, 10, 23)) == u("2026-10-23T12:10:00")   # CEST (summer)
    assert M.h10_noon_utc(date(2026, 10, 23)) == u("2026-10-23T16:00:00")           # EDT
    assert M.h10_noon_utc(date(2026, 11, 2)) == u("2026-11-02T17:00:00")            # EST


def test_compare_units():
    c = M.compare(158.27, 158.25, 0.01)
    assert abs(c["pips"] - 2.0) < 1e-9 and abs(c["bp"] - 1e4 * 0.02 / 158.25) < 1e-9


def test_realized_vol_and_specialist_status():
    rng = np.random.default_rng(0)
    closes = 150 * np.exp(np.cumsum(rng.normal(0, 0.005, 40)))
    v = M.realized_vol(closes, 20, 21)
    assert 0.03 < v < 0.15
    assert M.realized_vol(closes[:10], 20, 21) is None
    w = CFG["specialist_status"]
    assert M.specialist_status("LIVE", v, w) == "DATA OK"
    assert M.specialist_status("STALE", v, w) == "STALE MARKET DATA"
    assert M.specialist_status("LIVE", None, w) == "INSUFFICIENT DATA"
    assert M.specialist_status("UNAVAILABLE", v, w) == "INSUFFICIENT DATA"


def _imports(path):
    tree = ast.parse(Path(path).read_text())
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            names |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            names.add(n.module)
            names |= {"%s.%s" % (n.module, a.name) for a in n.names}
    return names


def test_isolation_research_code_never_uses_market_intel_or_live():
    """Monitoring must not leak into research: no src/ module or research tool imports market_intel or reads live/."""
    allowed = {"tools/market_intel.py", "src/market_intel.py"}
    offenders = []
    for p in list((PROJECT_ROOT / "src").rglob("*.py")) + list((PROJECT_ROOT / "tools").glob("*.py")):
        rel = str(p.relative_to(PROJECT_ROOT))
        if rel in allowed:
            continue
        if any("market_intel" in x for x in _imports(p)):
            offenders.append(rel)
        mentions_live = '"live"' in p.read_text() or "'live'" in p.read_text() or "live/" in p.read_text()
        if rel.startswith("src/") and mentions_live and rel != "src/memory.py":     # memory.py only defines the path of
            offenders.append(rel + " (mentions live/)")                             # the private forecast ledger
        if rel.startswith("src/") and "src.memory.FORECASTS" in _imports(p):
            offenders.append(rel + " (uses the forecast ledger)")
    assert offenders == []


def test_market_intel_writes_only_to_allowed_folders():
    import importlib.util
    spec = importlib.util.spec_from_file_location("mi", PROJECT_ROOT / "tools" / "market_intel.py")
    mi = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mi)
    with pytest.raises(RuntimeError):
        mi._guard(PROJECT_ROOT / "data" / "x.json")
    with pytest.raises(RuntimeError):
        mi._guard(PROJECT_ROOT / "research_log.csv")
    assert mi._guard(PROJECT_ROOT / "live" / "intel" / "latest.json")
