"""Financing-rate integrity (compliance fix + amendment v0.4, 2026-11-02). SYNTHETIC inputs only; every expected
amount comes from an independent reference written here (no simulator code). A missing rate is never 0%."""
import copy
import math
from datetime import date, datetime, timedelta, timezone

import pytest
import yaml

from src import PROJECT_ROOT
from src.live_usdjpy import financing as FIN
from src.live_usdjpy import lifecycle as LC
from src.live_usdjpy import paper as PP
from src.live_usdjpy.registry import Registry

CFG = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text())["live_usdjpy"]
NOW = datetime(2026, 11, 2, 22, 2, tzinfo=timezone.utc)                  # Mon 17:02 EST


class Resp:
    def __init__(self, text, code=200):
        self.text, self.status_code = text, code


def csv(sid, rows):
    return Resp("observation_date,%s\n" % sid + "".join("%s,%s\n" % r for r in rows))


def getter(answers):
    """answers: list of callables/Resp/Exception, consumed per call."""
    calls = []

    def get(url, timeout=None):
        calls.append(url)
        a = answers.pop(0) if answers else Resp("", 500)
        if isinstance(a, Exception):
            raise a
        return a(url) if callable(a) else a
    get.calls = calls
    return get


GOOD = lambda url: csv("DTB3", [("2026-10-29", "4.00"), ("2026-10-30", "3.98")]) if "DTB3" in url else \
    csv("IRSTCI01JPM156N", [("2026-08-01", "0.977"), ("2026-09-01", "1.043")])


# ---------------------------------------------------------------- fetch and validation

@pytest.mark.parametrize("resp, err", [
    (Resp("", 500), "HTTP 500"), (Resp("Too Many Requests", 429), "HTTP 429"), (Resp("<html>down</html>", 503), "HTTP 503"),
    (Resp("", 200), "not a FRED CSV"), (Resp("<html>ok</html>", 200), "not a FRED CSV"),
    (Resp("observation_date,DTB3\n2026-10-30,abc\n"), "malformed"), (Resp("observation_date,DTB3\n2026-10-30,nan\n"), "non-finite"),
    (Resp("observation_date,DTB3\n2026-10-30,400\n"), "outside the plausible range"),
    (Resp("observation_date,DTB3\n2099-01-01,4.0\n"), "future"), (Resp("observation_date,DTB3\n2026-10-30,.\n"), "no observations")])
def test_fetch_rejects_every_bad_response(resp, err):
    obs, e = FIN.fetch("DTB3", NOW, getter([resp]))
    assert obs is None and err in e


def test_fetch_timeout_and_percent_to_decimal_once_and_negative_and_zero_valid():
    assert FIN.fetch("DTB3", NOW, getter([TimeoutError()]))[1].startswith("request failed")
    obs, e = FIN.fetch("DTB3", NOW, getter([csv("DTB3", [("2026-10-29", "4.00"), ("2026-10-30", "0"), ("2026-10-31", "-0.10")])]))
    assert e is None and [v for _, v, _ in obs] == [0.04, 0.0, -0.001]


def test_failure_is_never_cached_and_retry_waits_15_minutes_then_success_replaces_it():
    fin = {}
    g = getter([TimeoutError(), TimeoutError(), GOOD, GOOD])
    FIN.refresh(fin, NOW, CFG, g)
    assert fin["usd"]["history"] == [] and fin["usd"]["last_error"] and fin["jpy"]["last_error"]
    assert FIN.refresh(fin, NOW + timedelta(minutes=10), CFG, g) == {"usd": "waiting to retry", "jpy": "waiting to retry"}
    assert len(g.calls) == 2                                                     # no download storm
    FIN.refresh(fin, NOW + timedelta(minutes=16), CFG, g)
    assert fin["usd"]["last_error"] is None and fin["usd"]["history"][-1]["obs_date"] == "2026-10-30"


def test_one_leg_failing_does_not_affect_the_other():
    fin = {}
    FIN.refresh(fin, NOW, CFG, getter([GOOD, Resp("", 503)]))
    assert fin["usd"]["history"] and not fin["jpy"]["history"] and "503" in fin["jpy"]["last_error"]


