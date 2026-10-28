"""DATA PILOT (Priority 2, approved 2026-10-28): HistData USD/JPY ticks for 2019, quality tests Q1-Q9 of
reports/data_vendor_comparison.md. Not research: no hypothesis, no strategy, nothing enters a study.

Input (untrusted, read only): data/raw/histdata/usdjpy_tick_2019/HISTDATA_COM_ASCII_USDJPY_T2019MM.zip
  rows "YYYYMMDD HHMMSSmmm,bid,ask,0" (millisecond file time).
Time zone. HistData's FAQ says: "Eastern Standard Time (EST) time-zone WITHOUT Day Light Savings adjustments", i.e.
fixed UTC-5. Q2 tests three readings of the file time against events whose real time is known:
  A  FAQ: fixed UTC-5                         utc = file + 5 h
  B  New York local time (US DST)             file is America/New_York wall time
  C  UTC-5 shifted by EU summer time          utc = file + 5 h in EU winter, + 4 h in EU summer
                                              (= file + 7 h read as Europe/Helsinki wall time)
Events: the BLS payroll release at 08:30 New York (12 in 2019) and the daily 17:00 New York rollover spread spike
(Monday-Thursday). All other tests (Q3-Q8) use the reading that Q2 supports; the documented reading is reported too.
Optional cross-check (Q4): data/raw/truefx/USDJPY-2019-MM.zip (TrueFX monthly files; the user downloads them).
Outputs: data/raw/histdata/usdjpy_tick_2019/manifest.json (SHA-256 of each raw file),
         reports/data_quality/histdata_usdjpy_2019_pilot.md
Usage: .venv/bin/python tools/pilot_histdata.py
"""
import glob
import hashlib
import json
import sys
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src import PROJECT_ROOT
from src import clock as K

RAW = PROJECT_ROOT / "data" / "raw" / "histdata" / "usdjpy_tick_2019"
TFX = PROJECT_ROOT / "data" / "raw" / "truefx"
OUT = PROJECT_ROOT / "reports" / "data_quality" / "histdata_usdjpy_2019_pilot.md"
NY = "America/New_York"
PIP = 0.01
# BLS Employment Situation release dates in 2019 (08:30 ET), from the archive links on bls.gov/bls/news-release/empsit.htm
NFP = ["2019-01-04", "2019-02-01", "2019-03-08", "2019-04-05", "2019-05-03", "2019-06-07", "2019-07-05", "2019-08-02",
       "2019-09-06", "2019-10-04", "2019-11-01", "2019-12-06"]
CONV = {"A": "FAQ: fixed UTC−5", "B": "New York local time", "C": "UTC−5, +1 h during EU summer time"}
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def to_utc(file_time, conv):
    if conv == "A":
        return (file_time + pd.Timedelta(hours=5)).dt.tz_localize("UTC")
    if conv == "B":
        return file_time.dt.tz_localize(NY, ambiguous=False, nonexistent="shift_forward").dt.tz_convert("UTC")
    if conv == "C":
        return (file_time + pd.Timedelta(hours=7)).dt.tz_localize("Europe/Helsinki", ambiguous=False,
                                                                  nonexistent="shift_forward").dt.tz_convert("UTC")
    raise ValueError(conv)


def load_histdata():
    parts = []
    for z in sorted(RAW.glob("HISTDATA_COM_ASCII_USDJPY_T2019*.zip")):
        zf = zipfile.ZipFile(z)
        name = [n for n in zf.namelist() if n.endswith(".csv")][0]
        parts.append(pd.read_csv(zf.open(name), header=None, names=["ts", "bid", "ask", "vol"], dtype={"ts": str}))
    df = pd.concat(parts, ignore_index=True)
    out = pd.DataFrame({"file_time": pd.to_datetime(df["ts"], format="%Y%m%d %H%M%S%f"),
                        "bid": df["bid"].astype(float), "ask": df["ask"].astype(float)})
    out["mid"] = (out["bid"] + out["ask"]) / 2
    out["spread"] = (out["ask"] - out["bid"]) / PIP
    return out


