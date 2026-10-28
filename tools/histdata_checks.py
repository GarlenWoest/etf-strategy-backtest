"""Phase D data-quality checks for HistData USD/JPY ticks (one year per run). Data quality only, no research.

  1. Time-zone test with the rule fixed before the data were read (config q2_timezone_rule;
     reports/data_quality/phaseD_2018_test_specification.md), under readings A, B and C, plus the legacy minute rule,
     the H.10 noon anchor, the weekend window and the rollover spike.
  2. Under reading C: out-of-order rows, stale quotes, large one-minute jumps (spike-and-revert vs persistent),
     weekday/weekend continuity, spread distributions, reproducibility fingerprint.
Cross-vendor confirmation (TrueFX) is BLOCKED until its files exist; nothing here substitutes for it.
Writes only reports/data_quality/histdata_usdjpy_<year>_phaseD.md (aggregates and timestamps; no vendor quotes).
Usage: .venv/bin/python tools/histdata_checks.py --year 2018
"""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src import PROJECT_ROOT, load_config
from src import histdata as H

NY = H.NY
OUT = PROJECT_ROOT / "reports" / "data_quality"


def rule():
    r = load_config()["specialists"]["data_quality"]["q2_timezone_rule"]
    w = tuple(r["window_seconds_after_release"])
    return w, int(r["required"].split()[0])


def timezone_tests(t, year, h10):
    w, need = rule()
    res = {}
    for c in H.READINGS:
        utc = H.to_utc(t["file_time"], c)
        mid = H.series(utc, t["mid"])
        ok, secs = H.q2_seconds(mid, H.NFP[year], w)
        noon = H.noon_anchor(mid, h10)
        sp = H.series(utc, t["spread"])
        ny = sp.index.tz_convert(NY)
        mask = (ny.day_of_week <= 3) & (ny.hour * 60 + ny.minute >= 15 * 60 + 30) & (ny.hour * 60 + ny.minute <= 18 * 60 + 30)
        df = pd.DataFrame({"day": ny.date[mask], "min": (ny.hour * 60 + ny.minute)[mask], "sp": sp.to_numpy()[mask]})
        pk = df.groupby(["day", "min"])["sp"].median().reset_index()
        pk = pk.loc[pk.groupby("day")["sp"].idxmax()]
        res[c] = {"ok": ok, "secs": secs, "minute": [H.minute_peak(mid, d) for d in H.NFP[year]],
                  "noon_med": float(noon.abs().median()), "noon_max": float(noon.abs().max()), "noon_n": len(noon),
                  "weekend": int(H.weekend_mask(utc).sum()),
                  "roll": float(((pk["min"] >= 17 * 60) & (pk["min"] < 17 * 60 + 15)).mean())}
    return res, need


def out_of_order(t):
    back = t["file_time"].diff().dt.total_seconds()
    rows = []
    for i in np.flatnonzero(back.to_numpy() < 0):
        rows.append({"row": int(i), "file_time": t["file_time"].iloc[i].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                     "previous_file_time": t["file_time"].iloc[i - 1].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                     "step_back_s": float(-back.iloc[i]),
                     "context": [t["file_time"].iloc[j].strftime("%a %H:%M:%S") for j in range(max(0, i - 3), min(len(t), i + 3))]})
    return rows


def stale_runs(mid, liquid_minute):
    """Minute grid. Inside continuous London/NY business-hour blocks only (never across closed hours or weekends):
    runs of >= 3 consecutive minutes (> 2 min) with no mid change, split into 'no tick at all' and 'ticks, same mid'."""
    grid = pd.date_range(mid.index.min().floor("min"), mid.index.max().floor("min"), freq="1min", tz="UTC")
    ch = mid.diff().ne(0).groupby(mid.index.floor("min")).sum().reindex(grid, fill_value=0)
    nt = mid.groupby(mid.index.floor("min")).size().reindex(grid, fill_value=0)
    liq = liquid_minute(grid)
    quiet = (ch.to_numpy() == 0) & liq
    runs, i = [], 0
    while i < len(grid):
        if quiet[i]:
            j = i
            while j + 1 < len(grid) and quiet[j + 1]:
                j += 1
            if j - i + 1 >= 3:
                runs.append((grid[i], j - i + 1, int(nt.iloc[i:j + 1].sum())))
            i = j + 1
        else:
            i += 1
    r = pd.DataFrame(runs, columns=["start", "minutes", "ticks"])
    return {"liquid_minutes": int(liq.sum()), "runs": len(r), "runs_no_tick": int((r["ticks"] == 0).sum()) if len(r) else 0,
            "minutes_in_runs": int(r["minutes"].sum()) if len(r) else 0,
            "pct": {q: float(r["minutes"].quantile(q)) for q in (0.5, 0.9, 1.0)} if len(r) else {},
            "hours_ny": r["start"].dt.tz_convert(NY).dt.hour.value_counts().sort_index().to_dict() if len(r) else {},
            "longest": [(x.tz_convert(NY).strftime("%Y-%m-%d %H:%M"), int(m), int(k)) for x, m, k in
                        r.sort_values("minutes", ascending=False).head(5).itertuples(index=False)] if len(r) else []}


