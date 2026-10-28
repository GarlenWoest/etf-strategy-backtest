"""Current-market intelligence (Phase B): READ-ONLY snapshot and accuracy check. Plain Python, no LLM calls, no orders.

Isolation (config market_intel.isolation): writes only live/intel/ (git-ignored) and, for `verify`, an aggregate-only
report in reports/market_intel/ (differences and counts, never vendor quotes). Nothing here enters data/,
research_log.csv or any study. Network: Yahoo via yfinance (unofficial client; indicative prices), the ECB reference
rates XML and FRED's public CSV download. Each command makes about a dozen requests; run it a few times a day at most.

Commands:
  snapshot   fetch, timestamp and grade the latest observation for USD/JPY, GBP/USD and gold; append new observations
             to live/intel/observations.jsonl (idempotent: a repeated observation is not written twice); write
             live/intel/latest.json and live/intel/latest.md; print the Markdown
  verify     time-aligned accuracy check of Yahoo 1-minute prices (last 7 days) against the ECB reference rates
             (~14:10 CET) and the Fed H.10 noon buying rates (12:00 New York); write reports/market_intel/accuracy_<date>.md

Usage: .venv/bin/python tools/market_intel.py snapshot|verify
"""
import hashlib
import io
import json
import re
import sys
import warnings
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import requests

from src import PROJECT_ROOT, load_config
from src import clock as K
from src import market_intel as M

OUT = PROJECT_ROOT / "live" / "intel"
REPORTS = PROJECT_ROOT / "reports" / "market_intel"
ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s&cosd=%s"
UA = {}                      # requests' default User-Agent (FRED stalls on unknown agents; tested 2026-10-28)
CFG = load_config()["market_intel"]


def now_utc():
    return datetime.now(timezone.utc)


def _guard(path):
    p = Path(path).resolve()
    if not (str(p).startswith(str(OUT.resolve())) or str(p).startswith(str(REPORTS.resolve()))):
        raise RuntimeError("market_intel may write only live/intel/ and reports/market_intel/: %s" % p)
    return p


# ---------------------------------------------------------------- sources

def yahoo(symbol, period_1m="1d"):
    """Last price, its timestamp, declared delay, raw bid/ask, 1-minute bars and ~3 months of daily closes."""
    import yfinance as yf
    tk = yf.Ticker(symbol)
    out = {"symbol": symbol, "error": None}
    try:
        i = tk.info
        ts = i.get("regularMarketTime")
        out.update(last=i.get("regularMarketPrice"), bid=i.get("bid"), ask=i.get("ask"),
                   source_ts=datetime.fromtimestamp(ts, timezone.utc) if ts else None,
                   delay_s=60 * int(i.get("exchangeDataDelayedBy") or 0), source_tz=i.get("exchangeTimezoneName"),
                   quote_type=i.get("quoteType"), name=i.get("shortName"))
    except Exception as e:                                         # a failure is reported, never filled in
        out["error"] = "quote: %s" % type(e).__name__
    try:
        h = tk.history(period=period_1m, interval="1m")
        out["bars"] = h["Close"].tz_convert("UTC") if len(h) else None
    except Exception as e:
        out["bars"], out["error"] = None, (out["error"] or "") + " bars: %s" % type(e).__name__
    try:
        d = tk.history(period="3mo", interval="1d")
        out["daily"] = d["Close"] if len(d) else None
    except Exception as e:
        out["daily"], out["error"] = None, (out["error"] or "") + " daily: %s" % type(e).__name__
    return out


def ecb_rates():
    """{date: {currency: rate string}} from the ECB 90-day XML (parsed with a regex; no XML entity expansion)."""
    r = requests.get(ECB_URL, headers=UA, timeout=30)
    r.raise_for_status()
    out = {}
    for block in re.finditer(r'<Cube time="(\d{4}-\d\d-\d\d)">(.*?)</Cube>\s*(?=<Cube time=|</Cube>)', r.text, re.S):
        out[date.fromisoformat(block.group(1))] = dict(re.findall(r'currency="([A-Z]{3})" rate="([0-9.]+)"', block.group(2)))
    return out, r.headers.get("Last-Modified")


def ecb_precision(ecb):
    """Usual published decimals per currency = the most decimals seen anywhere in the file (trailing zeros dropped)."""
    dp = {}
    for rates in ecb.values():
        for c, v in rates.items():
            dp[c] = max(dp.get(c, 0), M.decimals(v))
    return dp