def test_valid_cache_is_kept_through_an_outage():
    fin = {}
    FIN.refresh(fin, NOW, CFG, getter([GOOD, GOOD]))
    FIN.refresh(fin, NOW + timedelta(hours=7), CFG, getter([Resp("", 503), Resp("", 503)]))
    r = FIN.resolve(fin, "usd", NOW + timedelta(hours=7), CFG, now=NOW + timedelta(hours=7))
    assert r["state"] == "VALID" and r["value"] == 0.0398 and r["last_error"] == "HTTP 503"


# ---------------------------------------------------------------- resolution states

def state_with(key, rows, seen=NOW - timedelta(days=400)):
    return {key: {"history": [{"obs_date": d, "value": v, "raw": str(v), "first_seen_utc": seen.isoformat()} for d, v in rows]}}


def roll(y, m, d):
    return datetime(y, m, d, 22, 0, tzinfo=timezone.utc)                # 17:00 EST


@pytest.mark.parametrize("obs, roll_day, state, age", [
    ("2026-10-29", (2026, 11, 2), "VALID", 2),                              # Thu value at the Monday roll (weekend)
    ("2026-10-28", (2026, 11, 2), "VALID", 3),
    ("2026-10-27", (2026, 11, 2), "LATE", 4),                               # carried forward, flagged
    ("2026-10-26", (2026, 11, 2), "LATE", 5),
    ("2026-10-23", (2026, 11, 2), "STALE", 6),
    ("2026-11-10", (2026, 11, 13), "VALID", 2),                             # Veterans Day 11-11 (Fed holiday) not counted
])
def test_dtb3_business_day_ages(obs, roll_day, state, age):
    r = FIN.resolve(state_with("usd", [(obs, 0.04)]), "usd", roll(*roll_day), CFG)
    assert (r["state"], r["age"], r["obs_date"]) == (state, age, obs) and r["carried_forward"] == (state == "LATE")


@pytest.mark.parametrize("roll_day, state", [((2026, 11, 2), "VALID"), ((2026, 12, 5), "VALID"), ((2026, 12, 20), "LATE"),
                                             ((2027, 1, 4), "LATE"), ((2027, 1, 5), "STALE")])
def test_monthly_japan_rate_ages(roll_day, state):
    r = FIN.resolve(state_with("jpy", [("2026-09-01", 0.01043)]), "jpy", roll(*roll_day), CFG)
    assert r["state"] == state and r["obs_date"] == "2026-09-01"            # original date kept, never relabelled


def test_zero_negative_and_missing():
    assert FIN.resolve(state_with("usd", [("2026-10-30", 0.0)]), "usd", roll(2026, 11, 2), CFG)["state"] == "VALID_ZERO"
    assert FIN.resolve(state_with("usd", [("2026-10-30", -0.001)]), "usd", roll(2026, 11, 2), CFG)["value"] == -0.001
    r = FIN.resolve({}, "usd", roll(2026, 11, 2), CFG)
    assert r["state"] == "MISSING" and r["value"] is None


def test_no_look_ahead_later_dated_or_not_yet_seen_observations_are_never_used():
    st = state_with("usd", [("2026-10-29", 0.04), ("2026-11-05", 0.05)])
    assert FIN.resolve(st, "usd", roll(2026, 11, 2), CFG)["value"] == 0.04          # 11-05 is dated after the roll
    st2 = state_with("usd", [("2026-10-30", 0.04)], seen=NOW + timedelta(days=1))
    assert FIN.resolve(st2, "usd", roll(2026, 11, 2), CFG, now=NOW)["state"] == "MISSING"   # not fetched yet at `now`


# ---------------------------------------------------------------- independent arithmetic reference

