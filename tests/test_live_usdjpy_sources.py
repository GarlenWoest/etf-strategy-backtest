"""Read-only OANDA practice and Alpaca market-data clients. No network: a fake GET returns canned JSON shaped like the
official responses (synthetic numbers). Includes the ORDER-BLOCKING tests required by the owner (2026-10-29)."""
import re
from datetime import datetime, timezone

import pytest

from src import PROJECT_ROOT
from src.live_usdjpy import sources as SR

ACCT = "101-001-1234567-001"


class Resp:
    def __init__(self, j, code=200):
        self._j, self.status_code = j, code

    def json(self):
        return self._j


@pytest.fixture(autouse=True)
def fake_keys(monkeypatch):
    monkeypatch.setattr(SR, "secret", lambda item: ACCT if item.endswith("oanda-account") else "SECRET-" + item)


def test_order_trade_position_and_account_change_endpoints_are_blocked_before_any_network_call():
    called = []
    get = lambda *a, **k: called.append(a) or Resp({})
    for host, path in [(SR.OANDA_HOST, "/v3/accounts/%s/orders" % ACCT), (SR.OANDA_HOST, "/v3/accounts/%s/trades" % ACCT),
                       (SR.OANDA_HOST, "/v3/accounts/%s/positions" % ACCT), (SR.OANDA_HOST, "/v3/accounts/%s/configuration" % ACCT),
                       (SR.OANDA_HOST, "/v3/accounts/%s/orders/1/cancel" % ACCT), ("https://api-fxtrade.oanda.com", "/v3/accounts/%s/pricing" % ACCT),
                       ("https://paper-api.alpaca.markets", "/v2/orders"), ("https://api.alpaca.markets", "/v2/orders"),
                       (SR.ALPACA_HOST, "/v2/orders"), (SR.OANDA_HOST, "/v3/instruments/EUR_USD/candles")]:
        with pytest.raises(SR.OrderEndpointBlocked):
            SR._get(host, path, {}, {}, get)
    assert called == []                                          # blocked before anything left the machine


def test_module_has_no_write_capability_at_all():
    src = (PROJECT_ROOT / "src" / "live_usdjpy" / "sources.py").read_text()
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert not re.search(r"requests\.(post|put|patch|delete)|\.post\(|\.put\(|\.patch\(|\.delete\(", code)
    assert "api-fxtrade" not in code and "paper-api.alpaca" not in code.replace('"https://paper-api.alpaca.markets", "/v2/orders"', "")
    assert set(SR.ALLOWED) == {SR.OANDA_HOST, SR.ALPACA_HOST}
    assert SR.OANDA_HOST == "https://api-fxpractice.oanda.com" and SR.ALPACA_HOST == "https://data.alpaca.markets"


def test_oanda_pricing_and_candles_parse_and_never_return_credentials():
    seen = []

    def get(url, headers=None, timeout=None):
        seen.append((url, headers))
        if "/pricing" in url:
            return Resp({"prices": [{"instrument": "USD_JPY", "time": "2026-11-02T14:00:00.123456789Z", "tradeable": True,
                                     "bids": [{"price": "150.000"}], "asks": [{"price": "150.016"}]}]})
        return Resp({"candles": [
            {"complete": True, "time": "2026-10-29T21:00:00.000000000Z", "mid": {"c": "149.5"}},
            {"complete": True, "time": "2026-11-01T22:00:00.000000000Z", "mid": {"c": "149.9"}},     # Sun 17:00 EST open
            {"complete": False, "time": "2026-11-02T22:00:00.000000000Z", "mid": {"c": "150.1"}}]})
    o = SR.Oanda(http_get=get)
    p = o.pricing(("USD_JPY",))["USD_JPY"]
    assert p["mid"] == pytest.approx(150.008) and p["spread_pips"] == pytest.approx(1.6)
    assert p["time_utc"] == datetime(2026, 11, 2, 14, 0, 0, 123456, tzinfo=timezone.utc)
    d = o.daily("USD_JPY")
    assert [x.date().isoformat() for x in d.index] == ["2026-10-30", "2026-11-02"]   # Fri bar; weekend; Mon bar (after DST end)
    assert len(d) == 2                                           # the incomplete candle is dropped
    assert "SECRET-" not in str(p) and "SECRET-" not in str(d)
    assert seen[0][1]["Authorization"].startswith("Bearer SECRET-")   # header used, never in results


def test_oanda_daily_candle_is_labelled_with_the_new_york_trade_date_it_ends_on():
    get = lambda url, headers=None, timeout=None: Resp({"candles": [
        {"complete": True, "time": "2026-10-28T21:00:00.000000000Z", "mid": {"c": "150.0"}}]})   # Wed 17:00 ET start
    d = SR.Oanda(http_get=get).daily("USD_JPY")
    assert d.index[0].date().isoformat() == "2026-10-29"         # ends Thu 17:00 ET -> Thursday's bar