def fred_series(sid, start):
    r = requests.get(FRED_CSV % (sid, start.isoformat()), headers=UA, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s.index = pd.to_datetime(df.iloc[:, 0]).dt.date
    return s.dropna(), r.headers.get("Last-Modified")


# ---------------------------------------------------------------- snapshot

def bidask_check(y, tolerance_pct):
    """Accept bid/ask only if 0 < bid < ask and the last price lies within tolerance of [bid, ask]."""
    b, a, l = y.get("bid"), y.get("ask"), y.get("last")
    if not (b and a and l):
        return "UNAVAILABLE", "missing"
    if b >= a:
        return "REJECTED", "bid >= ask"
    if l < b * (1 - tolerance_pct / 100) or l > a * (1 + tolerance_pct / 100):
        return "REJECTED", "last price outside bid/ask by more than %.2f%%" % tolerance_pct
    return "ACCEPTED (unverified)", "consistent with last price"


def observe(spec, inst, role, now):
    rule = CFG["freshness"][inst["kind"]]
    y = yahoo(inst["symbol"])
    session = inst.get("session", "fx")
    status, age, why = M.freshness_intraday(y.get("source_ts"), now, rule, session, y.get("delay_s", 0)) \
        if y.get("last") is not None else ("UNAVAILABLE", None, y.get("error") or "no price")
    ba, ba_why = bidask_check(y, 0.10)
    daily = y.get("daily")
    vol, d_status, last_bar = None, "UNAVAILABLE", None
    if daily is not None and len(daily):
        tz = daily.index.tz or timezone.utc
        daily = daily[daily.index.date < now.astimezone(tz).date()]       # completed days only (today's bar is partial)
    if daily is not None and len(daily):
        last_bar = pd.Timestamp(daily.index[-1]).date()
        d_status, _ = M.freshness_daily_close(last_bar, now.astimezone(M.NY).date(),
                                              CFG["freshness"]["daily_close"]["max_age_business_days"])
        if d_status == "CURRENT":
            v = CFG["volatility"]
            vol = M.realized_vol(daily.to_numpy(), v["window_days"], v["min_closes"], v["annualisation_days"])
    return {"specialist": spec, "role": role, "source": "yahoo (yfinance, unofficial)", "symbol": inst["symbol"],
            "name": y.get("name"), "quote_type": inst["quote"], "last": y.get("last"),
            "bid": y.get("bid"), "ask": y.get("ask"), "bid_ask_status": ba, "bid_ask_note": ba_why,
            "source_ts_utc": y["source_ts"].isoformat() if y.get("source_ts") else None,
            "retrieved_ts_utc": now.isoformat(timespec="seconds"), "source_tz": y.get("source_tz"),
            "declared_delay_s": y.get("delay_s"), "age_s": None if age is None else round(age),
            "expected_update_s": rule["expected_update_s"], "freshness": status, "freshness_note": why,
            "session": session, "session_open": M.SESSIONS[session](now),
            "realized_vol_20d_annualised": vol, "daily_bars_status": d_status,
            "last_daily_bar": last_bar.isoformat() if last_bar else None, "error": y.get("error")}


def references(now):
    """Latest official reference values (ECB cross, Fed H.10) with dates and freshness."""
    today = now.astimezone(M.NY).date()
    out = {}
    try:
        ecb, lm = ecb_rates()
        d = max(ecb)
        r = ecb[d]
        st, age = M.freshness_reference(d, today, CFG["freshness"]["ecb_reference"]["max_age_calendar_days"])
        dp = ecb_precision(ecb)
        uj, ue = M.ecb_cross(r["JPY"], r["USD"], dp["JPY"], dp["USD"])
        gu, ge = M.ecb_cross(r["USD"], r["GBP"], dp["USD"], dp["GBP"])
        out["ecb"] = {"date": d.isoformat(), "observed_utc": M.ecb_concertation_utc(d).isoformat(), "last_modified": lm,
                      "usdjpy": uj, "usdjpy_rounding_pips": uj * ue / 0.01, "gbpusd": gu, "gbpusd_rounding_pips": gu * ge / 1e-4,
                      "freshness": st, "age_days": age, "use": "information only (ECB); not executable"}
    except Exception as e:
        out["ecb"] = {"freshness": "UNAVAILABLE", "error": type(e).__name__}
    for key, sid, invert in (("h10_usdjpy", "DEXJPUS", False), ("h10_gbpusd", "DEXUSUK", False)):
        try:
            s, lm = fred_series(sid, today - timedelta(days=30))
            d = s.index[-1]
            st, age = M.freshness_reference(d, today, CFG["freshness"]["fed_h10_weekly"]["max_age_calendar_days"])
            out[key] = {"date": d.isoformat(), "observed_utc": M.h10_noon_utc(d).isoformat(), "value": float(s.iloc[-1]),
                        "last_modified": lm, "freshness": st, "age_days": age,
                        "use": "noon buying rate in New York, certified for customs purposes (Fed H.10)"}
        except Exception as e:
            out[key] = {"freshness": "UNAVAILABLE", "error": type(e).__name__}
    return out


def key(o):
    return hashlib.sha256(("%s|%s|%s|%s" % (o["source"], o["symbol"], o["source_ts_utc"], o["last"])).encode()).hexdigest()[:20]


def snapshot():
    now = now_utc()
    insts = CFG["instruments"]
    obs = []
    for spec in ("usdjpy", "gbpusd", "gold"):
        obs.append(observe(spec, insts[spec]["primary"], "primary", now))
        for c in insts[spec].get("context", []):
            obs.append(observe(spec, c, "context (not the reference instrument)", now))
    refs = references(now)
    _guard(OUT).mkdir(parents=True, exist_ok=True)
    log = _guard(OUT / "observations.jsonl")
    seen = set()
    if log.exists():
        seen = {json.loads(l).get("key") for l in log.read_text().splitlines() if l.strip()}
    new = 0
    with open(log, "a") as fh:
        for o in obs:
            o["key"] = key(o)
            if o["key"] not in seen and o["last"] is not None:
                fh.write(json.dumps(o, default=str) + "\n")
                new += 1
    words = CFG["specialist_status"]
    status = {s: M.specialist_status(next(o for o in obs if o["specialist"] == s and o["role"] == "primary")["freshness"],
                                     next(o for o in obs if o["specialist"] == s and o["role"] == "primary")["realized_vol_20d_annualised"],
                                     words) for s in ("usdjpy", "gbpusd", "gold")}
    snap = {"generated_utc": now.isoformat(timespec="seconds"), "clock": K.snapshot(now), "status": status,
            "observations": obs, "references": refs, "new_observations_written": new,
            "label": "READ-ONLY MONITORING; indicative data; not research; no signal"}
    _guard(OUT / "latest.json").write_text(json.dumps(snap, indent=1, default=str))
    md = render(snap)
    _guard(OUT / "latest.md").write_text(md)
    print(md)


def render(s):
    c = s["clock"]
    L = ["# Market data snapshot (read-only; not a signal)\n",
         "Generated %s. New York %s. FX market %s. Active sessions: %s.\n" % (
             c["utc"], c["New York"], "open" if c["fx_open"] else "closed", ", ".join(c["active_sessions"]) or "none"),
         "| Market | Status | Instrument (role) | Last | Source time (UTC) | Age | Freshness | Bid/ask | 20-day realised vol |",
         "|---|---|---|---|---|---|---|---|---|"]
    for o in s["observations"]:
        L.append("| %s | %s | %s (%s) | %s | %s | %s | %s | %s | %s |" % (
            o["specialist"], s["status"][o["specialist"]] if o["role"] == "primary" else "", o["symbol"], o["role"],
            "%g" % o["last"] if o["last"] is not None else "—", (o["source_ts_utc"] or "—")[:19].replace("T", " "),
            "%d s" % o["age_s"] if o["age_s"] is not None else "—", "%s (%s)" % (o["freshness"], o["freshness_note"]),
            o["bid_ask_status"], "%.1f%%" % (100 * o["realized_vol_20d_annualised"]) if o["realized_vol_20d_annualised"] else
            "not computed (%s)" % o["daily_bars_status"]))
    r = s["references"]
    L += ["\n**Official references (not current prices; for checking only):**"]
    e = r.get("ecb", {})
    L.append("- ECB %s (concertation ~14:10 CET = %s UTC): USD/JPY %.3f (± %.1f pips rounding), GBP/USD %.5f (± %.1f pips); %s, %s days old." % (
        e.get("date"), (e.get("observed_utc") or "")[11:16], e.get("usdjpy", float("nan")), e.get("usdjpy_rounding_pips", float("nan")),
        e.get("gbpusd", float("nan")), e.get("gbpusd_rounding_pips", float("nan")), e.get("freshness"), e.get("age_days")) if "date" in e
             else "- ECB: UNAVAILABLE (%s)." % e.get("error"))
    for k, lab in (("h10_usdjpy", "USD/JPY"), ("h10_gbpusd", "GBP/USD")):
        h = r.get(k, {})
        L.append("- Fed H.10 %s %s (noon New York): %s; %s, %s days old (published weekly)." % (
            lab, h.get("date"), h.get("value"), h.get("freshness"), h.get("age_days")) if "date" in h else
                 "- Fed H.10 %s: UNAVAILABLE (%s)." % (lab, h.get("error")))
    L += ["\n**What the freshness words mean:** LIVE / DELAYED describe the age of the source's own timestamp. They do not "
          "prove the source is close to the real market: Yahoo's latency is not measured (no executable reference). "
          "Realised volatility is a quantitative estimate from Yahoo daily closes.",
          "\n**Not available:** executable bid/ask for FX (needs a broker or paid feed: decision pending); XAU/USD spot "
          "(no licensed free source). Yahoo prices are indicative and come from an unofficial client.",
          "\nObservations written this run: %d (duplicates skipped)." % s["new_observations_written"]]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- accuracy check

def verify():
    now = now_utc()
    today = now.astimezone(M.NY).date()
    ecb, ecb_lm = ecb_rates()
    rows, cover = [], {}
    for spec, sym, pip, ecb_pair, fred_id in (("usdjpy", "JPY=X", 0.01, ("JPY", "USD"), "DEXJPUS"),
                                              ("gbpusd", "GBPUSD=X", 1e-4, ("USD", "GBP"), "DEXUSUK")):
        y = yahoo(sym, period_1m="7d")
        bars = y.get("bars")
        if bars is None or not len(bars):
            cover[spec] = {"error": y.get("error") or "no 1-minute bars"}
            continue
        first, last = bars.index.min(), bars.index.max()
        mins = pd.date_range(first.floor("min"), last.floor("min"), freq="1min", tz="UTC")
        open_mins = [m for m in mins if K.fx_market_open(m.to_pydatetime())]
        have = set(bars.index.floor("min"))
        missing = sum(1 for m in open_mins if m not in have)
        r = np.log(bars).diff().dropna()
        mad = (r - r.median()).abs().median() * 1.4826
        cover[spec] = {"first": first, "last": last, "fx_open_minutes": len(open_mins), "missing": missing,
                       "outliers_10sigma": int((r.abs() > 10 * mad).sum()) if mad > 0 else None}
        for d, rates in sorted(ecb.items()):
            ref_ts = M.ecb_concertation_utc(d)
            if not (first <= pd.Timestamp(ref_ts) <= last + pd.Timedelta(minutes=1)):
                continue
            dp = ecb_precision(ecb)
            ref, rnd = M.ecb_cross(rates[ecb_pair[0]], rates[ecb_pair[1]], dp[ecb_pair[0]], dp[ecb_pair[1]])
            v, end = M.value_at(bars, ref_ts)
            rows.append({"market": spec, "reference": "ECB ~14:10 CET", "date": d, "ok": v is not None,
                         "rounding_pips": ref * rnd / pip, "lag_s": None if end is None else (ref_ts - end).total_seconds(),
                         **({} if v is None else M.compare(v, ref, pip))})
        s, fred_lm = fred_series(fred_id, (first - pd.Timedelta(days=3)).date())
        for d, ref in s.items():
            ref_ts = M.h10_noon_utc(d)
            if not (first <= pd.Timestamp(ref_ts) <= last + pd.Timedelta(minutes=1)):
                continue
            v, end = M.value_at(bars, ref_ts)
            rows.append({"market": spec, "reference": "Fed H.10 noon NY", "date": d, "ok": v is not None,
                         "rounding_pips": (0.005 if spec == "usdjpy" else 0.00005) / pip,
                         "lag_s": None if end is None else (ref_ts - end).total_seconds(),
                         **({} if v is None else M.compare(float(v), float(ref), pip))})
    df = pd.DataFrame(rows)
    vol_rows = []                                   # volatility estimate vs the same estimate from ECB daily fixes
    v = CFG["volatility"]
    for spec, sym, num, den in (("usdjpy", "JPY=X", "JPY", "USD"), ("gbpusd", "GBPUSD=X", "USD", "GBP")):
        ds = sorted(ecb)
        e = pd.Series([float(ecb[x][num]) / float(ecb[x][den]) for x in ds], index=ds)
        y = yahoo(sym).get("daily")
        if y is not None and len(y):
            y = y[y.index.date < now.astimezone(y.index.tz or timezone.utc).date()]
        vol_rows.append((spec, M.realized_vol(e.to_numpy(), v["window_days"], v["min_closes"], v["annualisation_days"]),
                         None if y is None else M.realized_vol(y.to_numpy(), v["window_days"], v["min_closes"], v["annualisation_days"])))
    L = ["# Current-market accuracy check (Phase B), %s\n" % today,
         "_Generated %s. Yahoo 1-minute prices (unofficial client, indicative) compared with official references at the "
         "references' documented times. Differences and counts only; no vendor quotes. Not executable prices on either "
         "side._\n" % now.isoformat(timespec="seconds"),
         "| Market | Reference | Days compared / possible | Median abs diff (pips) | Max abs diff (pips) | Median diff (bp) | "
         "Reference rounding (pips) | Price-time gap (s) |", "|---|---|---|---|---|---|---|---|"]
    for (mk, ref), g in (df.groupby(["market", "reference"]) if len(df) else []):
        ok = g[g["ok"]]
        L.append("| %s | %s | %d / %d | %s | %s | %s | ± %.1f | %s |" % (
            mk, ref, len(ok), len(g), "%.2f" % ok["pips"].abs().median() if len(ok) else "—",
            "%.2f" % ok["pips"].abs().max() if len(ok) else "—", "%+.2f" % ok["bp"].median() if len(ok) else "—",
            g["rounding_pips"].max(), "%.0f–%.0f" % (ok["lag_s"].min(), ok["lag_s"].max()) if len(ok) else "—"))
    L += ["\n| Market | 1-minute bars covered (UTC) | FX-open minutes | Minutes without a bar | 1-min moves > 10 robust σ |",
          "|---|---|---|---|---|"]
    for mk, c in cover.items():
        if "error" in c:
            L.append("| %s | UNAVAILABLE (%s) | — | — | — |" % (mk, c["error"]))
            continue
        L.append("| %s | %s to %s | %d | %d (%.2f%%) | %s |" % (
            mk, c["first"].strftime("%m-%d %H:%M"), c["last"].strftime("%m-%d %H:%M"), c["fx_open_minutes"], c["missing"],
            100 * c["missing"] / max(c["fx_open_minutes"], 1), c["outliers_10sigma"]))
    L += ["\n| Market | 20-day realised vol, ECB daily fixes (~14:10 CET) | Same, Yahoo completed daily bars |", "|---|---|---|"]
    for spec, ve, vy in vol_rows:
        L.append("| %s | %s | %s |" % (spec, "%.1f%%" % (100 * ve) if ve else "—", "%.1f%%" % (100 * vy) if vy else "—"))
    if len(df):
        L += ["\n## Each comparison\n", "| Market | Reference | Date | Diff (pips) | Diff (bp) |", "|---|---|---|---|---|"]
        for _, r in df.sort_values(["market", "reference", "date"]).iterrows():
            L.append("| %s | %s | %s | %s | %s |" % (r["market"], r["reference"], r["date"],
                                                   "%+.2f" % r["pips"] if r["ok"] else "no bar within 2 min",
                                                   "%+.2f" % r["bp"] if r["ok"] else "—"))
    L += ["\n## What this does and does not show\n",
          "- It measures agreement between Yahoo's indicative price and two official references at documented times, "
          "over the few days Yahoo keeps 1-minute history (about 7).",
          "- It cannot verify executable prices, bid/ask spreads (Yahoo's FX bid/ask fields are rejected) or gold: GLD and "
          "COMEX futures have no independent licensed reference here, and XAU/USD spot isn't available.",
          "- ECB times are approximate ('normally around 14:10 CET'); H.10 rates are buying rates, not mid-market rates; the "
          "rounding column bounds the error from published decimals only.",
          "- Sources: ECB eurofxref-hist-90d.xml (Last-Modified %s); FRED DEXJPUS/DEXUSUK (Fed H.10)." % ecb_lm]
    _guard(REPORTS).mkdir(parents=True, exist_ok=True)
    out = _guard(REPORTS / ("accuracy_%s.md" % today))
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "snapshot":
        snapshot()
    elif cmd == "verify":
        verify()
    else:
        sys.exit(__doc__)