def jumps(mid):
    """One-minute mid changes between CONSECUTIVE minutes that both have ticks (never across a gap or weekend).
    Robust sigma by New York hour; absolute thresholds; spike-and-revert = undone by >= 80% within two minutes."""
    m = mid.resample("1min").last()
    prev_ok = m.shift(1).notna()
    d = ((m - m.shift(1)) / H.PIP)[prev_ok & m.notna()]
    hours = d.index.tz_convert(NY).hour
    med = d.abs().groupby(hours).median()
    mad = d.abs().groupby(hours).transform("median") * 1.4826
    sigma10 = d[(d.abs() > 10 * mad) & (mad > 0)]
    big = d[d.abs() >= 10]
    after = ((m.shift(-2) - m) / H.PIP).reindex(big.index)
    revert = (np.sign(big) != np.sign(after)) & (after.abs() >= 0.8 * big.abs())
    return {"n_minutes": int(len(d)), "gt10sigma": int(len(sigma10)), "zero_mad_hours": int((med == 0).sum()),
            "median_abs_move": float(d.abs().median()), "ge10pips": int(len(big)), "ge20pips": int((d.abs() >= 20).sum()),
            "ge10_revert": int(revert.sum()),
            "top": [(i.tz_convert(NY).strftime("%Y-%m-%d %H:%M"), round(float(v), 1), bool(revert.get(i, False)))
                    for i, v in big.abs().sort_values(ascending=False).head(8).items()]}


def convention_days(t):
    """EXPLORATORY (not a test): on Monday-Thursday days when New York and London DST differ, the FILE-time hour of the
    day's widest median spread between 15:30 and 18:30 file time. File = New York time puts the 17:00 NY rollover at
    17:xx; reading C puts it at 16:xx on these days."""
    ft = t["file_time"]
    d = ft.dt.date
    days = sorted(set(d))
    disc = []
    for x in days:
        noon = pd.Timestamp(str(x) + " 12:00", tz="UTC")
        if pd.Timestamp(x).weekday() <= 3 and bool(noon.tz_convert(NY).dst()) != bool(noon.tz_convert("Europe/London").dst()):
            disc.append(x)
    mins = ft.dt.hour * 60 + ft.dt.minute
    sel = d.isin(disc) & (mins >= 15 * 60 + 30) & (mins <= 18 * 60 + 30)
    g = pd.DataFrame({"day": d[sel], "min": mins[sel], "sp": t["spread"][sel]}).groupby(["day", "min"])["sp"].median().reset_index()
    pk = g.loc[g.groupby("day")["sp"].idxmax()]
    return [(str(r.day), "%02d:%02d" % divmod(int(r.min), 60)) for r in pk.itertuples()]


def continuity(mid):
    ny = mid.index.tz_convert(NY)
    s = pd.Series(ny, index=ny)
    weeks = s.groupby(pd.DatetimeIndex(ny).to_period("W-SAT"))
    first = weeks.min()
    last = weeks.max()
    daily = pd.Series(1, index=ny).groupby(ny.date).sum()
    wkday = daily[[d.weekday() < 5 for d in daily.index]]
    low = wkday[wkday < 0.25 * wkday.median()]
    return {"weeks": len(first), "first_tick_times": first.dt.strftime("%a %H:%M").value_counts().head(4).to_dict(),
            "last_tick_times": last.dt.strftime("%a %H:%M").value_counts().head(4).to_dict(),
            "weekday_median_ticks": float(wkday.median()),
            "low_days": [(str(d), int(v)) for d, v in low.items()],
            "by_weekday": {k: float(v) for k, v in daily.groupby([pd.Timestamp(d).day_name()[:3] for d in daily.index]).median().items()}}