def reference(rolls, usd_pos, jpy, r_usd_by_roll, r_jpy_by_roll, fee=0.01):
    """Hand-written reference (NO simulator code): legs grow by their own currency's interest at each roll
    (USD ACT/360, JPY ACT/365, `days` 3 on Wednesday), the admin fee is |USD leg| x fee x days/365 in USD."""
    cash = 0.0
    for t, days in rolls:
        a_u = usd_pos * r_usd_by_roll[t] * days / 360.0
        a_j = jpy * r_jpy_by_roll[t] * days / 365.0
        cash -= abs(usd_pos) * fee * days / 365.0
        usd_pos += a_u
        jpy += a_j
    return usd_pos, jpy, cash


def enter(reg, direction, size_x, S, t):
    sig = {"direction": direction, "invalidation": 120.0 if direction > 0 else 190.0, "target": None, "bar_date": "2026-10-30",
           "version": "0.3", "expiry_rule": "x"}
    LC.transition(reg, "F002-T", "triggered", {"bar_date": "2026-10-30"}, None, t)
    PP.enter(reg, CFG, "F002", "F002-T", sig, size_x, S, t, "s0", {"setup_id": "F002-T"})


@pytest.fixture
def reg(tmp_path):
    r = Registry(tmp_path / "r.sqlite")
    yield r
    r.close()


RATES_HIST = {"usd": {"history": [{"obs_date": "2026-10-29", "value": 0.04, "raw": "4.00", "first_seen_utc": "2026-10-30T00:00:00+00:00"},
                                  {"obs_date": "2026-11-03", "value": 0.05, "raw": "5.00", "first_seen_utc": "2026-11-04T00:00:00+00:00"}]},
              "jpy": {"history": [{"obs_date": "2026-09-01", "value": 0.01043, "raw": "1.043", "first_seen_utc": "2026-10-29T00:00:00+00:00"}]}}


@pytest.mark.parametrize("direction", [1, -1])
def test_long_and_short_over_a_week_with_wednesday_triple_and_a_rate_change_match_the_reference(reg, direction):
    t0 = datetime(2026, 11, 2, 21, 0, tzinfo=timezone.utc)                  # Mon 16:00 EST, before the roll
    enter(reg, direction, 0.5, 150.0, t0)
    st0 = PP.state(reg, "F002", CFG)
    scans = [datetime(2026, 11, d, 22, 2, tzinfo=timezone.utc) for d in (2, 3, 4, 5, 6)]     # Mon..Fri 17:02 EST
    for k, t in enumerate(scans):
        PP.manage(reg, CFG, t, 150.0, RATES_HIST, "s%d" % (k + 1))
    rolls = [(datetime(2026, 11, d, 17, 0).isoformat(), 3 if d == 4 else 1) for d in (2, 3, 4, 5, 6)]
    ru = {t: (0.05 if t >= "2026-11-04" else 0.04) for t, _ in rolls}      # 11-03 value first used at the 11-04 roll
    rj = {t: 0.01043 for t, _ in rolls}
    u, j, c = reference(rolls, st0["usd_pos"], st0["jpy"], ru, rj)
    st = PP.state(reg, "F002", CFG)
    assert st["usd_pos"] == pytest.approx(u, abs=1e-9) and st["jpy"] == pytest.approx(j, abs=1e-6)
    assert st["cash"] - st0["cash"] == pytest.approx(c, abs=1e-9)
    fins = [r["payload"] for r in reg.records("fill") if r["payload"]["type"] == "financing"]
    assert [f["days"] for f in fins] == [1, 1, 3, 1, 1] and len(fins) == 5                   # no duplicate, none skipped
    assert all(f["r_usd_detail"]["obs_date"] for f in fins)
    if direction > 0:
        assert sum(f["usd_interest"] for f in fins) > 0 and sum(f["jpy_interest"] for f in fins) < 0
    else:
        assert sum(f["usd_interest"] for f in fins) < 0 and sum(f["jpy_interest"] for f in fins) > 0


