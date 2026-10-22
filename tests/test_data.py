"""Phase 2 data tests: formulas by hand, validation catches bad data, holdout never loaded."""
import numpy as np
import pandas as pd
import pytest

from src import load_config
from src import data as D

cfg = load_config()
DAYS = pd.bdate_range("2020-01-06", periods=6)


def frame(closes, opens=None, highs=None, lows=None, idx=None):
    idx = idx if idx is not None else DAYS[:len(closes)]
    c = pd.Series(closes, index=idx, dtype=float)
    o = pd.Series(opens if opens is not None else closes, index=idx, dtype=float)
    h = pd.Series(highs, index=idx, dtype=float) if highs is not None else pd.concat([o, c], axis=1).max(axis=1)
    lo = pd.Series(lows, index=idx, dtype=float) if lows is not None else pd.concat([o, c], axis=1).min(axis=1)
    return pd.DataFrame({"Open": o, "High": h, "Low": lo, "Close": c})


# ---------------------------------------------------------------- synthetic formula

def test_synthetic_returns_match_hand_calculation():
    under = pd.Series([100.0, 102.0, 99.0], index=DAYS[:3])
    cash = pd.Series([0.0001, 0.0002, 0.0003], index=DAYS[:3])
    L, er = 3, 0.0095
    r = D.synthetic_returns(under, cash, L, er)
    day1 = 3 * 0.02 - 0.0095 / 252 - 2 * 0.0001          # financing uses the prior day's rate
    day2 = 3 * (99 / 102 - 1) - 0.0095 / 252 - 2 * 0.0002
    assert np.isnan(r.iloc[0])
    assert r.iloc[1] == pytest.approx(day1, abs=1e-15)
    assert r.iloc[2] == pytest.approx(day2, abs=1e-15)


def test_synthetic_ohlc_open_is_leveraged_overnight_move():
    under = frame([100, 102, 99], opens=[100, 101, 103])
    cash = pd.Series(0.0, index=DAYS[:3])
    s = D.synthetic_ohlc(under, cash, 2, 0.0, anchor_close=10.0)
    assert s["Close"].tolist() == pytest.approx([10.0, 10.4, 10.4 * (1 + 2 * (99 / 102 - 1))])
    assert s["Open"].iloc[1] == pytest.approx(10.0 * (1 + 2 * 0.01))
    assert s["Open"].iloc[2] == pytest.approx(10.4 * (1 + 2 * (103 / 102 - 1)))
    assert (s["High"] >= s[["Open", "Close"]].max(axis=1) - 1e-12).all()
    assert (s["Low"] <= s[["Open", "Close"]].min(axis=1) + 1e-12).all()


def test_splice_has_no_jump_and_keeps_real_data():
    syn = frame([1.0, 1.1, 1.21, 1.331, 1.4641])
    real = frame([50.0, 56.0, 57.0], idx=DAYS[2:5])
    j = D.splice(real, syn)
    assert j["source"].tolist() == ["synthetic", "synthetic", "real", "real", "real"]
    assert j.loc[DAYS[2:5], "Close"].tolist() == [50.0, 56.0, 57.0]
    # synthetic returns are preserved and scaled to meet the real close at the seam
    assert j["Close"].iloc[1] / j["Close"].iloc[0] == pytest.approx(1.1)
    assert j["Close"].iloc[2] / j["Close"].iloc[1] == pytest.approx(1.21 / 1.1)


# ---------------------------------------------------------------- cash rate

def test_cash_rate_formula_and_holiday_ffill_only():
    cal = DAYS[:5]
    irx = pd.DataFrame({"Close": [5.04, 5.04, np.nan, 2.52, 2.52, 9.99]},
                       index=list(DAYS[:2]) + [DAYS[2] + pd.Timedelta(hours=1)] + list(DAYS[3:5]) +
                       [pd.Timestamp("2020-01-11")])          # a Saturday print is dropped
    irx = irx.dropna()
    rate, info = D.daily_cash_rate(irx, cal)
    assert rate.iloc[0] == pytest.approx(5.04 / 100 / 252)
    assert rate.iloc[2] == pytest.approx(5.04 / 100 / 252)   # bond holiday: carried forward
    assert info["forward_filled_dates"] == [str(DAYS[2].date())]
    assert list(rate.index) == list(cal)


# ---------------------------------------------------------------- validation

def checks(issues):
    return {i["check"]: i for i in issues}