def spreads(mid_utc_spread, liquid, tokyo, year):
    sp = mid_utc_spread
    ny = sp.index.tz_convert(NY)
    mins = ny.hour * 60 + ny.minute
    buckets = {"all ticks": np.ones(len(sp), bool), "London/NY business hours": liquid, "Tokyo business hours": tokyo,
               "rollover 16:55-17:10 NY": (mins >= 16 * 60 + 55) & (mins < 17 * 60 + 10),
               "after NY close 17:10-19:00 NY": (mins >= 17 * 60 + 10) & (mins < 19 * 60)}
    out = {k: {q: float(np.quantile(sp.to_numpy()[np.asarray(m)], q)) for q in (0.5, 0.9, 0.99)} | {"n": int(np.asarray(m).sum())}
           for k, m in buckets.items() if np.asarray(m).sum()}
    nfp_days = {date.fromisoformat(d) for d in H.NFP[year]}
    nfp = np.array([d in nfp_days for d in ny.date]) & (mins >= 8 * 60 + 29) & (mins < 8 * 60 + 32)
    other_fri = (ny.day_of_week == 4) & ~np.array([d in nfp_days for d in ny.date]) & (mins >= 8 * 60 + 29) & (mins < 8 * 60 + 32)
    out["payroll 08:29-08:32 NY"] = {0.5: float(np.median(sp.to_numpy()[nfp])), 0.9: float(np.quantile(sp.to_numpy()[nfp], 0.9)),
                                    0.99: float(np.quantile(sp.to_numpy()[nfp], 0.99)), "n": int(nfp.sum())}
    out["other Fridays 08:29-08:32 NY"] = {0.5: float(np.median(sp.to_numpy()[other_fri])),
                                          0.9: float(np.quantile(sp.to_numpy()[other_fri], 0.9)),
                                          0.99: float(np.quantile(sp.to_numpy()[other_fri], 0.99)), "n": int(other_fri.sum())}
    by_hour = sp.groupby(ny.hour).median()
    return out, by_hour


