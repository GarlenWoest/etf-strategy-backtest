"""Study 6 runner on synthetic data only (no real returns are read)."""
import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_study6", ROOT / "tools" / "run_study6.py")
S6 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S6)


def cal(a="1990-06-01", b="2023-12-29"):
    return pd.bdate_range(a, b)


def frame(dates, x):
    return pd.DataFrame({"date": dates, "Mkt-RF": x, "RF": 0.0001})


def test_turn_days_are_last_day_and_first_three():
    d = cal("1990-06-01", "1990-10-31")
    tl = S6.turns(d)
    t = tl[0]
    assert t["month"] == "1990-07"
    assert [str(d[j].date()) for j in t["tom"]] == ["1990-07-31", "1990-08-01", "1990-08-02", "1990-08-03"]
    comp = [d[j] for j in t["comp"]]
    assert str(comp[0].date()) == "1990-07-05" and str(comp[-1].date()) == "1990-07-30"   # d_4 .. d_{k-1}
    assert not set(t["comp"]) & set(t["tom"])


def test_window_membership():
    d = cal()
    tl = S6.turns(d)
    assert tl[0]["month"] == "1990-07"                      # June 1990 turn: day -1 before 1990-07-02
    assert tl[-1]["month"] == "2023-11"                     # December 2023 turn needs January 2024
    assert len(tl) == 401


def test_placebo_is_shift_of_ten_trading_days():
    d = cal()
    t = S6.turns(d)[5]
    assert t["placebo"] == [t["tom"][0] + 10 + k for k in range(4)]


def test_e_series_detects_planted_effect_and_kills():
    d = cal()
    x = np.zeros(len(d))
    tl = S6.turns(d)
    rng = np.random.default_rng(1)
    x[:] = rng.normal(0, 0.01, len(d))
    for t in tl:
        x[t["tom"]] += 0.004
    res = S6.evaluate(frame(d, x), frame(d, x))
    assert res["primary_us"]["t"] > 3
    assert not res["kills"]["K1_t_le_3"] and not res["kills"]["K3_placebo_ge_tom"]
    assert not res["kills"]["K5_A1_exus_negative"]
    assert res["secondary_i_us_2009_2023"]["first_turn"] == "2009-01"


def test_no_effect_is_killed_and_negative_exus_kills():
    d = cal()
    rng = np.random.default_rng(2)
    x = rng.normal(0, 0.01, len(d))
    y = x.copy()
    for t in S6.turns(d):
        y[t["tom"]] -= 0.003
    res = S6.evaluate(frame(d, x), frame(d, y))
    assert res["kills"]["K1_t_le_3"]
    assert res["kills"]["K5_A1_exus_negative"]
    assert res["PASS"] is False


def test_cost_schedule_and_charges():
    assert S6.one_way_cost(pd.Timestamp("1992-12-31")) == 0.0034
    assert S6.one_way_cost(pd.Timestamp("1993-01-04")) == 0.0011
    assert S6.one_way_cost(pd.Timestamp("2003-01-02")) == 0.0007
    d = cal()
    tl = S6.turns(d)
    r, inm, _ = S6.strategy_daily(np.zeros(len(d)), d, tl, 2)
    n_early = sum(1 for t in tl if d[t["tom"][-1]] <= pd.Timestamp("1992-12-31"))
    assert inm.sum() == 4 * len(tl)
    assert r.sum() == pytest.approx(-2 * sum(S6.one_way_cost(d[t["tom"][0] - 1]) + S6.one_way_cost(d[t["tom"][-1]]) for t in tl))
    assert n_early > 0


def test_newey_west_equals_plain_for_lag0_iid():
    e = np.random.default_rng(3).normal(0.1, 1, 400)
    n = len(e)
    plain_pop = e.mean() / (e.std(ddof=0) / math.sqrt(n))
    assert S6.t_newey_west(e, lag=0) == pytest.approx(plain_pop)


def test_validation_stops_on_2024():
    d = pd.bdate_range("1990-06-01", "2024-01-05")
    _, stop = S6.validate_df(frame(d, 0.0), "x")
    assert "2024+ dates present" in stop


def test_refuses_without_run_flag():
    import subprocess, sys
    p = subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "run_study6.py")], capture_output=True, text=True)
    assert p.returncode != 0 and "refusing" in p.stderr
