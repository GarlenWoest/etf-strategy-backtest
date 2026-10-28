"""Write reports/data_quality.md and reports/synthetic_vs_real.png from data/clean/build_meta.json.

Usage: .venv/bin/python tools/make_data_report.py
"""
import json
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src import PROJECT_ROOT, load_config
from src import data as D

cfg = load_config()
build = json.load(open(D.clean_dir(cfg) / "build_meta.json"))
dl = json.load(open(D.raw_dir(cfg) / "download_meta.json"))
rep = PROJECT_ROOT / "reports"

# chart: real vs synthetic growth on the overlap
fig, axes = plt.subplots(2, 2, figsize=(11, 7))
for ax, (t, spec) in zip(axes.flat, cfg["instruments"]["leveraged"].items()):
    real = D.load_raw(t)["Close"]
    under = D.load_clean(spec["underlying"])
    syn = D.synthetic_ohlc(under, D.load_cash(), spec["leverage"], spec["expense_ratio"],
                          extra_drag=build["extra_drag"][t]["annual"])["Close"]
    syn = syn.reindex(real.index)
    ax.plot(real / real.iloc[0], label="real %s" % t, color="#1f4e79", lw=1.2)
    ax.plot(syn / syn.iloc[0], label="synthetic %dx %s" % (spec["leverage"], spec["underlying"]),
            color="#c55a11", lw=1.0, alpha=0.9)
    ax.set_yscale("log")
    ax.set_title("%s: growth of 1 from %s" % (t, real.index[0].date()), fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
fig.suptitle("Synthetic vs real leveraged ETFs (overlap through 2023-12-29, log scale)")
fig.tight_layout()
fig.savefig(rep / "synthetic_vs_real.png", dpi=110)

L = []
w = L.append
w("# Data quality report (Phase 2)\n")
w("_Generated %s. Holdout (2024-01-01 onward) not downloaded: holdout_locked = true._\n" % build["built_at_utc"])
w("## Provenance\n")
w("| Item | Value |\n|---|---|")
w("| Source | %s (auto_adjust=True: open, high, low, close all split- and dividend-adjusted) |" % dl["source"])
w("| Downloaded (UTC) | %s |" % dl["downloaded_at_utc"])
w("| Range requested | %s to %s (exclusive) |" % (dl["start"], dl["end_exclusive"]))
w("| yfinance | %s |" % dl["yfinance_version"])
w("| Python / pandas / numpy | %s / %s / %s |" % (platform.python_version(), pd.__version__, __import__("numpy").__version__))
w("| Random seed | %s (not used in Phase 2) |" % cfg["project"]["random_seed"])
w("| Calendar | %s, %s to %s, %d days |" % (build["calendar"]["source"], build["calendar"]["first"],
                                          build["calendar"]["last"], build["calendar"]["days"]))
w("\nRaw file hashes are in `data/raw/download_meta.json`; clean file hashes in `data/clean/build_meta.json`.\n")
w("**Caveat on adjusted prices:** Yahoo adjusts history for dividends paid later, including after 2023. "
  "Levels before 2024 may therefore be rescaled by holdout-period dividends. Returns are unaffected except for "
  "that scaling, and no holdout prices are in the data.\n")

w("## Raw downloads\n")
w("| File | Rows | First | Last |\n|---|---|---|---|")
for k, v in dl["files"].items():
    w("| %s | %d | %s | %s |" % (k, v["rows"], v["first"], v["last"]))

w("\n## Validation results\n")
w("Checked: duplicate dates, NaN prices, zero or negative prices, OHLC consistency, missing trading days "
  "against the SPY calendar, single-day moves over 10% (flagged, kept), and runs of 3+ identical closes.\n")
w("**No duplicates, no NaNs, no zero or negative prices, no OHLC inconsistencies, no missing days.**\n")
w("| Ticker | Check | Count | First dates | Note |\n|---|---|---|---|---|")
for i in build["issues"]:
    w("| %s | %s | %d | %s | %s |" % (i["ticker"], i["check"], i["count"], ", ".join(i["dates"][:6]) +
                                     (" ..." if i["count"] > 6 else ""), i["detail"]))
w("\n**Suspected stale prices (flagged, not changed):**")
w("- QQQ showed the same unadjusted close on three consecutive days (2012-08-27, -28 and -29), with different volumes and ranges each day. "
  "On 08-29 the open also equals that close.")
w("- UGL showed the same close on three consecutive trading days (2018-05-18, -21 and -22), with different volumes.")
w("- Both look like Yahoo data errors. **Status: UNRESOLVED.** No second source was available, so they could not "
  "be confirmed or fixed, and the clean data keeps Yahoo's values unchanged.")
w("- **Phase 5 safeguard (user instruction):** every surviving strategy is run twice: once as is, and once with "
  "closes in these windows (QQQ 2012-08-27 to 2012-08-29, UGL 2018-05-18 to 2018-05-22) replaced by linear "
  "interpolation between the neighboring good closes (`src/data.interpolate_suspects`). Any change in results is "
  "reported.\n")
w("**Large moves:** every >10% move falls on a known market event (Sep–Oct 2008, May 2010, Aug 2011, Apr–Jun 2013 "
  "gold crash, Aug 2015, Jun 2016 Brexit, Mar 2020) or is a 2x/3x fund amplifying one. All are kept.\n")

w("## Cash rate (^IRX)\n")
cr = build["cash_rate"]
w("- Daily rate = (IRX / 100) / 252 on SPY trading days.")
w("- Forward-filled on %d ETF trading days where IRX had no print (bond-market holidays): %s." %
  (len(cr["forward_filled_dates"]), ", ".join(cr["forward_filled_dates"])))
w("- Negative T-bill yields on %d days (%s to %s). These are real market prints and kept as is." %
  (len(cr["negative_rate_dates"]), cr["negative_rate_dates"][0], cr["negative_rate_dates"][-1]))

w("\n## Synthetic leveraged series\n")
w("Formula: r = L × r_underlying − expense_ratio/252 − (L − 1) × prior-day daily T-bill rate − extra_drag/252. "
  "Open, high and low map the underlying's move from the prior close at L× exposure. Real fund data is used from "
  "its first Yahoo date; before that the synthetic series is scaled to join without a jump.\n")
w("| Fund | L | Expense ratio | Real data from | Synthetic before |\n|---|---|---|---|---|")
for t, s in cfg["instruments"]["leveraged"].items():
    w("| %s | %d | %.2f%% | %s | %s back to %s |" % (t, s["leverage"], s["expense_ratio"] * 100,
                                                    build["leveraged_real_start"][t], s["underlying"],
                                                    cfg["dates"]["common_start"]))
w("\n### Calibration: extra annual cost (user decision, option ii)\n")
w("Real funds lagged the plain formula. Per fund, extra_drag = mean daily (synthetic − real) return × 252, "
  "measured **only on the overlap through %s** (in-sample). It is then charged as extra_drag/252 per day "
  "on the whole synthetic history. Validation and holdout data play no part.\n" % cfg["dates"]["in_sample_end"])
w("| Fund | Calibration window | Days | Extra drag (per year) |\n|---|---|---|---|")
for t, d in build["extra_drag"].items():
    w("| %s | %s to %s | %d | %.2f%% |" % (t, build["leveraged_real_start"][t], d["calibration_end"],
                                          d["calibration_days"], d["annual"] * 100))
w("\n### Tracking over the full overlap (daily close-to-close returns)\n")
w("| Fund | Overlap | Correlation | Tracking error (ann.) | Real CAGR | Formula CAGR (no drag) | Calibrated CAGR | Overnight corr. |")
w("|---|---|---|---|---|---|---|---|")
for t, s_ in build["tracking"].items():
    u = build["tracking_uncalibrated"][t]
    w("| %s | %s to %s | %.4f | %.2f%% | %.2f%% | %.2f%% | %.2f%% | %.4f |" % (
        t, s_["start"], s_["end"], s_["correlation"], s_["tracking_error_ann"] * 100, s_["cagr_real"] * 100,
        u["cagr_syn"] * 100, s_["cagr_syn"] * 100, s_["overnight_corr"]))
w("\n**Check on years not used for calibration (2019–2023):**\n")
w("| Fund | Real CAGR | Calibrated synthetic CAGR | Gap |\n|---|---|---|---|")
for t, o in build["tracking_2019_2023"].items():
    w("| %s | %.2f%% | %.2f%% | %+.2f pp |" % (t, o["cagr_real"] * 100, o["cagr_syn"] * 100,
                                            (o["cagr_syn"] - o["cagr_real"]) * 100))
gaps = {t: (o["cagr_syn"] - o["cagr_real"]) * 100 for t, o in build["tracking_2019_2023"].items()}
opt = {t: g for t, g in gaps.items() if g > 0}
pes = {t: g for t, g in gaps.items() if g <= 0}
w("\nAfter calibration, the full-overlap CAGR gap is small. In 2019–2023 (not used for calibration) the calibrated "
  "synthetic was too optimistic for %s and too pessimistic for %s. **This was not re-tuned:** that would use "
  "validation data. The pre-launch synthetic history (2004 to 2008–2010) therefore carries an error of about a point "
  "a year in either direction, stated here.\n" % (
      ", ".join("%s (%+.2f pp/yr)" % (t, g) for t, g in opt.items()) or "none",
      ", ".join("%s (%+.2f pp/yr)" % (t, g) for t, g in pes.items()) or "none"))
w("![Synthetic vs real](synthetic_vs_real.png)\n")
w("_Chart shows the calibrated synthetic series._\n")

w("## Cross-check against a second source (Stooq)\n")
cc_path = D.clean_dir(cfg) / "crosscheck.json"
if cc_path.exists():
    cc = json.load(open(cc_path))
    w("Stooq daily CSVs were downloaded by the user in a browser and truncated by `tools/truncate_holdout.py` "
      "before anything read them. Rows on or after %s were dropped and the originals deleted. "
      "Mismatch flag: %.1f%%.\n" % (cfg["dates"]["holdout_start"], cfg["data"]["crosscheck_mismatch_flag"] * 100))
    w("| Ticker | Stooq range | Common days | Matches Yahoo | Median abs. diff | Days > flag | Max diff (date) |")
    w("|---|---|---|---|---|---|---|")
    for t, r in cc["results"].items():
        b = r["compare"][r["basis"]]
        w("| %s | %s to %s | %d | %s | %.4f%% | %d | %.2f%% (%s) |" % (
            t, r["stooq_first"], r["stooq_last"], b["days"], r["basis"], b["median_abs_dev"] * 100,
            len(b["mismatch_dates"]), b["max_abs_dev"] * 100, b["max_abs_dev_date"]))
    for line in cc.get("notes", []):
        w("- " + line)
    w("")
else:
    w("**Skipped (user decision 2026-10-22, option C).** Stooq's CSV endpoint now serves a JavaScript bot-verification "
      "page instead of data, and no other free source was judged worth the trouble. All prices therefore rest on a "
      "single source (Yahoo Finance via yfinance). The Phase 3 unit tests and the Phase 5 suspect-price sensitivity run "
      "are the remaining safeguards.\n")
w("## Expense ratios used\n")
for t, s in cfg["instruments"]["leveraged"].items():
    w("- **%s:** %.2f%% (%s)" % (t, s["expense_ratio"] * 100, s["source"]))
w("\nToday's expense ratios are applied to the whole synthetic history. This is an approximation.\n")
(rep / "data_quality.md").write_text("\n".join(L) + "\n")
print("wrote", rep / "data_quality.md")
