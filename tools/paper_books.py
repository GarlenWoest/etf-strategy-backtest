"""PAPER TRADING test. PAPER, FICTIONAL MONEY. No orders, no broker, ever.

User decisions 2026-10-23: four fictional $100 books start at the open of Monday 2026-10-26:
  A    rules: $50 follows V122, $50 follows V074, target weights read from live/state.json (watchlist alerts);
       rebalanced to the targets at the next open after each processed month-end (the P2 rule rebalances monthly)
  B    discretionary: one decision per week, made in the Sunday run and submitted ONLY through `journal`, which checks
       the rules; fills at the next trading day's open; minimum hold 5 trading days; planned exits in the entry's
       machine-readable exit_rule execute automatically once the hold is over
  SPY  benchmark: 100% SPY
  MIX  benchmark: 70% SPY / 30% GLD, rebalanced at the next open after each month-end
Costs as Study 1: 0.07% one-way (unleveraged), 0.10% (leveraged), $0 commission; fractional shares; long only; no margin;
uninvested cash earns the T-bill rate (^IRX / 100 / 252 per trading day, prior day's value); dividends paid in cash on
the ex-date (quoted prices + yfinance dividends, so past fills never change when Yahoo rescales adjusted history).
Exempt from hard rule 2 for paper/ ONLY: writes nothing outside paper/, reads live/state.json, imports nothing from src/;
nothing here may enter data/, research_log.csv or any study.

Commands (all write only inside paper/):
  init --start YYYY-MM-DD        create the books (once)
  update [--today YYYY-MM-DD]    weekday run: fills, dividends, interest, mark to market, auto exits, checkpoints
  status                         Book B positions, cash and exit eligibility (for the Sunday decision)
  journal --json '{...}'         submit Book B's weekly decision (validated; appended with a SHA-256 fingerprint)
  summary                        Markdown table for the Sunday brief
"""
import csv
import hashlib
import json
import sys
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from watchlist_signals import is_month_end_trading_day, is_trading_day  # noqa: E402  (NYSE calendar, same tools/ dir)

ROOT = Path(__file__).resolve().parent.parent
LABEL = "PAPER, FICTIONAL MONEY"
ET = ZoneInfo("America/New_York")
LEVERAGED = {"UGL", "AGQ", "UCO", "UPRO", "TQQQ", "TMF"}
B_UNIVERSE = ["GLD", "SLV", "USO", "SPY", "QQQ", "TLT"] + sorted(LEVERAGED)
A_INSTR = ["VTI", "IEF", "DBC", "GLD", "UGL", "UPRO", "TQQQ", "TMF"]
COST = {"unlev": 0.0007, "lev": 0.0010}
MIN_HOLD = 5
BOOKS = ["A", "B", "SPY", "MIX"]


def cost(t):
    return COST["lev"] if t in LEVERAGED else COST["unlev"]


def next_trading_day(d):
    d += timedelta(days=1)
    while not is_trading_day(d):
        d += timedelta(days=1)
    return d


# ---------------------------------------------------------------- persistence

class Paper:
    def __init__(self, root):
        self.dir = root
        self.state_p = root / "state.json"
        self.journal_md = root / "book_b_journal.md"
        self.hashes = root / "journal_hashes.csv"
        self.values = root / "values.csv"
        self.trades = root / "trades.csv"

    def load(self):
        return json.loads(self.state_p.read_text())

    def save(self, s):
        self.state_p.write_text(json.dumps(s, indent=2))

    def append_csv(self, path, cols, row):
        new = not path.exists()
        with open(path, "a", newline="") as fh:
            if new:
                fh.write("# %s\n" % LABEL)
            w = csv.DictWriter(fh, fieldnames=cols)
            if new:
                w.writeheader()
            w.writerow(row)

    def read_csv(self, path):
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path, comment="#")


def empty_book(cash):
    return {"cash": cash, "shares": {}, "meta": {}}


