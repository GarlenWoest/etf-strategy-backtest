"""HistData USD/JPY tick data: loading, time-zone readings and data-quality measures (Phase D, 2026-10-28).

Data quality only: no hypothesis, no strategy; nothing here feeds a study. Pre-2024 years only (the loader refuses 2024+).
tools/pilot_histdata.py stays unchanged as the record of the 2019 pilot; this module serves tools/histdata_checks.py.

Time-zone readings of HistData's file time (see reports/data_quality/phaseD_2018_test_specification.md):
  A  fixed UTC-5 (HistData FAQ)
  B  New York local time
  C  UTC-5, +1 h during EU summer time = file + 7 h read as Europe/Helsinki wall time (suggested by 2019)
"""
import zipfile
from datetime import date

import numpy as np
import pandas as pd

from src import PROJECT_ROOT
from src import clock as K

NY = "America/New_York"
PIP = 0.01
RAW = PROJECT_ROOT / "data" / "raw" / "histdata"
READINGS = {"A": "fixed UTC−5 (FAQ)", "B": "New York local time", "C": "UTC−5, +1 h during EU summer time"}
# BLS Employment Situation release dates (08:30 ET), from the archive links on bls.gov/bls/news-release/empsit.htm
NFP = {2018: ["2018-01-05", "2018-02-02", "2018-03-09", "2018-04-06", "2018-05-04", "2018-06-01", "2018-07-06",
              "2018-08-03", "2018-09-07", "2018-10-05", "2018-11-02", "2018-12-07"],
       2019: ["2019-01-04", "2019-02-01", "2019-03-08", "2019-04-05", "2019-05-03", "2019-06-07", "2019-07-05",
              "2019-08-02", "2019-09-06", "2019-10-04", "2019-11-01", "2019-12-06"]}


def load(year, dedupe=True):
    """Rows in file order: file_time (naive), bid, ask, mid, spread_pips. With dedupe (default), exact duplicate rows
    (same timestamp, bid and ask) are dropped; out.attrs['duplicates_removed'] records how many."""
    if year >= 2024:
        raise ValueError("2024 onward is the locked holdout")
    parts = []
    for z in sorted((RAW / ("usdjpy_tick_%d" % year)).glob("HISTDATA_COM_ASCII_USDJPY_T%d*.zip" % year)):
        zf = zipfile.ZipFile(z)
        name = [n for n in zf.namelist() if n.endswith(".csv")][0]
        parts.append(pd.read_csv(zf.open(name), header=None, names=["ts", "bid", "ask", "vol"], dtype={"ts": str}))
    if not parts:
        raise FileNotFoundError("no HistData files for %d" % year)
    df = pd.concat(parts, ignore_index=True)
    dup = df.duplicated(["ts", "bid", "ask"])
    if dedupe:                                  # cleaning rule (Phase D): exact repeats of timestamp, bid and ask are
        df = df[~dup].reset_index(drop=True)    # vendor duplicates (e.g. the repeated hour on 2019-10-27)
    out = pd.DataFrame({"file_time": pd.to_datetime(df["ts"], format="%Y%m%d %H%M%S%f"),
                        "bid": df["bid"].astype(float), "ask": df["ask"].astype(float)})
    out["mid"] = (out["bid"] + out["ask"]) / 2
    out["spread"] = (out["ask"] - out["bid"]) / PIP
    out.attrs["duplicates_removed"] = int(dup.sum()) if dedupe else 0
    out.attrs["duplicates_found"] = int(dup.sum())
    return out


def to_utc(file_time, reading):
    if reading == "A":
        return (file_time + pd.Timedelta(hours=5)).dt.tz_localize("UTC")
    if reading == "B":
        return file_time.dt.tz_localize(NY, ambiguous=False, nonexistent="shift_forward").dt.tz_convert("UTC")
    if reading == "C":
        return (file_time + pd.Timedelta(hours=7)).dt.tz_localize("Europe/Helsinki", ambiguous=False,
                                                                  nonexistent="shift_forward").dt.tz_convert("UTC")
    raise ValueError(reading)


