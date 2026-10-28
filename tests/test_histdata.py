"""HistData helpers (Phase D): time-zone readings at the EU and US DST edges, the per-second payroll rule, weekend
window, fingerprint determinism, holdout refusal. Synthetic data only."""
import numpy as np
import pandas as pd
import pytest

from src import histdata as H


def ft(*s):
    return pd.Series(pd.to_datetime(list(s)))


def test_readings_around_dst_changes_2018():
    # EU summer time 2018: 25 Mar - 28 Oct; US: 11 Mar - 4 Nov
    f = ft("2018-03-14 08:30:00", "2018-04-06 08:30:00", "2018-10-31 07:30:00", "2018-12-07 08:30:00")
    c = H.to_utc(f, "C")
    assert list(c.dt.strftime("%m-%d %H:%M")) == ["03-14 13:30", "04-06 12:30", "10-31 12:30", "12-07 13:30"]
    a = H.to_utc(f, "A")
    assert list(a.dt.strftime("%H:%M")) == ["13:30", "13:30", "12:30", "13:30"]          # never shifts
    b = H.to_utc(f, "B")
    assert list(b.dt.strftime("%H:%M")) == ["12:30", "12:30", "11:30", "13:30"]          # follows the US clock


def test_reading_c_matches_payroll_time_in_each_regime():
    """Under C, file time t maps to 08:30 New York exactly when C's offset matches: EU winter + US winter (file 08:30),
    EU summer + US summer (file 08:30), EU winter + US summer (file 07:30)."""
    for f, day in (("2018-01-05 08:30:00", "2018-01-05"), ("2018-07-06 08:30:00", "2018-07-06"),
                   ("2018-11-02 07:30:00", "2018-11-02")):
        u = H.to_utc(ft(f), "C").iloc[0]
        assert u == pd.Timestamp(day + " 08:30", tz=H.NY).tz_convert("UTC")


def test_first_jump_seconds_and_misses():
    t0 = pd.Timestamp("2018-11-02 08:30:00", tz=H.NY)
    idx = pd.DatetimeIndex([t0 - pd.Timedelta(seconds=s) for s in (40, 20, 5)] +
                           [t0 + pd.Timedelta(seconds=s) for s in (0.8, 1.6, 30)]).tz_convert("UTC")
    mid = pd.Series([112.00, 112.01, 112.00, 112.02, 112.10, 112.15], index=idx)
    assert abs(H.first_jump_seconds(mid, "2018-11-02") - 1.6) < 1e-9                   # 0.8 s move is only 2 pips
    flat = pd.Series(112.0, index=idx)
    assert H.first_jump_seconds(flat, "2018-11-02") is None
    ok, secs = H.q2_seconds(mid, ["2018-11-02", "2018-12-07"])
    assert ok == 1 and secs[1] is None                                                 # a day without data is a miss
    late = mid.copy()
    late.index = late.index + pd.Timedelta(seconds=10)
    assert H.q2_seconds(late, ["2018-11-02"])[0] == 0                                  # outside the 0-5 s window


def test_weekend_mask():
    t = pd.DatetimeIndex(["2018-11-02 20:59:00", "2018-11-02 21:00:00", "2018-11-04 21:59:00",
                          "2018-11-04 22:00:00"]).tz_localize("UTC")                   # Fri 16:59/17:00 EDT; Sun 16:59/17:00 EST
    assert list(H.weekend_mask(t)) == [False, True, True, False]


def test_tick_hash_deterministic_and_sensitive():
    idx = pd.date_range("2018-01-02", periods=500, freq="7s", tz="UTC")
    m = pd.Series(110 + np.arange(500) * 0.001, index=idx)
    assert H.tick_hash(m) == H.tick_hash(m.copy())
    m2 = m.copy()
    m2.iloc[100] += 0.001                                                              # one tick inside a minute
    assert H.tick_hash(m2) != H.tick_hash(m)


def test_load_refuses_holdout():
    with pytest.raises(ValueError):
        H.load(2024)


def test_load_drops_exact_duplicates(tmp_path, monkeypatch):
    import zipfile
    d = tmp_path / "usdjpy_tick_2017"
    d.mkdir()
    rows = "20170103 170000100,117.100,117.105,0\n20170103 170000200,117.101,117.106,0\n" \
           "20170103 170000100,117.100,117.105,0\n20170103 170000300,117.102,117.106,0\n"
    with zipfile.ZipFile(d / "HISTDATA_COM_ASCII_USDJPY_T201701.zip", "w") as z:
        z.writestr("DAT_ASCII_USDJPY_T_201701.csv", rows)
    monkeypatch.setattr(H, "RAW", tmp_path)
    raw = H.load(2017, dedupe=False)
    clean = H.load(2017)
    assert len(raw) == 4 and raw.attrs["duplicates_found"] == 1
    assert len(clean) == 3 and clean.attrs["duplicates_removed"] == 1
