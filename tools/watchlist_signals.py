"""Watchlist alerts for two KILLED strategies (NOT VALIDATED, FAILED TESTING). Signals only: no orders, no broker, ever.

User decisions 2026-10-23:
  - V122 = Study 3 P2 multi-asset trend, 12 months, applied to ETF stand-ins VTI / IEF / DBC / GLD (approved; the rule was
    tested on indexes, not on these ETFs' own histories). 1/4 in each ETF whose month-end adjusted close is above the mean
    of its last 12 month-end closes (current included); the rest in cash.
  - V074 = Study 1 P2 multi-asset trend, 6 months, leveraged: signals from GLD / SPY / QQQ / TLT month-end adjusted
    closes vs the mean of the last 6 month-end closes; 25% in UGL / UPRO / TQQQ / TMF respectively; the rest in cash.
  - Exempt from hard rule 2 (holdout) for live/ ONLY. This script reads current market data, writes ONLY inside the live
    directory, imports nothing from src/, and nothing it produces may enter data/, research_log.csv or any study.
Both rules only change at a month-end close (last NYSE trading day of a month). A run on any other day fills in
pending paper prices and stays silent. Lines printed with the prefix "NOTIFY:" are for the scheduled task to send.

Files (all under live/):
  state.json             last processed month-end and current target weights per strategy
  paper_log.csv          one row per signal change (and the initial state): signal close, then the next day's open
  reports/YYYY-MM.md     monthly comparison of paper fills with the rule's close-to-close return

Usage: .venv/bin/python -I tools/watchlist_signals.py [--live-dir DIR] [--today YYYY-MM-DD]   (the options exist for tests)
"""
import csv
import json
import sys
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
LABEL = "NOT VALIDATED, FAILED TESTING"
FOOT = "Signal only. Not financial advice."
ET = ZoneInfo("America/New_York")
STRATS = {
    "V122": {"name": "P2 trend 12-month", "months": 12, "map": {"VTI": "VTI", "IEF": "IEF", "DBC": "DBC", "GLD": "GLD"},
             "worst": "historical worst drop -22% (1927-2018 index backtest, monthly)",
             "bt_month": {"mean": 0.0067, "std": 0.0194, "worst": -0.1304, "source": "Study 3, 1927-2018, indexes"},
             "fill_convention": "backtest traded at the month-end close; paper fills at the next open"},
    "V074": {"name": "P2 trend 6-month leveraged", "months": 6, "map": {"GLD": "UGL", "SPY": "UPRO", "QQQ": "TQQQ", "TLT": "TMF"},
             "worst": "historical worst drop -35% (2006-2023 backtest; pre-2009 leverage synthetic)",
             "bt_month": {"mean": 0.0147, "std": 0.0529, "worst": -0.1276, "source": "Study 1 in-sample, 2006-2018"},
             "fill_convention": "backtest filled at the next open, as the paper log does"},
}
LOG_COLS = ["logged_at_et", "signal_date", "strategy", "label", "action", "instrument", "old_weight", "new_weight",
            "reason", "signal_close", "fill_date", "fill_open_quoted", "fill_open_adjusted", "late", "note"]


# ---------------------------------------------------------------- NYSE calendar (full-day closures)

def easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mo = (h + l - 7 * m + 114) // 31
    return date(y, mo, (h + l - 7 * m + 114) % 31 + 1)


