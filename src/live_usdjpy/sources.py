"""Read-only market-data clients for the USD/JPY forward system (owner decision 2026-10-29).

  OANDA v20 PRACTICE API  USD/JPY, GBP/USD: current bid/ask (pricing endpoint) and daily candles (17:00 New York
                          alignment, complete flag). Host is hard-wired to api-fxpractice.oanda.com.
  Alpaca market data      SPY (F001's second leg) and GLD (gold reference): latest IEX quote and daily IEX bars.
                          Host is hard-wired to data.alpaca.markets (never the trading hosts).

READ-ONLY BY CONSTRUCTION: every request goes through `_get`, which allows only HTTP GET to an explicit allow-list
of path patterns (pricing, candles, latest quotes, bars). Order, trade, position and account-changing endpoints are
not in the list, any other method or path raises OrderEndpointBlocked before a network call is made, and a test
asserts this. Credentials come from the macOS Keychain at call time (notify.secret); they are never logged, stored
in records or returned. Errors report only the exception type and HTTP status.
Prices are the venues' indicative practice/IEX data: never presented as executable fills.
"""
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import pandas as pd

from src import clock as K
from src import market_intel as MI

from .notify import secret

NY = ZoneInfo("America/New_York")
OANDA_HOST = "https://api-fxpractice.oanda.com"
ALPACA_HOST = "https://data.alpaca.markets"
ALLOWED = {
    OANDA_HOST: (r"^/v3/accounts/[0-9]{3}-[0-9]{3}-[0-9]{6,9}-[0-9]{3}/pricing$",
                 r"^/v3/instruments/(USD_JPY|GBP_USD)/candles$"),
    ALPACA_HOST: (r"^/v2/stocks/quotes/latest$", r"^/v2/stocks/bars$"),
}
FX = {"usdjpy": "USD_JPY", "gbpusd": "GBP_USD"}
PIP = {"USD_JPY": 0.01, "GBP_USD": 0.0001}


class OrderEndpointBlocked(RuntimeError):
    pass


class SourceError(RuntimeError):
    pass


def _get(host, path, params, headers, http_get=None):
    """The ONLY way this module touches the network: GET to an allow-listed path on a hard-wired host."""
    if host not in ALLOWED or not any(re.match(p, path) for p in ALLOWED[host]):
        raise OrderEndpointBlocked("blocked: %s%s is not an allow-listed read-only endpoint" % (host, path))
    import requests
    get = http_get or requests.get
    try:
        r = get(host + path + ("?" + urlencode(params) if params else ""), headers=headers, timeout=20)
    except Exception as ex:
        raise SourceError("%s request failed: %s" % (host, type(ex).__name__)) from None
    if r.status_code != 200:
        raise SourceError("%s returned HTTP %d" % (host, r.status_code))
    return r.json()


def _post_is_never_available(*a, **k):                 # documents intent; nothing in this module posts
    raise OrderEndpointBlocked("this module has no write or order capability")


class Oanda:
    def __init__(self, http_get=None):
        self.http_get = http_get

    def _h(self):
        tok = secret("trading-research-oanda-token")
        if not tok:
            raise SourceError("OANDA practice token not configured")
        return {"Authorization": "Bearer " + tok, "Accept-Datetime-Format": "RFC3339"}

    def pricing(self, instruments=("USD_JPY", "GBP_USD")):
        acct = secret("trading-research-oanda-account")
        if not acct:
            raise SourceError("OANDA practice account id not configured")
        j = _get(OANDA_HOST, "/v3/accounts/%s/pricing" % acct, {"instruments": ",".join(instruments)}, self._h(), self.http_get)
        out = {}
        for p in j.get("prices", []):
            bid, ask = float(p["bids"][0]["price"]), float(p["asks"][0]["price"])
            out[p["instrument"]] = {"bid": bid, "ask": ask, "mid": (bid + ask) / 2, "spread": ask - bid,
                                    "spread_pips": (ask - bid) / PIP.get(p["instrument"], 1), "time_utc": _ts(p["time"]),
                                    "tradeable": p.get("tradeable")}
        return out

    def daily(self, instrument, count=400):
        """COMPLETE daily mid candles, 17:00 New York alignment. Index = New York trade date the candle ends on."""
        j = _get(OANDA_HOST, "/v3/instruments/%s/candles" % instrument,
                 {"granularity": "D", "count": count, "price": "M", "dailyAlignment": 17, "alignmentTimezone": "America/New_York"},
                 self._h(), self.http_get)
        rows = []
        for c in j.get("candles", []):
            if not c.get("complete"):
                continue
            start = _ts(c["time"]).astimezone(NY)
            end_date = (start + timedelta(days=1)).date() if start.hour >= 12 else start.date()
            rows.append((pd.Timestamp(end_date), float(c["mid"]["c"])))
        return pd.Series(dict(rows)).sort_index()