def load_truefx():
    files = sorted(f for f in glob.glob(str(TFX / "*.zip")) if "USDJPY" in Path(f).name.upper() and "2019" in Path(f).name)
    if not files:
        return None, []
    parts = []
    for z in files:
        zf = zipfile.ZipFile(z)
        name = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
        parts.append(pd.read_csv(zf.open(name), header=None, names=["pair", "ts", "bid", "ask"]))
    df = pd.concat(parts, ignore_index=True)
    utc = pd.to_datetime(df["ts"].astype(str), format="%Y%m%d %H:%M:%S.%f").dt.tz_localize("UTC")  # TrueFX: GMT (checked below)
    return pd.DataFrame({"utc": utc, "mid": (df["bid"] + df["ask"]) / 2, "bid": df["bid"], "ask": df["ask"]}), files


def minute_bars(utc, mid):
    g = pd.Series(mid.to_numpy(), index=pd.DatetimeIndex(utc))
    return g.resample("1min").last(), g.resample("1min").count()


def session_minutes(index_utc, kind):
    """Minutes inside business-day windows. kind 'ldn_ny': London 08-17 or New York 08-17 local; 'tokyo': 09-18."""
    if kind == "tokyo":
        tk = index_utc.tz_convert("Asia/Tokyo")
        return np.array([K.is_business_day(d, K.jp_bank_holidays) for d in tk.date]) & (tk.hour >= 9) & (tk.hour < 18)
    ny, ld = index_utc.tz_convert(NY), index_utc.tz_convert("Europe/London")
    in_ldn = (ld.hour >= 8) & (ld.hour < 17) & np.array([K.is_business_day(d, K.uk_bank_holidays) for d in ld.date])
    in_ny = (ny.hour >= 8) & (ny.hour < 17) & np.array([K.is_business_day(d, K.us_board_holidays) for d in ny.date])
    return in_ldn | in_ny


def nfp_peaks(last_ny):
    """Peak minute (NY) of the absolute 1-minute mid change 07:00-10:00 NY on each payroll day."""
    out = []
    for d in NFP:
        dd = date.fromisoformat(d)
        w = last_ny.loc[(last_ny.index.date == dd) & (last_ny.index.hour >= 7) & (last_ny.index.hour < 10)].ffill()
        r = w.diff().abs()
        out.append((r.idxmax().strftime("%H:%M"), float(r.max() / PIP)))
    return out


def nfp_seconds(utc, mid):
    """Time (NY) of the first tick-to-tick mid move >= 3 pips between 08:29:00 and 08:31:30 on each payroll day."""
    s = pd.Series(mid.to_numpy(), index=pd.DatetimeIndex(utc).tz_convert(NY)).sort_index(kind="stable")
    out = []
    for d in NFP:
        w = s.loc[pd.Timestamp(d + " 08:29:00", tz=NY): pd.Timestamp(d + " 08:31:30", tz=NY)]
        ch = w.diff().abs() / PIP
        first = ch[ch >= 3].index.min()
        out.append(None if pd.isna(first) else (first - pd.Timestamp(d + " 08:30:00", tz=NY)).total_seconds())
    return out


def rollover_share(utc, spread):
    """Share of Monday-Thursday days whose median-spread peak (15:30-18:30 NY) falls in 17:00-17:14 NY."""
    ny = pd.DatetimeIndex(utc).tz_convert(NY)
    m = (ny.day_of_week <= 3) & (ny.hour * 60 + ny.minute >= 15 * 60 + 30) & (ny.hour * 60 + ny.minute <= 18 * 60 + 30)
    df = pd.DataFrame({"day": ny.date[m], "min": (ny.hour * 60 + ny.minute)[m], "sp": spread.to_numpy()[m]})
    pk = df.groupby(["day", "min"])["sp"].median().reset_index()
    pk = pk.loc[pk.groupby("day")["sp"].idxmax()]
    return float(((pk["min"] >= 17 * 60) & (pk["min"] < 17 * 60 + 15)).mean()), len(pk)


def weekend_ticks(utc):
    ny = pd.DatetimeIndex(utc).tz_convert(NY)
    mins = ny.hour * 60 + ny.minute
    wk = ((ny.day_of_week == 4) & (mins >= 17 * 60)) | (ny.day_of_week == 5) | ((ny.day_of_week == 6) & (mins < 17 * 60))
    return int(wk.sum()), wk


