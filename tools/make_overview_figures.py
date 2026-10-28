"""Figures for reports/PROJECT_OVERVIEW.md: two diagrams and three charts in one consistent style.

Charts read only the frozen results files (results/*.csv); nothing is re-run and nothing is logged.
Usage: .venv/bin/python -I tools/make_overview_figures.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RES, OUT = ROOT / "results", ROOT / "reports" / "figures"
GOLD, BLUE, GREY, RED, INK, LIGHT = "#8a6d1f", "#1f4e8a", "#9a9a9a", "#b03a2e", "#1a1a1a", "#f3efe4"
plt.rcParams.update({"font.family": "Helvetica", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#555", "axes.titleweight": "bold", "axes.titlesize": 10, "savefig.dpi": 200})


def box(ax, x, y, w, h, text, fc=LIGHT, ec=GOLD, fs=8, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.015", fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=INK,
            fontweight="bold" if bold else "normal", linespacing=1.25)


def arrow(ax, x0, y0, x1, y1, color=GREY):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color=color, lw=1.2))


def pipeline():
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    ax.set_xlim(0, 1), ax.set_ylim(0, 1), ax.axis("off")
    steps = [("1. Write down\nthe rules first", "pre-registration,\nfrozen in git"),
             ("2. Fit on\nolder data", "in-sample period\n(tuning only)"),
             ("3. Test on\nlater data", "validation period,\nwalk-forward"),
             ("4. Correct\nfor luck", "Deflated Sharpe\nfor all trials so far"),
             ("5. Apply\nkill rules", "K1–K7, mechanical;\nfails one = killed")]
    w, h, gap = 0.17, 0.30, 0.0325
    for i, (t, s) in enumerate(steps):
        x = 0.01 + i * (w + gap)
        box(ax, x, 0.52, w, h, t, bold=True, fs=8.5)
        ax.text(x + w / 2, 0.43, s, ha="center", va="top", fontsize=7.2, color="#444", linespacing=1.2)
        if i:
            arrow(ax, x - gap + 0.003, 0.67, x - 0.003, 0.67)
    box(ax, 0.01, 0.02, 0.56, 0.15, "Locked holdout: 2024 onward, never opened or downloaded", fc="#fbeaea", ec=RED, fs=8, bold=True)
    box(ax, 0.60, 0.02, 0.39, 0.15, "Every run, pass or fail,\ngoes in the research log", fc="#eaf0f8", ec=BLUE, fs=8)
    fig.savefig(OUT / "overview_pipeline.png", bbox_inches="tight")
    plt.close(fig)


def architecture():
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.set_xlim(0, 1), ax.set_ylim(0, 1), ax.axis("off")
    ax.text(0.01, 0.97, "RESEARCH (historical data up to 2023)", fontsize=8, color=GOLD, fontweight="bold")
    ax.text(0.53, 0.97, "MONITORING (today's data; never enters research)", fontsize=8, color=BLUE, fontweight="bold")
    ax.plot([0.505, 0.505], [0.18, 0.97], color="#ccc", lw=1, ls="--")
    L = [(0.01, 0.80, "Data checks\nvendor tests, hashes"), (0.25, 0.80, "Market clock\nholidays, sessions"),
         (0.01, 0.60, "Research engine\nETFs, commodities,\nlong history"), (0.25, 0.60, "FX engine v2\ncurrency balances,\nhard 1x cap"),
         (0.01, 0.40, "Source library\n234 sources,\nreading depth"), (0.25, 0.40, "Research memory\nhash-chained ledger")]
    for x, y, t in L:
        box(ax, x, y, 0.21, 0.13, t, fs=7.5)
    R = [(0.53, 0.80, "Market snapshot\nfreshness-checked\nprices", "#eaf0f8"),
         (0.77, 0.80, "Event monitor\nofficial release\ncalendars", "#eaf0f8"),
         (0.53, 0.60, "Watchlist signals\nfailed strategies,\nlabelled as such", "#eaf0f8"),
         (0.77, 0.60, "Paper books\nfictional $100 each", "#eaf0f8"),
         (0.53, 0.40, "Weekly brief\ninformational only", "#eaf0f8"),
         (0.77, 0.40, "Heartbeat\nrun and alert records", "#eaf0f8")]
    for x, y, t, c in R:
        box(ax, x, y, 0.21, 0.13, t, fc=c, ec=BLUE, fs=7.5)
    arrow(ax, 0.115, 0.80, 0.115, 0.735), arrow(ax, 0.355, 0.80, 0.355, 0.735)
    arrow(ax, 0.115, 0.60, 0.115, 0.535), arrow(ax, 0.355, 0.60, 0.355, 0.535)
    arrow(ax, 0.742, 0.665, 0.768, 0.665, BLUE)
    box(ax, 0.01, 0.20, 0.46, 0.12, "Results: research log, reports, public code repository", fc="#ffffff", fs=7.5)
    arrow(ax, 0.24, 0.40, 0.24, 0.325)
    box(ax, 0.53, 0.20, 0.46, 0.12, "Scheduled tasks: weekdays 16:45 ET, Sundays 18:00 ET\nprivate backup of monitoring files only",
        fc="#ffffff", ec=BLUE, fs=7)
    arrow(ax, 0.76, 0.40, 0.76, 0.325, BLUE)
    box(ax, 0.01, 0.02, 0.98, 0.11, "Not connected to any broker. No real money. No orders can be placed.", fc="#fbeaea", ec=RED, fs=8.5, bold=True)
    fig.savefig(OUT / "overview_architecture.png", bbox_inches="tight")
    plt.close(fig)


def dsr_chart():
    s1 = pd.read_csv(RES / "phase5_metrics.csv")
    s2 = pd.read_csv(RES / "commodities_phase5_metrics.csv")
    s3 = pd.read_csv(RES / "study3_metrics.csv").rename(columns={"Unnamed: 0": "test_id"})
    s4 = pd.read_csv(RES / "usdjpy_study1_metrics.csv")
    sets = [("Study 1\nETFs (92)", s1), ("Study 2\nCommodities (26)", s2), ("Study 3\n1927–2018 (16)", s3), ("Study 4\nUSD/JPY (8)", s4)]
    fig, ax = plt.subplots(figsize=(7.0, 3.1))
    for i, (lab, d) in enumerate(sets):
        d = d[d.test_id.astype(str).str.startswith("V")]
        y = d.dsr.astype(float).values
        jit = ((pd.Series(range(len(y))) * 0.6180339) % 1 - 0.5).values * 0.5
        ax.scatter(i + jit, y, s=14, color=GOLD if i != 2 else GREY, alpha=0.8, edgecolor="none")
    ax.axhline(0.95, color=RED, lw=1.2, ls="--")
    ax.text(3.45, 0.965, "pass mark 0.95", color=RED, fontsize=8, ha="right")
    ax.annotate("Study 3: over 90 years almost any diversified\nrule clears this mark; it was decided by\nits era and robustness checks instead",
                xy=(2.2, 0.93), xytext=(2.45, 0.62), fontsize=7.2, color="#444", arrowprops=dict(arrowstyle="-", color=GREY))
    ax.set_xticks(range(4), [s[0] for s in sets]), ax.set_ylim(-0.02, 1.05), ax.set_xlim(-0.5, 3.5)
    ax.set_ylabel("Deflated Sharpe (probability)")
    ax.set_title("Each pre-registered trial's luck-adjusted score", loc="left")
    fig.savefig(OUT / "overview_dsr_all_trials.png", bbox_inches="tight")
    plt.close(fig)


def sharpe_hist():
    d = pd.read_csv(RES / "phase5_metrics.csv")
    v = d[d.test_id.str.startswith("V")].val_sharpe.astype(float)
    ew = float(d[d.test_id == "B09"].val_sharpe.iloc[0]) if (d.test_id == "B09").any() else None
    fig, ax = plt.subplots(figsize=(7.0, 2.9))
    ax.hist(v, bins=24, color=GOLD, alpha=0.85, edgecolor="white")
    ax.set_ylim(0, 9)
    ax.axvline(0.71, color="#666", lw=1.3, ls="--", label="best Sharpe expected from luck alone with 92 trials (about 0.71)")
    if ew is not None:
        ax.axvline(ew, color=BLUE, lw=1.3, ls="--", label="equal-weight portfolio, no rules (%.2f)" % ew)
    ax.axvline(v.max(), color=RED, lw=1.3, ls="--", label="best trial (%.2f): above luck, but not by enough" % v.max())
    ax.legend(loc="upper left", fontsize=7.3, frameon=False)
    ax.set_xlabel("Sharpe ratio in the 2019–2023 test period (higher = more return per unit of risk)")
    ax.set_ylabel("number of trials")
    ax.set_title("Study 1: the 92 ETF trials on data they were not tuned on", loc="left")
    fig.savefig(OUT / "overview_study1_sharpe.png", bbox_inches="tight")
    plt.close(fig)
    return ew


def risk_return():
    d = pd.read_csv(RES / "study3_metrics.csv").rename(columns={"Unnamed: 0": "test_id"})
    fig, ax = plt.subplots(figsize=(7.0, 3.1))
    names = {"V119": "trend 6-mo (V119)", "V122": "trend 12-mo (V122)", "L05": "equal weight", "L06": "60/40 stocks/bonds",
             "L01": "stocks only", "L02": "bonds only", "L03": "commodities only", "L04": "gold only (from 1971)"}
    for _, r in d.iterrows():
        tid = r.test_id
        x, y = -100 * float(r.full_max_dd), 100 * float(r.full_cagr)
        p2 = tid in ("V119", "V120", "V121", "V122")
        c = GOLD if p2 else (BLUE if tid.startswith("L") else GREY)
        ax.scatter(x, y, s=34 if (p2 or tid.startswith("L")) else 16, color=c, edgecolor="none", zorder=3)
        if tid in names:
            ax.annotate(names[tid], (x, y), xytext=(5, 4 if tid not in ("V119", "L04") else -9), textcoords="offset points", fontsize=7.3, color=c)
    ax.set_xlabel("worst fall from a peak, 1927–2018 (%)")
    ax.set_ylabel("average yearly return (%)")
    ax.set_title("Study 3: trend rules cut the worst fall, not the return", loc="left")
    ax.text(0.99, 0.04, "gold = multi-asset trend trials · grey = single-asset momentum trials · blue = benchmarks",
            transform=ax.transAxes, ha="right", fontsize=7, color="#555")
    fig.savefig(OUT / "overview_study3_risk_return.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    pipeline(), architecture(), dsr_chart()
    print("equal weight val Sharpe:", sharpe_hist())
    risk_return()
    print("wrote", sorted(p.name for p in OUT.glob("overview_*.png")))
