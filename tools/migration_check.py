"""Phase G source check for the approved Yahoo -> Alpaca migration of the older monitoring workflows (paper books,
watchlist). Read-only: Alpaca IEX bars through the allow-listed GET client; Yahoo prices are NOT downloaded, the
comparison uses the Yahoo prices the books actually used (paper/replay/prices_as_used_2026-10-29.pkl and
paper/inputs/<date>.json). Writes the detail (with prices) only under live/ (private); prints aggregates only.

PASS CRITERIA (fixed 2026-10-31 before any comparison was run):
  S1 coverage   every instrument has an Alpaca IEX daily bar on every NYSE trading day 2026-10-26..30
  S2 opens      |Alpaca IEX open / Yahoo open - 1| <= 0.10% for every instrument-day (paper fills use the open)
  S3 closes     |Alpaca IEX close / Yahoo close - 1| <= 0.10% for every instrument-day (valuation uses the close)
  S4 signals    watchlist targets from Alpaca month-end ADJUSTED closes equal the recorded targets for 2026-09-30 and
                2026-10-30
The migration proceeds only if S1-S4 all pass; otherwise the books stay on Yahoo and the result is reported.

Usage: .venv/bin/python -I tools/migration_check.py [--feed iex|sip] [--paper-dir DIR] [--live-dir DIR]
(2026-10-31: IEX failed S2/S3 on thin leveraged ETFs; the consolidated SIP feed is checked with the same criteria.)
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

TOL = 0.0010
DAYS = ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"]
TARGETS = {"2026-09-30": {"V122": {"VTI": 0.25, "IEF": 0.0, "DBC": 0.25, "GLD": 0.0},
                          "V074": {"UGL": 0.0, "UPRO": 0.25, "TQQQ": 0.25, "TMF": 0.0}}}   # from the private backup 8d11673


def yahoo_used(paper):
    fr = pd.read_pickle(paper / "replay" / "prices_as_used_2026-10-29.pkl")
    o, c = fr["Open"], fr["Close"]
    rows = {}
    for d in DAYS[:4]:
        ts = pd.Timestamp(d)
        rows[d] = {"open": o.loc[ts].to_dict(), "close": c.loc[ts].to_dict()}
    for f in sorted((paper / "inputs").glob("*.json")):
        j = json.loads(f.read_text())
        rows[j["date"]] = {"open": j["open"], "close": j["close"]}
    return rows


def main(a):
    from src.live_usdjpy import sources as SR
    import watchlist_signals as WS
    paper = Path(a[a.index("--paper-dir") + 1]) if "--paper-dir" in a else ROOT / "paper"
    live = Path(a[a.index("--live-dir") + 1]) if "--live-dir" in a else ROOT / "live"
    targets = dict(TARGETS)
    st = json.loads((live / "state.json").read_text())
    targets[st["last_month_end"]] = st["targets"]
    y = yahoo_used(paper)
    instr = sorted({k for d in y.values() for k in d["open"]} - {"^IRX"})
    al = SR.Alpaca()
    feed = a[a.index("--feed") + 1] if "--feed" in a else "iex"
    raw = SR.daily_ohlc(al, instr, "2026-10-20", "2026-10-30T23:00:00Z", adjustment="raw", feed=feed)
    detail, worst = [], {"open": (0, None), "close": (0, None)}
    missing = []
    for d in DAYS:
        if d not in y:
            continue
        for t in instr:
            bar = raw.get(t)
            if bar is None or pd.Timestamp(d) not in bar.index:
                missing.append("%s %s" % (t, d))
                continue
            for k in ("open", "close"):
                yv = y[d][k].get(t)
                if yv is None or pd.isna(yv):
                    continue
                rel = float(bar.loc[pd.Timestamp(d), k]) / float(yv) - 1
                detail.append({"date": d, "instrument": t, "field": k, "yahoo": float(yv),
                               "alpaca_iex": float(bar.loc[pd.Timestamp(d), k]), "rel_diff": rel})
                if abs(rel) > abs(worst[k][0]):
                    worst[k] = (rel, "%s %s" % (t, d))
    # S4: watchlist signals from adjusted month-end closes
    sig_syms = sorted({s for v in WS.STRATS.values() for s in v["map"]})
    adj = SR.daily_ohlc(al, sig_syms, "2024-06-01", "2026-10-30T23:00:00Z", adjustment="all", feed=feed)
    close = pd.DataFrame({s: adj[s]["close"] for s in sig_syms})
    s4 = {}
    for me, tg in targets.items():
        got = {sid: WS.p2_targets(close, v["months"], pd.Timestamp(me).date(), v["map"]) for sid, v in WS.STRATS.items()}
        got = {sid: (g[0] if isinstance(g, tuple) else g) for sid, g in got.items()}
        s4[me] = {"recorded": tg, "alpaca": got, "equal": all(abs(got[sid].get(k, 0) - w) < 1e-9 for sid in tg for k, w in tg[sid].items())}
    by = pd.DataFrame(detail)
    res = {"S1_coverage": {"pass": not missing, "missing": missing},
           "S2_opens": {"pass": bool((by[by.field == "open"].rel_diff.abs() <= TOL).all()), "worst": worst["open"],
                        "n": int((by.field == "open").sum()),
                        "over_tolerance": int((by[by.field == "open"].rel_diff.abs() > TOL).sum())},
           "S3_closes": {"pass": bool((by[by.field == "close"].rel_diff.abs() <= TOL).all()), "worst": worst["close"],
                         "n": int((by.field == "close").sum()),
                         "over_tolerance": int((by[by.field == "close"].rel_diff.abs() > TOL).sum())},
           "S4_signals": {"pass": all(v["equal"] for v in s4.values()), "detail": s4}}
    res["PASS"] = all(v["pass"] for k, v in res.items() if k.startswith("S"))
    out = live / "migration_check" / feed
    out.mkdir(parents=True, exist_ok=True)
    by.to_csv(out / "price_comparison.csv", index=False)                      # private: contains prices
    (out / "result.json").write_text(json.dumps(res, indent=1, default=str))
    per = by.assign(abs_rel=by.rel_diff.abs()).groupby(["instrument", "field"]).abs_rel.max().unstack()
    print("PER-INSTRUMENT MAX |relative difference| (%):")
    print((per * 100).round(3).to_string())
    for k in ("S1_coverage", "S2_opens", "S3_closes", "S4_signals"):
        v = res[k]
        print("%s: %s %s" % (k, "PASS" if v["pass"] else "FAIL", {x: y_ for x, y_ in v.items() if x not in ("pass", "detail")}))
    print("S4 detail:", {me: ("equal" if v["equal"] else "DIFFER: alpaca %s" % v["alpaca"]) for me, v in s4.items()})
    print("MIGRATION CHECK (feed %s) %s" % (feed, "PASS" if res["PASS"] else "FAIL"))


if __name__ == "__main__":
    main(sys.argv)