def init(p, start):
    p.dir.mkdir(parents=True, exist_ok=True)
    (p.dir / "reports").mkdir(exist_ok=True)
    if p.state_p.exists():
        sys.exit("paper books already exist")
    if not is_trading_day(start):
        sys.exit("start must be a trading day")
    s = {"label": LABEL, "start": start.isoformat(), "last_update": None, "books": {
        "A": {"V122": empty_book(50.0), "V074": empty_book(50.0)}, "B": empty_book(100.0),
        "SPY": empty_book(100.0), "MIX": empty_book(100.0)},
        "pending": [{"book": "A", "kind": "rebalance_live", "fill_date": start.isoformat()},
                    {"book": "SPY", "kind": "target", "weights": {"SPY": 1.0}, "fill_date": start.isoformat()},
                    {"book": "MIX", "kind": "target", "weights": {"SPY": 0.7, "GLD": 0.3}, "fill_date": start.isoformat()}],
        "a_applied_month_end": None, "checkpoints": {}, "journal_entries": 0}
    p.save(s)
    p.journal_md.write_text("# Book B journal (%s)\n\nAppend-only. Each entry is written by `tools/paper_books.py journal` "
                            "before its trade and fingerprinted in `journal_hashes.csv`; any later edit is detected.\n" % LABEL)
    print("initialised paper books; start %s" % start)


# ---------------------------------------------------------------- data

def download(tickers, start):
    import yfinance as yf
    df = yf.download(sorted(set(tickers)), start=start, auto_adjust=False, actions=True, progress=False, threads=False)
    if df is None or df.empty:
        raise RuntimeError("empty download")
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df


# ---------------------------------------------------------------- execution

def value_of(book, px):
    return book["cash"] + sum(sh * px[t] for t, sh in book["shares"].items())


def trade_to(book, weights, opens, d, tag, log):
    """Rebalance `book` to target weights (of its value at the open) at the open; sells first, then buys scaled to cash."""
    tickers = set(book["shares"]) | set(weights)
    eq = value_of(book, {t: opens[t] for t in tickers})
    fills = []
    for t in sorted(tickers):
        cur = book["shares"].get(t, 0.0) * opens[t]
        tgt = weights.get(t, 0.0) * eq
        if tgt < cur - 1e-6:
            full = weights.get(t, 0.0) == 0
            q = book["shares"][t] if full else (cur - tgt) / opens[t]
            px = opens[t] * (1 - cost(t))
            book["cash"] += q * px
            book["shares"][t] = 0.0 if full else book["shares"][t] - q
            if book["shares"][t] <= 1e-12:
                book["shares"].pop(t)
                book["meta"].pop(t, None)
            fills.append(("SELL", t, q, px))
    for t in sorted(tickers):
        cur = book["shares"].get(t, 0.0) * opens[t]
        want = weights.get(t, 0.0) * eq - cur
        if want > 1e-6:
            want = min(want, book["cash"])
            if want < 0.01:
                continue
            px = opens[t] * (1 + cost(t))
            q = want / px
            book["cash"] -= want
            book["shares"][t] = book["shares"].get(t, 0.0) + q
            fills.append(("BUY", t, q, px))
    for side, t, q, px in fills:
        log.append({"date": d.isoformat(), "book": tag, "side": side, "instrument": t, "shares": "%.6f" % q,
                    "price_incl_costs": "%.4f" % px, "open": "%.4f" % opens[t], "cost_rate": cost(t)})
    return fills


def live_targets():
    st = json.loads((ROOT / "live" / "state.json").read_text())
    return st["last_month_end"], st["targets"]