def test_validation_flags_bad_data():
    df = frame([10, 10, 10, 0, 12], highs=[10, 10, 10, 0, 11], lows=[10, 10, 10, 0, 12])
    df = pd.concat([df, df.iloc[[1]]]).sort_index()                # duplicate date
    cal = DAYS[:6]
    c = checks(D.validate_prices(df, "X", cal, gap_flag=0.10, stale_days=3))
    assert c["duplicate_date"]["count"] == 1
    assert c["non_positive_price"]["dates"] == [str(DAYS[3].date())]
    assert str(DAYS[4].date()) in c["ohlc_inconsistent"]["dates"]  # low above close
    assert c["missing_trading_day"]["dates"] == [str(DAYS[5].date())]
    assert "stale_close_run" in c
    assert "gap_close_to_close" in c


def test_validation_clean_data_has_no_issues():
    df = frame([10, 10.1, 10.05, 10.2], opens=[10, 10.05, 10.1, 10.1])
    assert D.validate_prices(df, "X", DAYS[:4]) == []


# ---------------------------------------------------------------- holdout and clean files

def test_download_end_is_holdout_start_while_locked():
    assert cfg["dates"]["holdout_locked"] is True
    assert D.download_end(cfg) == "2024-01-01"


def _have_clean():
    return (D.clean_dir(cfg) / "prices" / "SPY.csv").exists()


@pytest.mark.skipif(not _have_clean(), reason="run build_clean() first")
def test_clean_data_has_no_holdout_and_no_gaps():
    end = pd.Timestamp(cfg["dates"]["holdout_start"])
    spy = D.load_clean("SPY")
    for t in cfg["instruments"]["unleveraged"] + list(cfg["instruments"]["leveraged"]):
        df = D.load_clean(t)
        assert df.index.max() < end, t
        assert df.index.equals(spy.index), t
        assert not df[D.OHLC].isna().any().any(), t
        assert (df[D.OHLC] > 0).all().all(), t
    assert D.load_cash().index.equals(spy.index)


@pytest.mark.skipif(not _have_clean(), reason="run build_clean() first")
def test_clean_leveraged_real_segment_equals_raw():
    for t in cfg["instruments"]["leveraged"]:
        clean = D.load_clean(t)
        raw = D.load_raw(t)
        real = clean[clean["source"] == "real"]
        assert real.index[0] == raw.index[0]
        pd.testing.assert_frame_equal(real[D.OHLC], raw.loc[real.index, D.OHLC], check_freq=False)
        assert (clean.loc[clean.index < raw.index[0], "source"] == "synthetic").all()


def test_extra_drag_calibration_uses_only_dates_through_end():
    idx = pd.bdate_range("2018-12-26", periods=6)                 # 3 days in 2018, 3 in 2019
    real = pd.Series([100, 100, 100, 100, 50, 25], index=idx, dtype=float)
    syn = pd.Series([100, 101, 102.01, 103.0301, 103.0301, 103.0301], index=idx, dtype=float)
    drag, n = D.calibrate_extra_drag(real, syn, "2018-12-31")
    assert n == 3                                                  # 2018-12-27, -28, -31 returns only
    assert drag == pytest.approx(0.01 * 252)                       # 2019 crash ignored


def test_extra_drag_lowers_synthetic_return_by_drag_over_252():
    under = pd.Series([100.0, 101.0], index=DAYS[:2])
    cash = pd.Series([0.0, 0.0], index=DAYS[:2])
    a = D.synthetic_returns(under, cash, 3, 0.0)
    b = D.synthetic_returns(under, cash, 3, 0.0, extra_drag=0.0252)
    assert a.iloc[1] - b.iloc[1] == pytest.approx(0.0001)


def test_interpolate_suspects_replaces_only_window_closes():
    df = frame([10, 11, 11, 11, 14], opens=[10, 10.5, 11, 11, 13])
    out = D.interpolate_suspects(df, str(DAYS[1].date()), str(DAYS[3].date()))
    # neighbors: DAYS[0]=Mon 10, DAYS[4]=Fri 14, linear in calendar days
    assert out["Close"].tolist() == pytest.approx([10, 11, 12, 13, 14])
    assert out["Open"].tolist() == df["Open"].tolist()
    assert (out["High"] >= out["Close"]).all() and (out["Low"] <= out["Close"]).all()
    assert df["Close"].tolist() == [10, 11, 11, 11, 14]      # input untouched