def test_rescans_are_idempotent_and_no_accrual_without_a_position_or_after_close(reg):
    t0 = datetime(2026, 11, 2, 21, 0, tzinfo=timezone.utc)
    PP.manage(reg, CFG, NOW, 150.0, RATES_HIST, "x0")                        # no position at the roll
    enter(reg, 1, 0.5, 150.0, t0)
    for _ in range(3):
        PP.manage(reg, CFG, NOW, 150.0, RATES_HIST, "s1")
    assert len([r for r in reg.records("fill") if r["payload"]["type"] == "financing"]) == 1


def test_missing_rate_is_unresolved_then_trued_up_with_the_exact_reference_amount(reg):
    t0 = datetime(2026, 11, 2, 21, 0, tzinfo=timezone.utc)
    enter(reg, 1, 0.5, 150.0, t0)
    st0 = PP.state(reg, "F002", CFG)
    no_usd = {"usd": {"history": [], "last_error": "HTTP 503"}, "jpy": RATES_HIST["jpy"]}
    PP.manage(reg, CFG, NOW, 150.0, no_usd, "s1")                            # Monday roll: USD MISSING
    st1 = PP.state(reg, "F002", CFG)
    assert (st1["usd_pos"], st1["jpy"], st1["cash"]) == (st0["usd_pos"], st0["jpy"], st0["cash"])   # never 0% booked
    ok, rep = PP.reconcile(reg, CFG, NOW, 150.0)
    assert ok and rep["F002"]["exact_ok"] and "deferred" in rep["F002"]["parity_note"]   # no false HALT
    PP.manage(reg, CFG, NOW + timedelta(minutes=15), 150.0, RATES_HIST, "s2")  # data arrives: TRUE-UP
    tu = [r["payload"] for r in reg.records("fill") if r["payload"]["type"] == "financing_trueup"]
    u, j, c = reference([("x", 1)], st0["usd_pos"], st0["jpy"], {"x": 0.04}, {"x": 0.01043})
    assert len(tu) == 1 and tu[0]["roll_et"].startswith("2026-11-02T17:00")
    assert tu[0]["usd_interest"] == pytest.approx(u - st0["usd_pos"]) and tu[0]["jpy_interest"] == pytest.approx(j - st0["jpy"])
    assert -tu[0]["admin_fee_usd"] == pytest.approx(c)
    ok, rep = PP.reconcile(reg, CFG, NOW + timedelta(minutes=15), 150.0)
    assert ok and rep["F002"]["exact_ok"] and rep["F002"]["parity_note"] is None
    assert len([r for r in reg.records("fill") if r["payload"]["type"] == "financing_unresolved"]) == 1   # original kept


def test_true_up_after_the_position_closed_goes_to_cash_with_the_recorded_conversion(reg):
    t0 = datetime(2026, 11, 2, 21, 0, tzinfo=timezone.utc)
    enter(reg, 1, 0.5, 150.0, t0)
    st0 = PP.state(reg, "F002", CFG)
    PP.manage(reg, CFG, NOW, 150.0, {}, "s1")                                # unresolved (legacy-shaped empty input)
    PP.exit_position(reg, CFG, "F002", 150.0, NOW + timedelta(minutes=5), "s2", "test close")
    cash_closed = PP.state(reg, "F002", CFG)["cash"]
    PP.manage(reg, CFG, NOW + timedelta(minutes=10), 151.0, RATES_HIST, "s3")
    tu = [r["payload"] for r in reg.records("fill") if r["payload"]["type"] == "financing_trueup"][0]
    expected = st0["usd_pos"] * 0.04 / 360 + st0["jpy"] * 0.01043 / 365 / 151.0 - abs(st0["usd_pos"]) * 0.01 / 365
    assert tu["conversion_mid"] == 151.0 and PP.state(reg, "F002", CFG)["cash"] - cash_closed == pytest.approx(expected)
    ok, rep = PP.reconcile(reg, CFG, NOW + timedelta(minutes=10), 151.0)
    assert rep["F002"]["exact_ok"]