def nth_weekday(y, mo, wd, n):
    d = date(y, mo, 1)
    d += timedelta(days=(wd - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def last_weekday(y, mo, wd):
    d = date(y, mo + 1, 1) - timedelta(days=1) if mo < 12 else date(y, 12, 31)
    return d - timedelta(days=(d.weekday() - wd) % 7)


def observed(d):
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d


def nyse_holidays(y):
    h = {nth_weekday(y, 1, 0, 3), nth_weekday(y, 2, 0, 3), easter(y) - timedelta(days=2), last_weekday(y, 5, 0),
         observed(date(y, 7, 4)), nth_weekday(y, 9, 0, 1), nth_weekday(y, 11, 3, 4), observed(date(y, 12, 25))}
    if y >= 2022:
        h.add(observed(date(y, 6, 19)))
    nyd = date(y, 1, 1)
    if nyd.weekday() != 5:                      # NYSE does not close on Friday Dec 31 for a Saturday New Year
        h.add(observed(nyd))
    return h


def is_trading_day(d):
    return d.weekday() < 5 and d not in nyse_holidays(d.year)


def is_month_end_trading_day(d):
    if not is_trading_day(d):
        return False
    n = d + timedelta(days=1)
    while not is_trading_day(n):
        n += timedelta(days=1)
    return n.month != d.month


# ---------------------------------------------------------------- data and the P2 rule

def download(tickers, adjusted):
    import yfinance as yf
    df = yf.download(tickers, period="3y", auto_adjust=adjusted, progress=False, threads=False)
    if df is None or df.empty:
        raise RuntimeError("empty download")
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df


def month_end_closes(close, upto):
    """Month-end closes up to and including `upto` (a month-end trading day)."""
    c = close.loc[:pd.Timestamp(upto)]
    me = c.groupby(c.index.to_period("M")).tail(1)
    return me


def p2_targets(close, months, upto, mapping):
    """P2: slice in each signal ETF whose month-end close is above the mean of its last `months` month-end closes."""
    me = month_end_closes(close[list(mapping)], upto)
    avg = me.rolling(months, min_periods=months).mean()
    last, a = me.iloc[-1], avg.iloc[-1]
    if pd.Timestamp(me.index[-1]) != pd.Timestamp(upto) or a.isna().any():
        raise RuntimeError("incomplete history for %s" % ",".join(mapping))
    k = len(mapping)
    w = {mapping[s]: (1.0 / k if last[s] > a[s] else 0.0) for s in mapping}
    why = {mapping[s]: "%s month-end close %.2f %s its %d-month average %.2f" % (
        s, last[s], "above" if last[s] > a[s] else "below", months, a[s]) for s in mapping}
    closes = {mapping[s]: float(last[s]) for s in mapping}
    return w, why, closes


# ---------------------------------------------------------------- main

def main(live, today):
    live.mkdir(parents=True, exist_ok=True)
    (live / "reports").mkdir(exist_ok=True)
    state_p, log_p = live / "state.json", live / "paper_log.csv"
    state = json.loads(state_p.read_text()) if state_p.exists() else None
    now = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
    sig = sorted({s for v in STRATS.values() for s in v["map"]})
    held = sorted({t for v in STRATS.values() for t in v["map"].values()})
    try:
        adj = download(sorted(set(sig) | set(held)), True)
        raw = download(held, False)
    except Exception as e:
        print("NOTIFY: [WATCHLIST] data download failed (%s); no signals checked today. %s" % (str(e)[:80], FOOT))
        return
    adj = adj.loc[:pd.Timestamp(today)]
    raw = raw.loc[:pd.Timestamp(today)]
    last_bar = adj.index[-1].date()
    rows = list(csv.DictReader(open(log_p))) if log_p.exists() else []

    # 1. fill pending paper prices with the open of the first trading day after the signal date
    for r in rows:
        if not r["fill_date"]:
            after = adj.index[adj.index > pd.Timestamp(r["signal_date"])]
            if len(after):
                d = after[0]
                r["fill_date"] = str(d.date())
                r["fill_open_quoted"] = "%.4f" % raw["Open"][r["instrument"]].loc[d]
                r["fill_open_adjusted"] = "%.4f" % adj["Open"][r["instrument"]].loc[d]

    # 2. the latest month-end whose close is available
    if is_month_end_trading_day(today) and last_bar == today:
        me = today
    else:
        past = adj.index[adj.index.to_period("M") < pd.Period(today, "M")]
        me = past[-1].date()                     # last bar of an earlier month = that month's last trading day
        if is_month_end_trading_day(today) and last_bar != today:
            print("Today is a month-end, but today's close is not in the data yet; will process it on the next run (LATE).")
    notes = []
    if state is None or me.isoformat() > state["last_month_end"]:
        late = me != today
        new = {}
        for sid, spec in STRATS.items():
            w, why, cl = p2_targets(adj["Close"], spec["months"], me, spec["map"])
            new[sid] = w
            old = state["targets"][sid] if state else None
            for inst in spec["map"].values():
                o = None if old is None else old.get(inst, 0.0)
                if old is not None and abs(o - w[inst]) < 1e-12:
                    continue
                if old is None:
                    if w[inst] == 0:
                        continue
                    action = "INITIAL-HOLD"
                else:
                    action = "BUY" if w[inst] > o else "SELL"
                rows.append({"logged_at_et": now, "signal_date": me.isoformat(), "strategy": sid, "label": LABEL,
                             "action": action, "instrument": inst, "old_weight": "" if o is None else "%.4f" % o,
                             "new_weight": "%.4f" % w[inst], "reason": why[inst], "signal_close": "%.4f" % cl[inst],
                             "fill_date": "", "fill_open_quoted": "", "fill_open_adjusted": "", "late": str(late),
                             "note": "V122 rule applied to ETF stand-ins VTI/IEF/DBC/GLD (tested on indexes)" if sid == "V122" else ""})
                if old is not None:
                    notes.append("NOTIFY: [WATCHLIST, NOT VALIDATED] %s | %s | %s | %s | %s | %s | %s%s" % (
                        sid, action, inst, me.isoformat(), why[inst], spec["worst"], FOOT, " (LATE)" if late else ""))
            if old is None:
                hold = [i for i in spec["map"].values() if w[i] > 0]
                notes.append("NOTIFY: [WATCHLIST, NOT VALIDATED, FAILED TESTING] %s %s | INITIAL STATE | %s | as of %s | %s | %s"
                             % (sid, spec["name"], ", ".join("%s %.0f%%" % (i, 100 * w[i]) for i in hold) or "all cash",
                                me.isoformat(), spec["worst"], FOOT))
        if state is None:
            notes.append("NOTIFY: [WATCHLIST] Note: V122 was tested on indexes (1927-2018); these alerts apply its rule to "
                         "the ETFs' own histories (VTI/IEF/DBC/GLD), which was never tested. %s" % FOOT)
        state = {"last_month_end": me.isoformat(), "targets": new, "last_report_month": (state or {}).get(
            "last_report_month", pd.Period(me, "M").strftime("%Y-%m")), "created": (state or {}).get("created", now)}
    with open(log_p, "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=LOG_COLS)
        wr.writeheader()
        wr.writerows(rows)

    # 3. monthly report for the latest completed month not yet reported
    prev = (pd.Period(today, "M") - 1).strftime("%Y-%m")
    if prev > state["last_report_month"]:
        rep = monthly_report(prev, adj, rows, state)
        if rep:
            (live / "reports" / ("%s.md" % prev)).write_text(rep)
            notes.append("NOTIFY: [WATCHLIST, NOT VALIDATED] Monthly paper-vs-backtest report for %s: live/reports/%s.md. %s"
                         % (prev, prev, FOOT))
            state["last_report_month"] = prev
    state_p.write_text(json.dumps(state, indent=2))
    for n in notes:
        print(n)
    if not notes:
        print("No signal change (last processed month-end %s; latest bar %s)." % (state["last_month_end"], last_bar))


def monthly_report(month, adj, rows, state):
    """Rule (close-to-close from the prior month-end) vs paper (from the logged next-day open) for one calendar month."""
    per = pd.Period(month, "M")
    c = adj["Close"]
    o = adj["Open"]
    start_me = c.index[c.index.to_period("M") < per]
    end_me = c.index[c.index.to_period("M") == per]
    if not len(start_me) or not len(end_me):
        return None
    d0, d1 = start_me[-1], end_me[-1]
    L = ["# Watchlist paper report: %s\n" % month, "**%s.** Signals only; no orders were placed. %s\n" % (LABEL, FOOT),
         "Rule return: weights set at the %s close, close-to-close to %s. Paper return: the same weights entered at the "
         "next open after %s (adjusted prices; costs not deducted).\n" % (d0.date(), d1.date(), d0.date()),
         "| Strategy | Holdings | Rule return | Paper return | Gap | Cost assumption (one-way x turnover) | Backtest monthly mean / std / worst |",
         "|---|---|---|---|---|---|---|"]
    for sid, spec in STRATS.items():
        w = weights_at(rows, sid, d0.date())
        if w is None:
            L.append("| %s | no logged weights at %s | — | — | — | — | — |" % (sid, d0.date()))
            continue
        nxt = c.index[c.index > d0][0]
        rule = sum(w[i] * (c[i].loc[d1] / c[i].loc[d0] - 1) for i in w)
        paper = sum(w[i] * (c[i].loc[d1] / o[i].loc[nxt] - 1) for i in w)
        lev = sid == "V074"
        turn = sum(abs(float(r["new_weight"]) - float(r["old_weight"] or 0)) for r in rows
                   if r["strategy"] == sid and r["signal_date"] == str(d0.date()) and r["action"] in ("BUY", "SELL"))
        cost = turn * (0.0010 if lev else 0.0007)
        b = spec["bt_month"]
        L.append("| %s %s | %s | %+.2f%% | %+.2f%% | %+.2f pp | %.3f%% | %+.2f%% / %.2f%% / %+.2f%% (%s) |" % (
            sid, spec["name"], ", ".join("%s %.0f%%" % (i, 100 * x) for i, x in w.items() if x > 0) or "cash",
            100 * rule, 100 * paper, 100 * (paper - rule), 100 * cost, 100 * b["mean"], 100 * b["std"], 100 * b["worst"],
            b["source"]))
    L.append("\nNotes: %s. V122 uses ETF stand-ins for the tested indexes. Cash earns nothing in these figures. "
             "One month says nothing about whether a strategy works." % "; ".join(
                 "%s %s" % (s, v["fill_convention"]) for s, v in STRATS.items()))
    return "\n".join(L) + "\n"


def weights_at(rows, sid, d):
    """Target weights in force after the month-end `d`, rebuilt from the paper log."""
    w = None
    for r in sorted((r for r in rows if r["strategy"] == sid and r["signal_date"] <= str(d)), key=lambda r: r["signal_date"]):
        if w is None:
            w = {i: 0.0 for i in STRATS[sid]["map"].values()}
        w[r["instrument"]] = float(r["new_weight"])
    return w


if __name__ == "__main__":
    a = sys.argv
    live = Path(a[a.index("--live-dir") + 1]) if "--live-dir" in a else ROOT / "live"
    if not str(live.resolve()).startswith(str(ROOT.resolve())):
        sys.exit("live dir must be inside the project")
    today = date.fromisoformat(a[a.index("--today") + 1]) if "--today" in a else datetime.now(ET).date()
    main(live, today)
