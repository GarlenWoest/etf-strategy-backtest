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


def _get(host, path, params, headers, http_get=None, meta=None):
    """The ONLY way this module touches the network: GET to an allow-listed path on a hard-wired host.
    `meta` (optional dict) receives request_utc, retrieved_utc and the server's HTTP Date header (for clock checks)."""
    if host not in ALLOWED or not any(re.match(p, path) for p in ALLOWED[host]):
        raise OrderEndpointBlocked("blocked: %s%s is not an allow-listed read-only endpoint" % (host, path))
    import requests
    get = http_get or requests.get
    t0 = datetime.now(timezone.utc)
    try:
        r = get(host + path + ("?" + urlencode(params) if params else ""), headers=headers, timeout=20)
    except Exception as ex:
        raise SourceError("%s request failed: %s" % (host, type(ex).__name__)) from None
    if meta is not None:
        meta.update(request_utc=t0, retrieved_utc=datetime.now(timezone.utc),
                    server_date=(getattr(r, "headers", None) or {}).get("Date"))
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
        meta = {}
        j = _get(OANDA_HOST, "/v3/accounts/%s/pricing" % acct, {"instruments": ",".join(instruments)}, self._h(),
                 self.http_get, meta=meta)
        out = {}
        for p in j.get("prices", []):
            q = quote_fields(_px(p.get("bids")), _px(p.get("asks")), PIP.get(p["instrument"], 1))
            q.update(time_utc=_ts(p["time"]) if p.get("time") else None, tradeable=p.get("tradeable"), **meta)
            out[p["instrument"]] = q
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
        meta = {}
        j = _get(ALPACA_HOST, "/v2/stocks/quotes/latest", {"symbols": ",".join(symbols), "feed": "iex"}, self._h(),
                 self.http_get, meta=meta)
        out = {}
        for s, q in (j.get("quotes") or {}).items():
            f = quote_fields(float(q.get("bp") or 0) or None, float(q.get("ap") or 0) or None, None)
            f.update(time_utc=_ts(q["t"]) if q.get("t") else None, feed="iex", **meta)
            out[s] = f
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


def _px(levels):
    try:
        return float(levels[0]["price"])
    except (TypeError, IndexError, KeyError, ValueError):
        return None


def quote_fields(bid, ask, pip):
    """bid/ask/mid/spread with explicit problems: missing sides, non-positive prices, crossed or locked quotes."""
    problems = [n for n, v in (("bid", bid), ("ask", ask)) if v is None]
    problems += ["%s not positive" % n for n, v in (("bid", bid), ("ask", ask)) if v is not None and v <= 0]
    ok = not problems
    if ok and bid > ask:
        problems.append("crossed quote (bid > ask)")
    elif ok and bid == ask:
        problems.append("locked quote (bid = ask)")
    valid = ok and bid < ask
    return {"bid": bid, "ask": ask, "mid": (bid + ask) / 2 if valid else None, "spread": round(ask - bid, 8) if valid else None,
            "spread_pips": round((ask - bid) / pip, 3) if valid and pip else None, "quote_problems": problems}


def timing(quote_utc, meta, skew_tolerance_s=2.0):
    """Quote age measured from the moment the response arrived (not from the start of the run), plus clock checks:
    a quote stamped later than its own retrieval means the local clock is behind the venue's by at least that much."""
    ret = meta.get("retrieved_utc")
    out = {"quote_ts_utc": quote_utc.isoformat() if quote_utc else None,
           "request_utc": meta["request_utc"].isoformat() if meta.get("request_utc") else None,
           "retrieved_utc": ret.isoformat() if ret else None, "age_s": None, "clock_note": None}
    if quote_utc and ret:
        age = (ret - quote_utc).total_seconds()
        out["age_s"] = round(age, 3)
        if age < -skew_tolerance_s:
            out["clock_note"] = "CLOCK SKEW: quote stamped %.1f s after it was received (local clock behind)" % -age
    sd = meta.get("server_date")
    if sd and ret:
        try:
            from email.utils import parsedate_to_datetime
            off = (parsedate_to_datetime(sd) - (meta["request_utc"] + (ret - meta["request_utc"]) / 2)).total_seconds()
            out["server_clock_offset_s"] = round(off, 1)            # HTTP Date has 1 s resolution: +/-1 s is noise
        except Exception:
            out["server_clock_offset_s"] = None
    return out


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
            tm = timing(p.get("time_utc"), p)
            o.update(bid=p["bid"], ask=p["ask"], spread=p["spread"], spread_pips=p["spread_pips"], quote_problems=p["quote_problems"],
                     tradeable=p.get("tradeable"), source_ts_utc=tm["quote_ts_utc"], retrieved_utc=tm["retrieved_utc"],
                     request_utc=tm["request_utc"], age_s=tm["age_s"], clock_note=tm["clock_note"],
                     server_clock_offset_s=tm.get("server_clock_offset_s"), session="fx", session_open=K.fx_market_open(now))
            if p["quote_problems"] or not p.get("time_utc"):
                o.update(last=None, freshness="UNAVAILABLE", freshness_note="invalid quote: %s" % (
                    ", ".join(p["quote_problems"]) or "no quote time"))
            else:
                fr, _, note = MI.freshness_intraday(p["time_utc"], p["retrieved_utc"], fr_fx, "fx")
                o.update(last=p["mid"], freshness=fr, freshness_note=note)
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
    if q:
        tm = timing(q.get("time_utc"), q)
        g.update(quote_bid=q["bid"], quote_ask=q["ask"], quote_problems=q["quote_problems"], quote_ts_utc=tm["quote_ts_utc"],
                 retrieved_utc=tm["retrieved_utc"], clock_note=tm["clock_note"])
    if q and q.get("mid") and MI.nyse_open(now):
        fr, _, note = MI.freshness_intraday(q["time_utc"], q["retrieved_utc"], fr_ex, "nyse")
        g.update(last=q["mid"], bid=q["bid"], ask=q["ask"], spread=q["spread"], source_ts_utc=tm["quote_ts_utc"],
                 age_s=tm["age_s"], freshness=fr, freshness_note=note)
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