def update(p, today):
    s = p.load()
    notes = []
    tamper = verify_journal(p)
    if tamper:
        notes.append("NOTIFY: [PAPER, FICTIONAL MONEY] Book B journal check FAILED: %s" % tamper)
    else:
        notes += record_missed(p, s, datetime.combine(today, datetime.min.time()).replace(hour=16, minute=45, tzinfo=ET)
                               if today != datetime.now(ET).date() else datetime.now(ET))
        p.save(s)
    start = date.fromisoformat(s["start"])
    if today < start:
        print("paper books start %s; nothing to do yet" % start)
        return notes
    need = set(A_INSTR) | set(B_UNIVERSE) | {"SPY", "GLD"}
    df = download(list(need) + ["^IRX"], (start - timedelta(days=10)).isoformat())
    O, C = df["Open"], df["Close"]
    D = df["Dividends"] if "Dividends" in df.columns.get_level_values(0) else None
    irx = C["^IRX"].ffill()
    days = [d.date() for d in C.index if start <= d.date() <= today and is_trading_day(d.date())]
    last = date.fromisoformat(s["last_update"]) if s["last_update"] else None
    trade_log = []
    for d in days:
        if last and d <= last:
            continue
        ts = pd.Timestamp(d)
        if C.loc[ts, ["SPY"]].isna().any():
            notes.append("NOTIFY: [PAPER, FICTIONAL MONEY] no close for %s yet; values not updated" % d)
            break
        prev = C.index[C.index < ts]
        rate = float(irx.loc[prev[-1]]) / 100 / 252 if len(prev) else 0.0
        all_books = [("A:V122", s["books"]["A"]["V122"]), ("A:V074", s["books"]["A"]["V074"]), ("B", s["books"]["B"]),
                     ("SPY", s["books"]["SPY"]), ("MIX", s["books"]["MIX"])]
        for tag, bk in all_books:                                   # interest, then dividends (held at prior close)
            if d > start:
                bk["cash"] *= 1 + rate
            if D is not None:
                for t, sh in bk["shares"].items():
                    dv = D[t].get(ts, 0.0) if t in D.columns else 0.0
                    if dv and not np.isnan(dv):
                        bk["cash"] += sh * dv
        opens = {t: float(O.loc[ts, t]) for t in need if not np.isnan(O.loc[ts, t])}
        day_fills = {}
        for order in [o for o in s["pending"] if o["fill_date"] <= d.isoformat()]:
            s["pending"].remove(order)
            late = order["fill_date"] < d.isoformat()
            if order["kind"] == "rebalance_live":
                me, tg = live_targets()
                for sid in ("V122", "V074"):
                    f = trade_to(s["books"]["A"][sid], tg[sid], opens, d, "A:" + sid, trade_log)
                    day_fills.setdefault("A", []).extend(f)
                s["a_applied_month_end"] = me
            elif order["kind"] == "target":
                f = trade_to(s["books"][order["book"]], order["weights"], opens, d, order["book"], trade_log)
                day_fills.setdefault(order["book"], []).extend(f)
            elif order["kind"] == "b_buy":
                bk = s["books"]["B"]
                eq = value_of(bk, opens)
                w = {t: bk["shares"][t] * opens[t] / eq for t in bk["shares"]}
                w[order["instrument"]] = w.get(order["instrument"], 0.0) + order["size_pct"] / 100.0
                if sum(w.values()) > 1 + 1e-9:
                    notes.append("NOTIFY: [PAPER, FICTIONAL MONEY] Book B order #%d rejected at fill: not enough cash" % order["entry"])
                    continue
                f = trade_to(bk, w, opens, d, "B", trade_log)
                bk["meta"][order["instrument"]] = {"fill_date": d.isoformat(), "entry": order["entry"],
                                                   "exit_rule": order.get("exit_rule", {})}
                day_fills.setdefault("B", []).extend(f)
            elif order["kind"] == "b_sell":
                bk = s["books"]["B"]
                if order["instrument"] in bk["shares"]:
                    eq = value_of(bk, opens)
                    w = {t: bk["shares"][t] * opens[t] / eq for t in bk["shares"] if t != order["instrument"]}
                    f = trade_to(bk, w, opens, d, "B", trade_log)
                    day_fills.setdefault("B", []).extend(f)
            if late:
                notes.append("NOTIFY: [PAPER, FICTIONAL MONEY] order for %s filled late on %s (was due %s)" % (
                    order["book"], d, order["fill_date"]))
        for book, f in day_fills.items():
            if f:
                notes.append("NOTIFY: [PAPER, FICTIONAL MONEY] Book %s trades at the %s open: %s" % (
                    book, d, ", ".join("%s %s @ %.2f" % (sd, t, px) for sd, t, q, px in f)))
        closes = {t: float(C.loc[ts, t]) for t in need if not np.isnan(C.loc[ts, t])}
        vals = {"A": value_of(s["books"]["A"]["V122"], closes) + value_of(s["books"]["A"]["V074"], closes),
                "A_V122": value_of(s["books"]["A"]["V122"], closes), "A_V074": value_of(s["books"]["A"]["V074"], closes),
                "B": value_of(s["books"]["B"], closes), "SPY": value_of(s["books"]["SPY"], closes),
                "MIX": value_of(s["books"]["MIX"], closes)}
        p.append_csv(p.values, ["date"] + list(vals), {"date": d.isoformat(), **{k: "%.4f" % v for k, v in vals.items()}})
        # after the close: new orders for the next trading day
        nxt = next_trading_day(d).isoformat()
        try:
            me, _ = live_targets()
        except Exception:
            me = None
        if me and me <= d.isoformat() and me != s["a_applied_month_end"] and \
                not any(o["kind"] == "rebalance_live" for o in s["pending"]):
            s["pending"].append({"book": "A", "kind": "rebalance_live", "fill_date": nxt})
        if is_month_end_trading_day(d) and d > start:
            s["pending"].append({"book": "MIX", "kind": "target", "weights": {"SPY": 0.7, "GLD": 0.3}, "fill_date": nxt})
        bk = s["books"]["B"]
        for t, m in list(bk["meta"].items()):                       # planned exits, only after the minimum hold
            held = trading_days_between(date.fromisoformat(m["fill_date"]), date.fromisoformat(nxt))
            if held < MIN_HOLD or any(o["kind"] == "b_sell" and o["instrument"] == t for o in s["pending"]):
                continue
            r = m.get("exit_rule", {})
            hit = (r.get("stop_below") and closes[t] < r["stop_below"]) or \
                  (r.get("take_profit_above") and closes[t] > r["take_profit_above"]) or \
                  (r.get("exit_on_or_after") and d.isoformat() >= r["exit_on_or_after"])
            if hit:
                s["pending"].append({"book": "B", "kind": "b_sell", "instrument": t, "fill_date": nxt, "entry": m["entry"],
                                     "reason": "planned exit from journal entry #%d" % m["entry"]})
        s["last_update"] = d.isoformat()
    for row in trade_log:
        p.append_csv(p.trades, list(row), row)
    p.save(s)
    notes += checkpoints(p, s, today)
    return notes