def test_parity_uses_the_same_per_roll_rates_so_a_rate_change_does_not_drift(reg):
    t0 = datetime(2026, 11, 2, 21, 0, tzinfo=timezone.utc)
    enter(reg, 1, 0.5, 150.0, t0)
    for k, d in enumerate((2, 3, 4, 5, 6, 9, 10, 11, 12, 13)):
        PP.manage(reg, CFG, datetime(2026, 11, d, 22, 2, tzinfo=timezone.utc), 150.0, RATES_HIST, "s%d" % k)
    ok, rep = PP.reconcile(reg, CFG, datetime(2026, 11, 13, 22, 3, tzinfo=timezone.utc), 150.0)
    assert ok and rep["F002"]["parity_ok"]


def test_legacy_flag_reproduces_the_old_zero_rate_behaviour_for_rollback(reg):
    cfg = copy.deepcopy(CFG)
    cfg["financing"]["policy"] = "legacy"
    t0 = datetime(2026, 11, 2, 21, 0, tzinfo=timezone.utc)
    enter(reg, 1, 0.5, 150.0, t0)
    PP.manage(reg, cfg, NOW, 150.0, {"usd": (None, "UNKNOWN (Timeout)"), "jpy": (0.01043, "x")}, "s1")
    f = [r["payload"] for r in reg.records("fill") if r["payload"]["type"] == "financing"][0]
    assert f["usd_interest"] == 0 and f["policy"] == "legacy"


# ---------------------------------------------------------------- ETF books, preflight, events, W005 grace

def test_etf_tbill_rate_states():
    import importlib.util
    import pandas as pd
    spec = importlib.util.spec_from_file_location("pb", PROJECT_ROOT / "tools" / "paper_books.py")
    PB = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(PB)
    irx = pd.Series({pd.Timestamp("2026-10-29"): 4.0, pd.Timestamp("2026-10-30"): float("nan"), pd.Timestamp("2026-11-02"): float("nan")})
    r, d = PB.tbill_rate(irx, pd.Timestamp("2026-10-30"), date(2026, 11, 2))
    assert r == pytest.approx(0.04 / 252) and d["state"] == "VALID" and d["obs_date"] == "2026-10-29"
    r, d = PB.tbill_rate(irx, pd.Timestamp("2026-11-02"), date(2026, 11, 5))         # 5 US business days after 10-29
    assert r is not None and d["state"] == "LATE" and d["carried_forward"]
    r, d = PB.tbill_rate(irx, pd.Timestamp("2026-11-02"), date(2026, 11, 6))         # 6
    assert r is None and d["state"] == "STALE"                               # never 0%
    r, d = PB.tbill_rate(pd.Series(dtype=float), pd.Timestamp("2026-11-02"), date(2026, 11, 3))
    assert r is None and d["state"] == "MISSING"


def test_preflight_reports_financing_as_degraded_never_blocked(reg):
    from src.live_usdjpy import preflight as PF
    import pandas as pd
    snap = {"observations": [{"specialist": "usdjpy", "role": "primary", "freshness": "LIVE", "quote_problems": [], "session_open": True}],
            "status": {"usdjpy": "DATA OK"}}
    bars = {"USD_JPY": pd.Series([150.0], index=[pd.Timestamp("2026-11-02")]), "SPY": pd.Series([600.0], index=[pd.Timestamp("2026-11-02")])}
    st = {"financing": {"usd": {"history": [], "last_error": "HTTP 503"}, "jpy": RATES_HIST["jpy"]}}
    pf = PF.check(datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc), reg, snap, bars,
                  {"generated_utc": NOW.isoformat(), "events": {}}, st, CFG["preflight"], live_cfg=CFG)
    c = [x for x in pf["checks"] if x["check"] == "financing rates"][0]
    assert c["status"] == "DEGRADED" and "MISSING" in c["detail"] and pf["blocks"] == []


