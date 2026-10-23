"""Watchlist alerts: NYSE month-end calendar, rule equivalence with Study 1's P2, offline end-to-end flow."""
import csv
import importlib.util
import json
import shutil
from datetime import date

import numpy as np
import pandas as pd

from src import PROJECT_ROOT
from src import strategies as S

spec = importlib.util.spec_from_file_location("wl", PROJECT_ROOT / "tools" / "watchlist_signals.py")
WL = importlib.util.module_from_spec(spec)
spec.loader.exec_module(WL)


def test_nyse_month_end_calendar():
    assert WL.is_month_end_trading_day(date(2026, 10, 30))          # Friday
    assert not WL.is_month_end_trading_day(date(2026, 10, 29))
    assert WL.is_month_end_trading_day(date(2027, 5, 28))           # Memorial Day is Monday 2027-05-31
    assert not WL.is_month_end_trading_day(date(2027, 5, 31))
    assert WL.easter(2029) == date(2029, 4, 1)
    assert WL.is_month_end_trading_day(date(2029, 3, 29))           # Good Friday 2029-03-30
    assert WL.is_month_end_trading_day(date(2027, 12, 31))          # Jan 1 2028 is Saturday: NYSE open Dec 31


def _prices(n=700, seed=3, tickers=("GLD", "SPY", "QQQ", "TLT", "VTI", "IEF", "DBC", "UGL", "UPRO", "TQQQ", "TMF")):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2023-01-02", periods=n)
    c = pd.DataFrame({t: 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n))) for t in tickers}, index=idx)
    o = c.shift(1).fillna(c.iloc[0]) * (1 + rng.normal(0, 0.002, c.shape))
    return pd.concat({"Close": c, "Open": o}, axis=1)


def test_rule_matches_study1_p2():
    px = _prices()
    c = px["Close"][["GLD", "SPY", "QQQ", "TLT"]]
    w_ref, me = S.multi_trend_weights(c, 6)
    for d in c.index[me.values][-6:]:
        w, _, _ = WL.p2_targets(px["Close"], 6, d.date(), {"GLD": "UGL", "SPY": "UPRO", "QQQ": "TQQQ", "TLT": "TMF"})
        assert [w[x] for x in ("UGL", "UPRO", "TQQQ", "TMF")] == list(w_ref.loc[d].to_numpy())


def test_end_to_end_offline(monkeypatch, capsys):
    px = _prices()
    monkeypatch.setattr(WL, "download", lambda tickers, adjusted: px)
    live = PROJECT_ROOT / "tmp" / "test_live"
    shutil.rmtree(live, ignore_errors=True)
    mes = [d.date() for d in px.index if WL.is_month_end_trading_day(d.date())]
    WL.main(live, mes[-4])                                          # first run: initial state
    out = capsys.readouterr().out
    assert out.count("INITIAL STATE") == 2 and "never tested" in out
    for d in mes[-3:-1]:                                            # later month-ends, then the day after
        WL.main(live, d)
        nxt = px.index[px.index > pd.Timestamp(d)][0].date()
        WL.main(live, nxt)
    rows = list(csv.DictReader(open(live / "paper_log.csv")))
    assert all(r["label"] == "NOT VALIDATED, FAILED TESTING" for r in rows)
    assert all(r["fill_date"] for r in rows if r["signal_date"] < str(mes[-2]))
    st = json.loads((live / "state.json").read_text())
    assert st["last_month_end"] == str(mes[-2])
    out = capsys.readouterr().out
    assert all("Signal only. Not financial advice." in l for l in out.splitlines() if l.startswith("NOTIFY:"))
    assert any((live / "reports").glob("*.md"))
    shutil.rmtree(live)