def trading_days_between(a, b):
    """Number of trading days from a (exclusive) to b (inclusive)."""
    n, d = 0, a
    while d < b:
        d = next_trading_day(d)
        n += 1
    return n


# ---------------------------------------------------------------- Book B journal

REQ = ["decision_date", "action", "entry_reason", "wrong_if", "planned_exit"]


def entry_hash(e):
    return hashlib.sha256(json.dumps(e, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read_entries(p):
    txt = p.journal_md.read_text() if p.journal_md.exists() else ""
    out = []
    for block in txt.split("```json\n")[1:]:
        out.append(json.loads(block.split("\n```")[0]))
    return out


def verify_journal(p):
    entries = read_entries(p)
    h = p.read_csv(p.hashes)
    if len(h) != len(entries):
        return "journal has %d entries but %d fingerprints" % (len(entries), len(h))
    for e, (_, r) in zip(entries, h.iterrows()):
        if entry_hash(e) != r["sha256"]:
            return "entry #%s was changed after it was written" % e.get("entry")
    return None


def journal(p, raw, now_et):
    s = p.load()
    if verify_journal(p):
        sys.exit("REJECTED: journal check failed: %s" % verify_journal(p))
    for n in record_missed(p, s, now_et):                    # close out earlier weeks first, so entries stay in order
        print(n)
    p.save(s)
    e = json.loads(raw)
    miss = [k for k in REQ if not str(e.get(k, "")).strip()]
    if miss:
        sys.exit("REJECTED: missing fields %s" % miss)
    dd = date.fromisoformat(e["decision_date"])
    if dd.weekday() != 6:
        sys.exit("REJECTED: decision_date must be the Sunday of the decision week")
    if dd > now_et.date():
        sys.exit("REJECTED: decision date is in the future")
    if now_et.date() > dd + timedelta(days=6):
        sys.exit("REJECTED: the window for the week of %s closed on %s; that week is recorded MISSED"
                 % (dd, dd + timedelta(days=6)))
    if dd < first_decision_sunday(s):
        sys.exit("REJECTED: the first decision week is %s" % first_decision_sunday(s))
    prior = read_entries(p)
    if any(x["decision_date"] == dd.isoformat() for x in prior):
        sys.exit("REJECTED: a decision for this week already exists")
    act = e["action"].upper()
    fill = fill_after(now_et)                       # never earlier than the moment the entry is written
    late = now_et.date() > dd
    if fill < date.fromisoformat(s["start"]):
        fill = date.fromisoformat(s["start"])
    bk = s["books"]["B"]
    if act == "BUY":
        if e.get("instrument") not in B_UNIVERSE:
            sys.exit("REJECTED: instrument must be one of %s" % B_UNIVERSE)
        size = float(e.get("size_pct", 0))
        if not 0 < size <= 100:
            sys.exit("REJECTED: size_pct must be in (0, 100]")
        r = e.get("exit_rule", {})
        if not any(r.get(k) for k in ("stop_below", "take_profit_above", "exit_on_or_after")):
            sys.exit("REJECTED: BUY needs a machine-readable exit_rule (stop_below / take_profit_above / exit_on_or_after)")
        if e["instrument"] in bk["shares"]:
            sys.exit("REJECTED: already holding %s; one position per instrument" % e["instrument"])
    elif act == "SELL":
        t = e.get("instrument")
        if t not in bk["shares"]:
            sys.exit("REJECTED: not holding %s" % t)
        if trading_days_between(date.fromisoformat(bk["meta"][t]["fill_date"]), fill) < MIN_HOLD:
            sys.exit("REJECTED: minimum hold is %d trading days" % MIN_HOLD)
    elif act != "NO_TRADE":
        sys.exit("REJECTED: action must be BUY, SELL or NO_TRADE")
    e = append_entry(p, s, {**e, "action": act, "late": late, "fill_planned": fill.isoformat()}, now_et)
    if act == "BUY":
        s["pending"].append({"book": "B", "kind": "b_buy", "instrument": e["instrument"], "size_pct": float(e["size_pct"]),
                             "exit_rule": e["exit_rule"], "fill_date": fill.isoformat(), "entry": e["entry"]})
    elif act == "SELL":
        s["pending"].append({"book": "B", "kind": "b_sell", "instrument": e["instrument"], "fill_date": fill.isoformat(),
                             "entry": e["entry"]})
    p.save(s)
    print("ACCEPTED entry #%d%s: %s %s, fill at the %s open" % (e["entry"], " (LATE)" if late else "", act,
                                                               e.get("instrument", ""), fill))


def append_entry(p, s, e, now_et):
    """Append one fingerprinted entry (the only way anything is written to the journal)."""
    s["journal_entries"] += 1
    e = {**e, "entry": s["journal_entries"], "written_at_et": now_et.strftime("%Y-%m-%d %H:%M ET"), "label": LABEL}
    tag = " (LATE)" if e.get("late") else ""
    with open(p.journal_md, "a") as fh:
        fh.write("\n## Entry #%d (week of %s): %s %s%s\n\n```json\n%s\n```\n" % (
            e["entry"], e["decision_date"], e["action"], e.get("instrument", ""), tag,
            json.dumps(e, sort_keys=True, ensure_ascii=False, indent=1)))
    p.append_csv(p.hashes, ["entry", "written_at_et", "sha256"], {"entry": e["entry"], "written_at_et": e["written_at_et"],
                                                                   "sha256": entry_hash(e)})
    return e


def first_decision_sunday(s):
    st = date.fromisoformat(s["start"])
    return st - timedelta(days=(st.weekday() + 1) % 7)


def fill_after(now_et):
    """First open at or after the moment of writing: today's open if written before 9:30 ET on a trading day."""
    d = now_et.date()
    if is_trading_day(d) and (now_et.hour, now_et.minute) < (9, 30):
        return d
    return next_trading_day(d)


def record_missed(p, s, now_et):
    """Append a MISSED entry for every decision week whose window (Sunday..Saturday) closed without a decision."""
    done = {x["decision_date"] for x in read_entries(p)}
    notes = []
    d = first_decision_sunday(s)
    while d + timedelta(days=7) <= now_et.date():
        if d.isoformat() not in done:
            append_entry(p, s, {"decision_date": d.isoformat(), "action": "MISSED", "late": False,
                                "entry_reason": "no decision was written during the week's window (%s to %s)"
                                % (d, d + timedelta(days=6)), "wrong_if": "n/a", "planned_exit": "n/a"}, now_et)
            notes.append("NOTIFY: [PAPER, FICTIONAL MONEY] Book B: no decision for the week of %s; recorded MISSED" % d)
        d += timedelta(days=7)
    return notes


def status(p):
    s = p.load()
    bk = s["books"]["B"]
    print("# Book B status (%s)\nstart %s; last update %s; cash $%.2f" % (LABEL, s["start"], s["last_update"], bk["cash"]))
    for t, sh in bk["shares"].items():
        m = bk["meta"][t]
        nxt = next_trading_day(date.today())
        print("- %s: %.4f shares, filled %s (entry #%d), exit_rule %s, may be sold at the %s open: %s" % (
            t, sh, m["fill_date"], m["entry"], m["exit_rule"], nxt,
            trading_days_between(date.fromisoformat(m["fill_date"]), nxt) >= MIN_HOLD))
    print("pending orders: %s" % [o for o in s["pending"] if o["book"] == "B"])
    print("allowed instruments: %s; minimum hold %d trading days; one decision per week" % (B_UNIVERSE, MIN_HOLD))


# ---------------------------------------------------------------- reporting

def table(p):
    v = p.read_csv(p.values)
    if v.empty:
        return "_%s: books start Monday %s; no values yet._" % (LABEL, p.load()["start"])
    rows = [("Book A (rules: V122 + V074)", "A"), ("Book B (discretionary)", "B"), ("Benchmark: SPY", "SPY"),
            ("Benchmark: 70/30 SPY/GLD", "MIX")]
    L = ["**%s** — since %s, %d trading days, through %s\n" % (LABEL, v["date"].iloc[0], len(v), v["date"].iloc[-1]),
         "| Book | Value | Return since start | Max drawdown |", "|---|---|---|---|"]
    for name, c in rows:
        x = v[c].astype(float)
        L.append("| %s | $%.2f | %+.2f%% | %.2f%% |" % (name, x.iloc[-1], 100 * (x.iloc[-1] / 100 - 1),
                                                     100 * float((x / x.cummax().clip(lower=100) - 1).min())))
    return "\n".join(L)


def checkpoints(p, s, today):
    v = p.read_csv(p.values)
    notes = []
    for key, n, title, warn in (("2w", 10, "2-week checkpoint", "2 weeks is statistically meaningless; informational only"),
                                ("3m", 63, "3-month summary", "3 months is still far too short to conclude anything; informational only")):
        if len(v) >= n and key not in s["checkpoints"]:
            tr = p.read_csv(p.trades)
            txt = "# %s: %s\n\n**%s.** **%s.**\n\n%s\n\nTrades so far: %d (see `paper/trades.csv`). Book B journal entries: %d.\n" % (
                LABEL, title, LABEL, warn, table(p), len(tr), s["journal_entries"])
            (p.dir / "reports" / ("checkpoint_%s.md" % key)).write_text(txt)
            s["checkpoints"][key] = today.isoformat()
            p.save(s)
            notes.append("NOTIFY: [PAPER, FICTIONAL MONEY] %s written: paper/reports/checkpoint_%s.md (%s)" % (title, key, warn))
    return notes


if __name__ == "__main__":
    a = sys.argv
    root = Path(a[a.index("--paper-dir") + 1]) if "--paper-dir" in a else ROOT / "paper"
    if not str(root.resolve()).startswith(str(ROOT.resolve())):
        sys.exit("paper dir must be inside the project")
    p = Paper(root)
    cmd = a[1]
    if cmd == "init":
        init(p, date.fromisoformat(a[a.index("--start") + 1]))
    elif cmd == "update":
        today = date.fromisoformat(a[a.index("--today") + 1]) if "--today" in a else datetime.now(ET).date()
        for n in update(p, today):
            print(n)
    elif cmd == "status":
        status(p)
    elif cmd == "journal":
        journal(p, a[a.index("--json") + 1], datetime.now(ET))
    elif cmd == "summary":
        print(table(p))
    else:
        sys.exit(__doc__)