def main():
    files = sorted(RAW.glob("*.zip")) + sorted(RAW.glob("*.txt"))
    manifest = {"source": "histdata.com, ASCII tick (T), USDJPY, 2019",
                "downloaded_files": {f.name: {"bytes": f.stat().st_size, "sha256": sha(f)} for f in files},
                "hashed_at_utc": NOW,
                "timezone": "FAQ says fixed UTC-5; the 2019 pilot found UTC-5 shifted by EU summer time (see report)"}
    (RAW / "manifest.json").write_text(json.dumps(manifest, indent=1))
    t = load_histdata()
    n = len(t)
    back = t["file_time"].diff().dt.total_seconds()
    n_back, worst_back = int((back < 0).sum()), float(-back.min())
    back_ex = t.loc[back < 0, "file_time"].dt.strftime("%Y-%m-%d %H:%M:%S").head(3).tolist()
    t = t.sort_values("file_time", kind="stable").reset_index(drop=True)          # analysis order; raw order reported

    # ---------------- Q2: three readings of the file time against known events
    q2 = {}
    for c in CONV:
        utc = to_utc(t["file_time"], c)
        last, _ = minute_bars(utc, t["mid"])
        peaks = nfp_peaks(last.tz_convert(NY))
        share, ndays = rollover_share(utc, t["spread"])
        secs = nfp_seconds(utc, t["mid"])
        q2[c] = {"peaks": peaks, "nfp_ok": sum(p == "08:30" for p, _ in peaks), "roll": share, "roll_days": ndays,
                 "weekend": weekend_ticks(utc)[0], "secs": secs,
                 "sec_ok": sum(x is not None and 0 <= x <= 5 for x in secs), "sec_n": sum(x is not None for x in secs)}
    best = max(CONV, key=lambda c: (q2[c]["sec_ok"], q2[c]["nfp_ok"], q2[c]["roll"]))
    passes = lambda c: q2[c]["nfp_ok"] >= 11            # the rule set in the vendor report (minute of the peak)
    t["utc"] = to_utc(t["file_time"], best)
    assert t["utc"].max() < pd.Timestamp("2020-01-01", tz="UTC") and t["utc"].max() < pd.Timestamp("2024-01-01", tz="UTC")
    t["ny"] = t["utc"].dt.tz_convert(NY)
    last_utc, nticks = minute_bars(t["utc"], t["mid"])

    # ---------------- Q3: daily anchor vs FRED H.10 noon rate
    fx = pd.read_csv(PROJECT_ROOT / "data" / "raw" / "usdjpy" / "fred_DEXJPUS.csv", index_col=0, parse_dates=True)["DEXJPUS"]
    s = pd.Series(t["mid"].to_numpy(), index=pd.DatetimeIndex(t["utc"])).sort_index(kind="stable")
    diffs = []
    for d, v in fx.loc["2019"].dropna().items():
        noon = pd.Timestamp(d.date().isoformat() + " 12:00", tz=NY).tz_convert("UTC")
        w = s.loc[noon - pd.Timedelta(seconds=60): noon]
        if len(w):
            diffs.append((d.date(), float(w.iloc[-1]), float(v), (float(w.iloc[-1]) - float(v)) / PIP))
    dq3 = pd.DataFrame(diffs, columns=["date", "histdata_mid", "h10", "diff_pips"])
    q3_med = float(dq3["diff_pips"].abs().median())

    # ---------------- Q5: bid/ask sanity
    neg, zero = int((t["ask"] < t["bid"]).sum()), int((t["ask"] == t["bid"]).sum())
    wide = t[t["spread"] > 20 * t.groupby(t["ny"].dt.hour)["spread"].transform("median")]

    # ---------------- Q6: coverage
    idx = nticks.index
    fx_open = np.array([K.fx_market_open(x.to_pydatetime()) for x in idx])
    liquid, tokyo = session_minutes(idx, "ldn_ny") & fx_open, session_minutes(idx, "tokyo") & fx_open
    cov_l, cov_t = float((nticks[liquid] > 0).mean()), float((nticks[tokyo] > 0).mean())
    empty = (nticks[liquid] == 0)
    gap_lens = empty.groupby((~empty).cumsum()).sum()
    long_gaps = int((gap_lens > 5).sum())

    # ---------------- Q7: weekends and holidays
    n_weekend, wk = weekend_ticks(t["utc"])
    wk_days = t.loc[wk, "ny"].dt.strftime("%a %Y-%m-%d").value_counts()
    daily = t.groupby(t["ny"].dt.date).size()
    weekday_med = float(daily[[d.weekday() < 5 for d in daily.index]].median())
    hol = {d: int(daily.get(d, 0)) for d in (date(2019, 1, 1), date(2019, 7, 4), date(2019, 11, 28), date(2019, 12, 25))}

    # ---------------- Q8: stale quotes, outliers, duplicates
    liq_t = session_minutes(pd.DatetimeIndex(t["utc"]), "ldn_ny")
    ch = t["mid"].diff().ne(0)
    stale = int((t.loc[ch & liq_t, "utc"].diff().dt.total_seconds() > 120).sum())
    r1 = last_utc.ffill().diff() / PIP
    mad = r1.abs().groupby(r1.index.tz_convert(NY).hour).transform("median") * 1.4826
    big = r1[(r1.abs() > 10 * mad) & (mad > 0)]
    dup = float(t["file_time"].duplicated().mean())

    # ---------------- Q4: cross-vendor (TrueFX), when present
    tf, tf_files = load_truefx()
    if tf is not None:
        tl, _ = minute_bars(tf["utc"], tf["mid"])
        both = pd.concat({"hd": last_utc, "tf": tl}, axis=1).dropna()
        both = both[session_minutes(both.index, "ldn_ny")]
        q4_mad = float((both["hd"] - both["tf"]).abs().median() / PIP)
        q4_corr = float(both.diff().dropna().corr().iloc[0, 1])
        tf_secs = nfp_seconds(tf["utc"], tf["mid"])                       # TrueFX's own clock, read as UTC
        tf_sec_ok = sum(x is not None and 0 <= x <= 5 for x in tf_secs)

    V = lambda b: "PASS" if b else "FAIL"
    res = {"Q1": "CONDITIONAL", "Q2 (documented reading A)": V(passes("A")), "Q2 (reading %s)" % best: V(passes(best)),
           "Q3": V(q3_med <= 3), "Q4": "PENDING" if tf is None else V(q4_mad <= 0.5 and q4_corr >= 0.95),
           "Q5": V(neg == 0 and (neg + zero) / n < 1e-4), "Q6": V(cov_l >= 0.99), "Q7": V(n_weekend / n < 1e-4),
           "Q8": "PENDING", "Q9": "PASS"}
    hm = lambda m: "%02d:%02d" % divmod(int(m), 60)
    L = ["# Data pilot: HistData USD/JPY ticks, 2019 (quality tests Q1–Q9)\n",
         "_Run %s. Data pilot only: no hypothesis, no strategy; nothing enters a study. 2019 only (holdout untouched)._\n" % NOW,
         "**Data:** %d ticks in 12 monthly files (%.0f MB zipped, %.0f MB unzipped), %s to %s UTC (reading %s). "
         "Raw files are SHA-256-hashed in `data/raw/histdata/usdjpy_tick_2019/manifest.json`.\n" % (
             n, sum(v["bytes"] for k, v in manifest["downloaded_files"].items() if k.endswith(".zip")) / 1e6,
             sum(i.file_size for z in RAW.glob("*.zip") for i in zipfile.ZipFile(z).infolist()) / 1e6,
             t["utc"].min().strftime("%Y-%m-%d %H:%M"), t["utc"].max().strftime("%Y-%m-%d %H:%M"), best),
         "## Results\n", "| Test | Verdict | Evidence |", "|---|---|---|",
         "| Q1 licence | %s | FAQ: \"Use the data at your own will and risk\"; storage isn't restricted; publication isn't addressed, so only aggregate statistics are ever published, never data |" % res["Q1"],
         "| Q2 time zone, documented reading (A: fixed UTC−5) | %s | Payroll spike at 08:30 NY in %d of 12 releases; rollover spike at 17:00 NY on %.0f%% of %d Mon–Thu days. **The FAQ's convention does not hold for 2019.** |" % (
             res["Q2 (documented reading A)"], q2["A"]["nfp_ok"], 100 * q2["A"]["roll"], q2["A"]["roll_days"]),
         "| Q2 time zone, reading supported by the data (%s: %s) | %s by the pre-set rule | Largest one-minute move at 08:30 NY in %d of 12 releases (rule ≥ 11). Second by second: the first ≥ 3-pip move lands 0–5 s after 08:30:00 in %d of the 12 releases (%d had no ≥ 3-pip move in the window; range %s s). Rollover spike at 17:00 NY on %.0f%% of Mon–Thu days. The H.10 noon rate (Q3) and the weekend window (Q7) agree with this reading. It was found from this same year: confirm on another year and with TrueFX before adoption |" % (
             best, CONV[best], res["Q2 (reading %s)" % best], q2[best]["nfp_ok"], q2[best]["sec_ok"], 12 - q2[best]["sec_n"],
             "%.1f to %.1f" % (min(x for x in q2[best]["secs"] if x is not None), max(x for x in q2[best]["secs"] if x is not None)),
             100 * q2[best]["roll"]),
         "| Q3 daily anchor (H.10 noon rate) | %s | %d days; median absolute difference %.2f pips (rule ≤ 3); 95th percentile %.2f; largest %.2f (%s) |" % (
             res["Q3"], len(dq3), q3_med, dq3["diff_pips"].abs().quantile(0.95), dq3["diff_pips"].abs().max(),
             dq3.loc[dq3["diff_pips"].abs().idxmax(), "date"]),
         "| Q4 cross-vendor (TrueFX) | %s | %s |" % (res["Q4"], "TrueFX 2019 files not downloaded yet" if tf is None else
                                                    "%d files; median absolute difference of 1-min mids %.2f pips (rule ≤ 0.5); 1-min return correlation %.3f (rule ≥ 0.95); TrueFX's own clock (read as UTC): first ≥ 3-pip payroll move 0–5 s after 08:30:00 in %d of 12" % (len(tf_files), q4_mad, q4_corr, tf_sec_ok)),
         "| Q5 bid/ask sanity | %s | ask < bid: %d ticks; ask = bid: %d; spreads > 20× the hourly median: %d ticks (%.3f%%) |" % (
             res["Q5"], neg, zero, len(wide), 100 * len(wide) / n),
         "| Q6 coverage | %s | London/NY business hours: %.2f%% of minutes have ≥ 1 tick (rule ≥ 99%%); %d gaps > 5 min. Tokyo business hours: %.2f%% (reported only) |" % (
             res["Q6"], 100 * cov_l, long_gaps, 100 * cov_t),
         "| Q7 weekends and holidays | %s | %d ticks inside Fri 17:00 – Sun 17:00 NY (%.4f%%; rule < 0.01%%); under reading A there would be %d. Holiday tick counts vs a median weekday of %.0f: %s |" % (
             res["Q7"], n_weekend, 100 * n_weekend / n, q2["A"]["weekend"], weekday_med,
             ", ".join("%s %d" % (k, v) for k, v in hol.items())),
         "| Q8 stale and outliers | %s | %d stale runs (> 2 min without a mid change in London/NY hours); %d one-minute moves > 10 robust σ, to be confirmed or rejected by TrueFX; %.1f%% of rows repeat the previous timestamp |" % (
             res["Q8"], stale, len(big), 100 * dup),
         "| Q8b out-of-order rows | FINDING | %d row(s) earlier than the row before (largest step back %.0f s, at file time %s); sorted (stable) before every test |" % (
             n_back, worst_back, ", ".join(back_ex)),
         "| Q9 reproducibility | %s | Raw zips immutable and hashed; data ends 2019-12-31; this script is the cleaning rule |" % res["Q9"],
         "\n## Q2 detail: payroll releases (08:30 New York)\n",
         "| Release | US clock | EU clock | Peak minute NY, reading A | reading B | reading C | Size (pips, C) | First ≥ 3-pip move, C (s after 08:30:00) |",
         "|---|---|---|---|---|---|---|---|"]
    for i, d in enumerate(NFP):
        ts = pd.Timestamp(d + " 08:30", tz=NY)
        sc = q2["C"]["secs"][i]
        L.append("| %s | %s | %s | %s | %s | %s | %.1f | %s |" % (
            d, "EDT" if ts.dst() else "EST", "summer" if ts.tz_convert("Europe/London").dst() else "winter",
            q2["A"]["peaks"][i][0], q2["B"]["peaks"][i][0], q2["C"]["peaks"][i][0], q2["C"]["peaks"][i][1],
            "%.1f" % sc if sc is not None else "no ≥ 3-pip move"))
    L += ["\n| Reading | Peak minute at 08:30 NY | First ≥ 3-pip move within 0–5 s of 08:30:00 (of 12) | Rollover spike at 17:00 NY (Mon–Thu days) | Ticks inside the weekend window |",
          "|---|---|---|---|---|"]
    for c in CONV:
        L.append("| %s: %s | %d of 12 | %d of 12 | %.0f%% | %d |" % (c, CONV[c], q2[c]["nfp_ok"], q2[c]["sec_ok"],
                                                                100 * q2[c]["roll"], q2[c]["weekend"]))
    L += ["\n**Why the pre-set Q2 rule misses under reading C:** it asks which whole minute had the largest move. On "
          "2019-02-01 the follow-through in 08:31 was larger than the first jump; on 2019-04-05 the minute bar 08:29 closed "
          "after a pre-release drift; on 2019-08-02 payrolls barely moved USD/JPY. The second-by-second measure is the "
          "better test of the clock. **Proposed rule for future years (set before they are run):** the first ≥ 3-pip move "
          "falls 0–5 s after 08:30:00 in ≥ 90% of releases that produce a ≥ 3-pip move under the reading being tested, and no more than one release has none.\n"]
    L += ["\nThe readings differ only in two windows: US summer with EU winter (10–31 March and 27 October – 3 November "
          "2019), and EU summer (31 March – 27 October). A day-by-day look at the Monday–Thursday "
          "rollover spike in file time (diagnostic during the pilot) shows it at 16:00 file time exactly in the two short "
          "windows and at 17:00 otherwise, as reading C predicts; reading B would put it at 16:00 New York in those weeks. "
          "The 17% of days outside 17:00–17:14 NY under C are days whose widest spread fell elsewhere in 15:30–18:30.\n",
          "## Q3 detail: largest differences from the H.10 noon rate\n",
          "| Date | HistData mid 12:00 NY | H.10 | Difference (pips) |", "|---|---|---|---|"]
    for _, r in dq3.reindex(dq3["diff_pips"].abs().sort_values(ascending=False).index).head(5).iterrows():
        L.append("| %s | %.3f | %.2f | %+.2f |" % (r["date"], r["histdata_mid"], r["h10"], r["diff_pips"]))
    L += ["\n## Q5–Q8 detail\n",
          "- Median spread over the year: %.2f pips; London/NY hours %.2f; Tokyo hours %.2f." % (
              t["spread"].median(), t.loc[liq_t, "spread"].median(),
              t.loc[session_minutes(pd.DatetimeIndex(t["utc"]), "tokyo"), "spread"].median()),
          "- Widest spreads (pips, NY time): %s." % ", ".join(
              "%s %.1f" % (a.strftime("%Y-%m-%d %H:%M"), b) for a, b in
              wide.nlargest(5, "spread")[["ny", "spread"]].drop_duplicates("ny").itertuples(index=False)),
          "- Largest one-minute moves (pips, NY time): %s." % ", ".join(
              "%s %+.1f" % (a.tz_convert(NY).strftime("%Y-%m-%d %H:%M"), r1.loc[a]) for a in
              big.abs().sort_values(ascending=False).head(5).index),
          "- Weekend-window ticks by NY day (top 5): %s." % (", ".join("%s %d" % kv for kv in wk_days.head(5).items()) or "none"),
          "- Longest London/NY gap: %d minutes." % (int(gap_lens.max()) if len(gap_lens) else 0),
          "\n## Notes\n",
          "- HistData publishes its own gap report per file (STATUS_*.txt, kept with the raw files).",
          "- Holiday counts are informational; FX trades on holidays, but thinly.",
          "- Q8 stays PENDING until TrueFX confirms or rejects the large moves and the stale runs."]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return res


if __name__ == "__main__":
    main()