def test_alpaca_quotes_and_paged_bars():
    pages = [{"bars": {"SPY": [{"t": "2026-10-28T04:00:00Z", "c": 600.0}]}, "next_page_token": "abc"},
             {"bars": {"SPY": [{"t": "2026-10-29T04:00:00Z", "c": 601.0}]}, "next_page_token": None}]

    def get(url, headers=None, timeout=None):
        assert headers["APCA-API-KEY-ID"].startswith("SECRET-")
        if "quotes/latest" in url:
            return Resp({"quotes": {"SPY": {"bp": 600.0, "ap": 600.1, "t": "2026-10-29T19:59:59.5Z"}}})
        return Resp(pages.pop(0))
    a = SR.Alpaca(http_get=get)
    q = a.latest_quotes(("SPY",))["SPY"]
    assert q["mid"] == pytest.approx(600.05) and q["feed"] == "iex"
    b = a.daily(("SPY",))["SPY"]
    assert [x.date().isoformat() for x in b.index] == ["2026-10-28", "2026-10-29"]


def test_source_errors_report_status_only():
    with pytest.raises(SR.SourceError) as e:
        SR._get(SR.ALPACA_HOST, "/v2/stocks/bars", {}, {"APCA-API-SECRET-KEY": "SECRET"}, lambda *a, **k: Resp({}, 403))
    assert "403" in str(e.value) and "SECRET" not in str(e.value)


def test_quote_fields_name_missing_crossed_and_locked_quotes():
    assert SR.quote_fields(150.0, 150.016, 0.01)["spread_pips"] == pytest.approx(1.6)
    assert SR.quote_fields(None, 150.0, 0.01)["quote_problems"] == ["bid"]
    assert SR.quote_fields(150.02, 150.0, 0.01)["quote_problems"] == ["crossed quote (bid > ask)"]
    q = SR.quote_fields(150.0, 150.0, 0.01)
    assert q["quote_problems"] == ["locked quote (bid = ask)"] and q["mid"] is None


def test_age_is_measured_from_retrieval_not_from_the_start_of_the_run():
    """Regression 2026-10-30: ages were measured from the run's start time (taken before the event poll and the price
    request), so every quote looked younger than zero (-0.7 to -4.8 s, -34 s after a 30 s event poll)."""
    from datetime import timedelta
    run_start = datetime(2026, 11, 2, 14, 0, 0, tzinfo=timezone.utc)
    quote = run_start + timedelta(seconds=33)
    meta = {"request_utc": run_start + timedelta(seconds=32.5), "retrieved_utc": run_start + timedelta(seconds=34),
            "server_date": "Mon, 02 Nov 2026 14:00:33 GMT"}
    t = SR.timing(quote, meta)
    assert t["age_s"] == pytest.approx(1.0) and t["clock_note"] is None
    assert t["server_clock_offset_s"] == pytest.approx(-0.2, abs=0.01)
    skewed = SR.timing(quote + timedelta(seconds=5), meta)
    assert skewed["age_s"] == pytest.approx(-4.0) and skewed["clock_note"].startswith("CLOCK SKEW")


def test_snapshot_marks_an_invalid_quote_unavailable_and_keeps_its_fields():
    now = datetime(2026, 11, 2, 14, 0, tzinfo=timezone.utc)
    crossed = {"USD_JPY": dict(SR.quote_fields(150.02, 150.0, 0.01), time_utc=now, tradeable=True, request_utc=now, retrieved_utc=now),
               "GBP_USD": dict(SR.quote_fields(1.30, 1.3002, 0.0001), time_utc=now, tradeable=True, request_utc=now, retrieved_utc=now)}

    class O:
        def pricing(self):
            return crossed

    class A:
        def latest_quotes(self, s):
            raise SR.SourceError("Alpaca returned HTTP 503")
    snap = SR.snapshot(now, oanda=O(), alpaca=A())
    uj = [o for o in snap["observations"] if o["specialist"] == "usdjpy"][0]
    assert uj["freshness"] == "UNAVAILABLE" and uj["last"] is None and "crossed" in uj["freshness_note"]
    assert uj["bid"] == 150.02 and uj["ask"] == 150.0 and uj["retrieved_utc"] == now.isoformat()
    gb = [o for o in snap["observations"] if o["specialist"] == "gbpusd"][0]
    assert gb["freshness"] == "LIVE" and gb["spread_pips"] == pytest.approx(2.0)