def test_event_monitor_records_reactions_as_unknown_without_any_download():
    import importlib.util
    src = (PROJECT_ROOT / "tools" / "events.py").read_text()
    assert "yfinance" not in src and "import yf" not in src
    spec = importlib.util.spec_from_file_location("ev", PROJECT_ROOT / "tools" / "events.py")
    EV = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(EV)
    store = {"events": {"X": {"status": "PUBLISHED", "markets_affected": ["usdjpy"], "market_reaction": {}},
                        "Y": {"status": "PUBLISHED", "markets_affected": ["usdjpy"], "market_reaction": {"usdjpy": {"status": "COMPLETE", "initial_bp": 5}}}}}
    EV.reactions(store, NOW)
    assert store["events"]["X"]["market_reaction"]["usdjpy"]["status"] == "UNKNOWN"
    assert store["events"]["Y"]["market_reaction"]["usdjpy"]["initial_bp"] == 5               # earlier records kept


def test_w005_reopen_grace_quiet_when_prices_recover_alerted_when_they_do_not(reg):
    from src.live_usdjpy import watch as W
    cfg = CFG["market_watch"]
    sun = lambda h, m: datetime(2026, 11, 8, h + 5, m, tzinfo=timezone.utc)          # EST = UTC-5

    def snap(fresh):
        return {"observations": [{"specialist": s, "role": "primary", "freshness": fresh if s != "gold" else "CLOSED_LAST_PRICE",
                                  "session_open": s != "gold", "last": 150.0} for s in ("usdjpy", "gbpusd", "gold")],
                "status": {"usdjpy": "DATA OK" if fresh == "LIVE" else "STALE MARKET DATA", "gbpusd": "DATA OK" if fresh == "LIVE" else "STALE MARKET DATA", "gold": "DATA OK"}}
    ev = {"events": {}}
    W.run(reg, sun(17, 2), {}, snap("STALE"), ev, cfg)
    W.run(reg, sun(17, 17), {}, snap("LIVE"), ev, cfg)
    assert [n for n in reg.records("notification")] == []                             # quiet: recovered inside the grace
    W.run(reg, sun(17, 18) + timedelta(days=7), {}, snap("STALE"), ev, cfg)
    W.run(reg, sun(17, 47) + timedelta(days=7), {}, snap("STALE"), ev, cfg)          # still down after the grace
    titles = [n["payload"]["title"] for n in reg.records("notification")]
    assert any("continues after the reopen grace" in t for t in titles)
    W.run(reg, datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc), {}, snap("STALE"), ev, cfg)   # weekday: normal alerting


def test_regression_entry_day_price_move_does_not_cause_a_false_parity_halt(reg):
    """Regression 2026-11-01: v2_replay treated the LAST mark of the entry's UTC day as the entry price, so a move between
    the fill and 19:00 EST (00:00 UTC) became a ledger-vs-v2 mismatch. Here: F002-like entry (0.0738x) Sunday 19:02 EST
    at mid 150.000, then +50 pips before the next 19:00 EST, same UTC day -> the old replay showed a gap > $2 (HALT)."""
    t_entry = datetime(2026, 11, 9, 0, 2, tzinfo=timezone.utc)                 # Sun 19:02 EST
    enter(reg, 1, 0.0737593, 150.000, t_entry)
    PP.manage(reg, CFG, t_entry + timedelta(minutes=15), 150.000, RATES_HIST, "m1")
    t_mark = datetime(2026, 11, 9, 21, 47, tzinfo=timezone.utc)                # Mon 16:47 EST, before the 17:00 roll
    PP.manage(reg, CFG, t_mark, 150.500, RATES_HIST, "m2")
    ok, rep = PP.reconcile(reg, CFG, t_mark, 150.500)
    r = rep["F002"]
    assert ok and r["parity_ok"], r
    assert abs(r["ledger_pnl"] - r["v2_pnl"]) < 0.05                              # same entry price on both sides
    # and the next UTC day, after the roll: the entry-day move is not frozen into a permanent gap
    t2 = datetime(2026, 11, 10, 22, 2, tzinfo=timezone.utc)
    PP.manage(reg, CFG, t2, 150.600, RATES_HIST, "m3")
    ok, rep = PP.reconcile(reg, CFG, t2, 150.600)
    assert ok and abs(rep["F002"]["ledger_pnl"] - rep["F002"]["v2_pnl"]) < 0.5