def series(utc, values):
    """Values indexed by UTC time, sorted (stable) so time slicing is exact and fast."""
    return pd.Series(np.asarray(values), index=pd.DatetimeIndex(utc)).sort_index(kind="stable")


def first_jump_seconds(mid_utc, day, pips=3.0):
    """Seconds after 08:30:00 New York of the first tick-to-tick mid move >= `pips` in 08:29:00-08:31:30; None if none."""
    t0 = pd.Timestamp(day + " 08:30:00", tz=NY)
    w = mid_utc.loc[pd.Timestamp(day + " 08:29:00", tz=NY): pd.Timestamp(day + " 08:31:30", tz=NY)]
    ch = w.diff().abs() / PIP
    hit = ch[ch >= pips]
    return None if hit.empty else (hit.index[0] - t0).total_seconds()


def q2_seconds(mid_utc, days, rule_window=(0, 5), pips=3.0):
    secs = [first_jump_seconds(mid_utc, d, pips) for d in days]
    ok = sum(s is not None and rule_window[0] <= s <= rule_window[1] for s in secs)
    return ok, secs


def minute_peak(mid_utc, day):
    """Legacy (pre-set 2019) rule: New York minute with the largest absolute 1-minute mid change, 07:00-10:00."""
    m = mid_utc.resample("1min").last().ffill()
    ny = m.tz_convert(NY)
    w = ny[(ny.index.date == date.fromisoformat(day)) & (ny.index.hour >= 7) & (ny.index.hour < 10)]
    return w.diff().abs().idxmax().strftime("%H:%M")


def weekend_mask(utc):
    ny = pd.DatetimeIndex(utc).tz_convert(NY)
    mins = ny.hour * 60 + ny.minute
    wd = ny.day_of_week
    return np.asarray(((wd == 4) & (mins >= 17 * 60)) | (wd == 5) | ((wd == 6) & (mins < 17 * 60)))


def session_mask(utc, kind):
    """Business-day session windows: 'ldn_ny' (London 08-17 or New York 08-17 local), 'tokyo' (09-18 local)."""
    idx = pd.DatetimeIndex(utc)
    if kind == "tokyo":
        tk = idx.tz_convert("Asia/Tokyo")
        bus = pd.Series(tk.date).map(lambda d: K.is_business_day(d, K.jp_bank_holidays)).to_numpy()
        return bus & np.asarray((tk.hour >= 9) & (tk.hour < 18))
    ny, ld = idx.tz_convert(NY), idx.tz_convert("Europe/London")
    bus_l = pd.Series(ld.date).map(lambda d: K.is_business_day(d, K.uk_bank_holidays)).to_numpy()
    bus_n = pd.Series(ny.date).map(lambda d: K.is_business_day(d, K.us_board_holidays)).to_numpy()
    return (bus_l & np.asarray((ld.hour >= 8) & (ld.hour < 17))) | (bus_n & np.asarray((ny.hour >= 8) & (ny.hour < 17)))


def noon_anchor(mid_utc, h10):
    """Pips between the last mid at or before 12:00 New York (within 60 s) and the Fed H.10 noon rate, per day."""
    out = {}
    for d, v in h10.items():
        noon = pd.Timestamp(pd.Timestamp(d).date().isoformat() + " 12:00", tz=NY).tz_convert("UTC")
        w = mid_utc.loc[noon - pd.Timedelta(seconds=60): noon]
        if len(w):
            out[pd.Timestamp(d).date()] = (float(w.iloc[-1]) - float(v)) / PIP
    return pd.Series(out, dtype=float)


def tick_hash(mid_utc):
    """SHA-256 over every tick of the transformed series (UTC time in ns, mid rounded to 0.0001), in time order: a
    fingerprint for checking that the time-zone transformation and cleaning are reproducible."""
    import hashlib
    a = np.column_stack([mid_utc.index.asi8, np.round(mid_utc.to_numpy() * 1e4).astype(np.int64)])
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