def main(year):
    raw = H.load(year, dedupe=False)
    ooo = out_of_order(raw)                     # on the file exactly as delivered
    n_raw, n_dup = len(raw), raw.attrs["duplicates_found"]
    del raw
    t = H.load(year)
    n = len(t)
    t = t.sort_values("file_time", kind="stable").reset_index(drop=True)
    h10 = pd.read_csv(PROJECT_ROOT / "data" / "raw" / "usdjpy" / "fred_DEXJPUS.csv", index_col=0, parse_dates=True)["DEXJPUS"]
    h10 = h10.loc[str(year)].dropna()
    tz, need = timezone_tests(t, year, h10)
    utc = H.to_utc(t["file_time"], "C")
    assert utc.max() < pd.Timestamp("%d-01-02" % (year + 1), tz="UTC") and utc.max() < pd.Timestamp("2024-01-01", tz="UTC")
    mid = H.series(utc, t["mid"])
    sp = H.series(utc, t["spread"])
    liquid, tokyo = H.session_mask(mid.index, "ldn_ny"), H.session_mask(mid.index, "tokyo")
    st = stale_runs(mid, lambda g: H.session_mask(g, "ldn_ny"))
    jp = jumps(mid)
    co = continuity(mid)
    spr, by_hour = spreads(sp, liquid, tokyo, year)
    fp1 = H.tick_hash(mid)
    fp2 = H.tick_hash(H.series(H.to_utc(t["file_time"], "C"), t["mid"]))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    c = tz["C"]
    verdict = "PASS" if c["ok"] >= need else "FAIL"
    L = ["# HistData USD/JPY %d: Phase D data-quality checks\n" % year,
         "_Run %s. Data quality only (no hypothesis, no strategy). %d ticks after removing exact duplicates. Aggregates and timestamps only; no vendor quotes. "
         "Cross-vendor confirmation (TrueFX): **BLOCKED** (files not present)._\n" % (now, n),
         "## 1. Time-zone test (rule fixed before the data were read)\n",
         "**Primary rule:** first ≥ 3-pip move 0–5 s after 08:30:00 New York on the %d payroll days; ≥ %d required. "
         "**Reading C: %d of 12 → %s.**\n" % (year, need, c["ok"], verdict),
         "| Reading | First jump 0–5 s after 08:30 (of 12) | Legacy minute rule (peak minute 08:30) | Noon-anchor median / max (pips, %d days) | Weekend-window ticks | Rollover spike at 17:00 NY (Mon–Thu) |" % c["noon_n"],
         "|---|---|---|---|---|---|"]
    for k, r in tz.items():
        L.append("| %s: %s | %d | %d of 12 | %.2f / %.2f | %d | %.0f%% |" % (k, H.READINGS[k], r["ok"], sum(m == "08:30" for m in r["minute"]),
                                                               r["noon_med"], r["noon_max"], r["weekend"], 100 * r["roll"]))
    L += ["\n| Release | US clock | EU clock | First jump, reading C (s after 08:30:00) | reading A | reading B |", "|---|---|---|---|---|---|"]
    for i, d in enumerate(H.NFP[year]):
        ts = pd.Timestamp(d + " 08:30", tz=NY)
        f = lambda v: "%.1f" % v if v is not None else "none"
        L.append("| %s | %s | %s | %s | %s | %s |" % (d, "EDT" if ts.dst() else "EST",
                                                     "summer" if ts.tz_convert("Europe/London").dst() else "winter",
                                                     f(tz["C"]["secs"][i]), f(tz["A"]["secs"][i]), f(tz["B"]["secs"][i])))
    L += ["\n## 2. Out-of-order and duplicate rows (file exactly as delivered)\n",
          "- Exact duplicate rows (same timestamp, bid and ask): %d of %d (%.4f%%). They are removed before every other check (cleaning rule)." % (
              n_dup, n_raw, 100 * n_dup / n_raw)]
    L += ["- Row %d: file time %s follows %s (step back %.0f s). Neighbouring file times: %s." % (
        r["row"], r["file_time"], r["previous_file_time"], r["step_back_s"], ", ".join(r["context"])) for r in ooo] or ["- none"]
    L += ["\n## 3. Stale quotes (inside continuous London/NY business-hour blocks, reading C)\n",
          "- Business-hour minutes: %d. Runs of ≥ 3 minutes without a mid change: %d (%d minutes, %.3f%% of business-hour minutes); of these, runs with no tick at all: %d." % (
              st["liquid_minutes"], st["runs"], st["minutes_in_runs"], 100 * st["minutes_in_runs"] / max(st["liquid_minutes"], 1), st["runs_no_tick"]),
          ("- Run length (minutes): median %.0f, 90th percentile %.0f, longest %.0f." % (st["pct"][0.5], st["pct"][0.9], st["pct"][1.0])) if st["pct"] else "- none",
          "- By New York hour of start (count): %s." % st["hours_ny"],
          "- Longest (start NY, minutes, ticks during the run): %s." % st["longest"]]
    L += ["\n## 4. Large one-minute moves (reading C)\n",
          "- One-minute mid changes analysed (consecutive minutes with ticks only; no change is measured across a gap or weekend): %d." % jp["n_minutes"],
          "- Moves > 10 robust σ (σ = 1.4826 × median absolute change, per NY hour): %d (median absolute one-minute move %.2f pips; hours with a median of 0: %d). FX one-minute moves are fat-tailed, so this count is a screen, not evidence of bad data." % (
              jp["gt10sigma"], jp["median_abs_move"], jp["zero_mad_hours"]),
          "- Moves ≥ 10 pips: %d; ≥ 20 pips: %d. Of the ≥ 10-pip moves, %d were undone by ≥ 80%% within two minutes (spike-and-revert: candidate bad ticks or genuine flash moves; only a second vendor can tell)." % (
              jp["ge10pips"], jp["ge20pips"], jp["ge10_revert"]),
          "- Largest (NY time, pips, spike-and-revert): %s." % jp["top"]]
    L += ["\n## 5. Weekday and weekend continuity (reading C)\n",
          "- Weeks: %d. First tick of the week (New York, most common): %s. Last tick: %s." % (co["weeks"], co["first_tick_times"], co["last_tick_times"]),
          "- Median ticks per weekday: %.0f; by weekday: %s." % (co["weekday_median_ticks"], {k: int(v) for k, v in co["by_weekday"].items()}),
          "- Weekdays with < 25%% of the median tick count: %s." % (co["low_days"] or "none")]
    L += ["\n## 6. Bid/ask spreads (vendor indicative quotes; NOT executable costs)\n",
          "| Window | Ticks | Median (pips) | 90th pct | 99th pct |", "|---|---|---|---|---|"]
    for k, v in spr.items():
        L.append("| %s | %d | %.2f | %.2f | %.2f |" % (k, v["n"], v[0.5], v[0.9], v[0.99]))
    L.append("\nMedian spread by New York hour (pips): %s." % ", ".join("%02d: %.2f" % (h, v) for h, v in by_hour.items()))
    cd = convention_days(t)
    L += ["\n## 8. EXPLORATORY: which clock does the file use? (not a pre-registered test)\n",
          "On Monday–Thursday days when New York and London are on different DST settings, the file-time minute of the "
          "widest daily spread (the 17:00 New York rollover) is **17:xx if the file uses New York time** and **16:xx under "
          "reading C**.\n",
          "- %d such days: %s." % (len(cd), ", ".join("%s → %s" % x for x in cd) or "none")]
    L += ["\n## 7. Reproducibility\n",
          "- Tick-level fingerprint of the transformed series (reading C, SHA-256): `%s`." % fp1,
          "- Recomputed from the raw rows in the same run: %s." % ("identical" if fp1 == fp2 else "DIFFERENT"),
          "- Raw files: SHA-256 manifest in `data/raw/histdata/usdjpy_tick_%d/manifest.json`." % year,
          "\n## Not checked here (BLOCKED)\n",
          "- Q4 cross-vendor agreement and confirmation or rejection of the large moves and stale runs need TrueFX files."]
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / ("histdata_usdjpy_%d_phaseD.md" % year)
    p.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return {"year": year, "reading_C_ok": c["ok"], "verdict": verdict, "fingerprint": fp1}


if __name__ == "__main__":
    a = sys.argv
    main(int(a[a.index("--year") + 1]))