class Alpaca:
    def __init__(self, http_get=None):
        self.http_get = http_get

    def _h(self):
        k, s = secret("trading-research-alpaca-key-id"), secret("trading-research-alpaca-secret")
        if not (k and s):
            raise SourceError("Alpaca paper keys not configured")
        return {"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s}

    def latest_quotes(self, symbols=("SPY", "GLD")):
        j = _get(ALPACA_HOST, "/v2/stocks/quotes/latest", {"symbols": ",".join(symbols), "feed": "iex"}, self._h(), self.http_get)
        out = {}
        for s, q in (j.get("quotes") or {}).items():
            bid, ask = float(q.get("bp") or 0), float(q.get("ap") or 0)
            out[s] = {"bid": bid, "ask": ask, "mid": (bid + ask) / 2 if bid and ask else None,
                      "spread": (ask - bid) if bid and ask else None, "time_utc": _ts(q["t"]), "feed": "iex"}
        return out

    def daily(self, symbols=("SPY", "GLD"), days=620, now=None):
        now = now or datetime.now(timezone.utc)
        params = {"symbols": ",".join(symbols), "timeframe": "1Day", "start": (now - timedelta(days=days)).date().isoformat(),
                  "feed": "iex", "adjustment": "raw", "limit": 10000}
        out = {s: {} for s in symbols}
        for _ in range(20):
            j = _get(ALPACA_HOST, "/v2/stocks/bars", params, self._h(), self.http_get)
            for s, bars in (j.get("bars") or {}).items():
                for b in bars:
                    out[s][pd.Timestamp(_ts(b["t"]).astimezone(NY).date())] = float(b["c"])
            if not j.get("next_page_token"):
                break
            params = dict(params, page_token=j["next_page_token"])
        return {s: pd.Series(v).sort_index() for s, v in out.items()}


def _ts(s):
    s = s.replace("Z", "+00:00")
    m = re.match(r"^(.*\.\d{6})\d*(\+00:00)$", s)
    if m:
        s = m.group(1) + m.group(2)
    return datetime.fromisoformat(s)


# ---------------------------------------------------------------- snapshot in the scanner's format

def snapshot(now, oanda=None, alpaca=None, fx_bars=None, gld_bars=None, cfg_intel=None):
    """Observations shaped like live/intel/latest.json, built from OANDA (FX) and Alpaca (GLD) only.
    Freshness uses market_intel's own rules; a failed source gives UNAVAILABLE, never an invented price."""
    import yaml
    from src import PROJECT_ROOT
    cfg_intel = cfg_intel or yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text())["market_intel"]
    fr_fx, fr_ex = cfg_intel["freshness"]["fx_indicative_1m"], cfg_intel["freshness"]["exchange_delayed_1m"]
    obs, status = [], {}
    try:
        px = (oanda or Oanda()).pricing()
        err = None
    except Exception as ex:
        px, err = {}, str(ex)
    for spec, inst in FX.items():
        p = px.get(inst)
        o = {"specialist": spec, "role": "primary", "source": "OANDA v20 practice (pricing endpoint; indicative practice quote)",
             "symbol": inst, "quote_type": "practice bid/ask mid; not an executed fill"}
        if p:
            fr, _, note = MI.freshness_intraday(p["time_utc"], now, fr_fx, "fx")
            o.update(last=p["mid"], bid=p["bid"], ask=p["ask"], spread_pips=p["spread_pips"], source_ts_utc=p["time_utc"].isoformat(),
                     age_s=(now - p["time_utc"]).total_seconds(), freshness=fr, freshness_note=note, session="fx",
                     session_open=K.fx_market_open(now))
        else:
            o.update(last=None, freshness="UNAVAILABLE", error=err, session="fx", session_open=K.fx_market_open(now), age_s=None)
        bars = (fx_bars or {}).get(inst)
        vol = MI.realized_vol(bars, 20, 21) if bars is not None and len(bars) else None
        o["realized_vol_20d_annualised"] = vol
        status[spec] = MI.specialist_status(o["freshness"], vol, cfg_intel["specialist_status"])
        obs.append(o)
    try:
        q = (alpaca or Alpaca()).latest_quotes(("GLD",)).get("GLD")
        gerr = None
    except Exception as ex:
        q, gerr = None, str(ex)
    g = {"specialist": "gold", "role": "primary", "source": "Alpaca market data (IEX feed)", "symbol": "GLD",
         "quote_type": "IEX quote mid; GLD trades 09:30-16:00 ET; not spot gold", "session": "nyse",
         "session_open": MI.nyse_open(now)}
    if q and q.get("mid") and MI.nyse_open(now):
        fr, _, note = MI.freshness_intraday(q["time_utc"], now, fr_ex, "nyse")
        g.update(last=q["mid"], bid=q["bid"], ask=q["ask"], source_ts_utc=q["time_utc"].isoformat(),
                 age_s=(now - q["time_utc"]).total_seconds(), freshness=fr, freshness_note=note)
    elif gld_bars is not None and len(gld_bars) and not MI.nyse_open(now):
        # closed market (or a one-sided after-hours IEX quote): the last completed IEX daily close, labelled as such
        d = gld_bars.index[-1].date()
        close_t = datetime.combine(d, datetime.min.time().replace(hour=16), tzinfo=NY)
        g.update(last=float(gld_bars.iloc[-1]), bid=None, ask=None, source_ts_utc=close_t.astimezone(timezone.utc).isoformat(),
                 age_s=(now - close_t).total_seconds(), freshness="CLOSED_LAST_PRICE",
                 freshness_note="NYSE closed: last IEX daily close %s (not a live quote)" % d)
    else:
        g.update(last=None, freshness="UNAVAILABLE", error=gerr or "no two-sided IEX quote", age_s=None)
    gv = MI.realized_vol(gld_bars, 20, 21) if gld_bars is not None and len(gld_bars) else None
    g["realized_vol_20d_annualised"] = gv
    status["gold"] = MI.specialist_status(g["freshness"], gv, cfg_intel["specialist_status"])
    obs.append(g)
    return {"generated_utc": now.isoformat(), "observations": obs, "status": status, "clock": K.snapshot(now),
            "label": "FORWARD SYSTEM SNAPSHOT: OANDA practice (FX) + Alpaca IEX (GLD); indicative; no signal"}
