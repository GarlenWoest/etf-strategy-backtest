"""Phase 3 sanity check (in-sample only, 2004-11-18 to 2018-12-31).

Buy-and-hold CAGR and max drawdown for each ETF and the monthly equal-weight
portfolio: engine output vs the same numbers computed directly from the clean price
CSVs with plain pandas (no engine, no src.metrics). Plus one hand-checked trade.
Writes reports/phase3_sanity.md.

Usage: .venv/bin/python tools/sanity_in_sample.py
"""
import copy
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src import PROJECT_ROOT, load_config
from src import data as D
from src import metrics as M
from src import strategies as S
from src.engine import run_backtest

cfg = load_config()
START = cfg["dates"]["common_start"]
END = cfg["dates"]["in_sample_end"]
ETFS = cfg["instruments"]["unleveraged"] + list(cfg["instruments"]["leveraged"])
zero = copy.deepcopy(cfg)
zero["costs"]["half_spread"] = {"unleveraged": 0.0, "leveraged": 0.0}
zero["costs"]["slippage"] = 0.0
zero["capital"]["min_order_usd"] = 0.0      # isolates the arithmetic; the $1 minimum is shown separately
zero_min = copy.deepcopy(zero)
zero_min["capital"]["min_order_usd"] = cfg["capital"]["min_order_usd"]

# ---- inputs, read straight from the clean CSVs
raw = {t: pd.read_csv(PROJECT_ROOT / ("data/clean/prices/%s.csv" % t), index_col="Date",
                      parse_dates=["Date"]).loc[START:END] for t in ETFS}
idx = raw["SPY"].index
cash = pd.read_csv(PROJECT_ROOT / "data/clean/cash_rate.csv", index_col="Date",
                   parse_dates=["Date"])["daily_rate"].loc[START:END]
yrs = (idx[-1] - idx[0]).days / 365.25


def direct_cagr_mdd(path):
    """path: value series starting at 1 on idx[0]."""
    cg = path.iloc[-1] ** (1 / yrs) - 1
    mdd = (path / path.cummax() - 1).min()
    return cg, mdd


rows = []
for t in ETFS:
    p = raw[t]
    # direct: $1 at the close of day 0 (cash), invested at the open of day 1, marked at closes
    path = pd.Series(np.r_[1.0, p["Close"].iloc[1:].to_numpy() / p["Open"].iloc[1]], index=idx)
    dc, dm = direct_cagr_mdd(path)
    e0 = run_backtest(raw, S.buy_and_hold(idx, t), cash, zero, risk_layer=False).equity
    e1 = run_backtest(raw, S.buy_and_hold(idx, t), cash, cfg, risk_layer=False).equity
    src = "synthetic to %s, then real" % D.load_clean(t).query("source == 'real'").index[0].date() \
        if t in cfg["instruments"]["leveraged"] else "real"
    rows.append((t, src, dc, M.cagr(e0), M.cagr(e1), dm, M.max_drawdown(e0), M.max_drawdown(e1)))

# direct equal weight: rebalance to 25% each at the open after each month's last trading day
eq4 = cfg["instruments"]["unleveraged"]
month = idx.to_period("M")
reb_days = set(idx[1:][month[1:] != month[:-1]]) | {idx[1]}
val = np.empty(len(idx))
val[0] = 1.0
shares = None
for i, d in enumerate(idx[1:], start=1):
    if d in reb_days:
        v = 1.0 if shares is None else sum(shares[t] * raw[t].at[d, "Open"] for t in eq4)
        shares = {t: v / 4 / raw[t].at[d, "Open"] for t in eq4}
    val[i] = sum(shares[t] * raw[t].at[d, "Close"] for t in eq4)
dc, dm = direct_cagr_mdd(pd.Series(val, index=idx))
w, flag = S.equal_weight(idx, eq4)
e0 = run_backtest({t: raw[t] for t in eq4}, w, cash, zero, rebalance=flag, risk_layer=False).equity
emin = run_backtest({t: raw[t] for t in eq4}, w, cash, zero_min, rebalance=flag, risk_layer=False)
e1r = run_backtest({t: raw[t] for t in eq4}, w, cash, cfg, rebalance=flag, risk_layer=False)
n_trades_no_min = len(run_backtest({t: raw[t] for t in eq4}, w, cash, zero, rebalance=flag, risk_layer=False).trades)
rows.append(("EW 4 (monthly)", "real", dc, M.cagr(e0), M.cagr(e1r.equity), dm, M.max_drawdown(e0),
             M.max_drawdown(e1r.equity)))

# ---- hand-checked trade: SPY buy-and-hold first fill, 1x costs
r = run_backtest(raw, S.buy_and_hold(idx, "SPY"), cash, cfg, risk_layer=False)
tr = r.trades.iloc[0]
d0, d1 = idx[0], idx[1]
rate0 = cash.iloc[0]
cash_open = 100.0 * (1 + rate0)
o = raw["SPY"].at[d1, "Open"]
hs, sl = cfg["costs"]["half_spread"]["unleveraged"], cfg["costs"]["slippage"]
px_ = o * (1 + hs + sl)
q = cash_open / px_
hand = {"cash at open": cash_open, "exec price": px_, "shares": q, "notional at open": q * o,
        "half-spread $": q * o * hs, "slippage $": q * o * sl, "commission $": 0.0,
        "total paid": q * o + q * o * hs + q * o * sl}
engine = {"cash at open": float(-tr["cash_flow"]), "exec price": tr["exec_price"], "shares": tr["shares"],
          "notional at open": tr["notional_at_open"], "half-spread $": tr["half_spread_cost"],
          "slippage $": tr["slippage_cost"], "commission $": tr["commission"], "total paid": float(-tr["cash_flow"])}
# a sell from the equal-weight run: first rebalance sale
sell = e1r.trades[e1r.trades["side"] == "sell"].iloc[0]
s_hs = cfg["costs"]["half_spread"]["unleveraged"]
s_px = sell["ref_open"] * (1 - s_hs - sl)

# ---- write the report
L = []
w_ = L.append
w_("# Phase 3 sanity check (in-sample only)\n")
w_("_Window %s to %s (%d trading days, %.2f years). Risk layer off: the $1,000 switch would otherwise cap "
   "positions once a $100 account passed $1,000. Python %s, pandas %s, numpy %s, seed %s (not used)._\n"
   % (idx[0].date(), idx[-1].date(), len(idx), yrs, platform.python_version(), pd.__version__, np.__version__,
      cfg["project"]["random_seed"]))
w_("**Method:**")
w_("- **Direct:** read straight from `data/clean/prices/*.csv` with pandas: $1 bought at the open of %s "
   "(first fill after the %s close), marked at each close. The equal-weight portfolio is rebalanced to 25%% "
   "each at the open after every month's last trading day. Computed independently of `src/engine.py` and "
   "`src/metrics.py`." % (d1.date(), d0.date()))
w_("- **Engine (no costs):** `run_backtest` with half-spread, slippage and the $1 minimum order set to 0. The "
   "only difference from Direct is one night of T-bill interest on the starting cash before the first fill.")
w_("- **Engine (1x costs):** the normal configuration (costs and the $1 minimum order), shown for information.\n")
w_("| Instrument | Data | CAGR direct | CAGR engine (no costs) | CAGR engine (1x costs) | Max DD direct | "
   "Max DD engine (no costs) | Max DD engine (1x costs) |")
w_("|---|---|---|---|---|---|---|---|")
for t, src, dc, c0, c1, dm, m0, m1 in rows:
    w_("| %s | %s | %.2f%% | %.2f%% | %.2f%% | %.2f%% | %.2f%% | %.2f%% |" %
       (t, src, dc * 100, c0 * 100, c1 * 100, dm * 100, m0 * 100, m1 * 100))
dcg = max(abs(r_[2] - r_[3]) for r_ in rows)
ddd = max(abs(r_[5] - r_[6]) for r_ in rows)
match = all(round(r_[2] * 100, 2) == round(r_[3] * 100, 2) and round(r_[5] * 100, 2) == round(r_[6] * 100, 2)
            for r_ in rows)
w_("\n**Largest gap, direct vs engine (no costs): CAGR %.5f percentage points, max drawdown %.5f percentage "
   "points. Match at 2-decimal rounding on every row: %s.**\n" % (dcg * 100, ddd * 100, "YES" if match else "NO"))
w_("**Effect of the $1 minimum order (equal weight, no costs):** with the minimum on, the engine skips rebalance "
   "trades under $1, which is about half of them on a $100 account (%d trades vs %d without the minimum). "
   "Weights drift between rebalances, giving CAGR %.2f%% and max drawdown %.2f%% instead of %.2f%% and %.2f%%. "
   "This is the realistic behavior of a $100 account, not an engine error. The 1x-costs column includes it.\n"
   % (len(emin.trades), n_trades_no_min, M.cagr(emin.equity) * 100, M.max_drawdown(emin.equity) * 100,
      M.cagr(e0) * 100, M.max_drawdown(e0) * 100))
w_("Leveraged ETFs use the spliced clean series: synthetic (with calibrated extra cost) before launch, real "
   "after. These are not trial results. They are benchmarks, and in-sample only.\n")
w_("## Hand-checked trade: first SPY buy (1x costs)\n")
w_("Signal: buy-and-hold target 100%% SPY, decided at the close of %s. Executed at the open of %s." % (d0.date(), d1.date()))
w_("\n| Line | By hand | Engine |\n|---|---|---|")
w_("| Starting cash | $100.000000 | |")
w_("| Overnight T-bill interest: rate(%s) = IRX %.3f%% / 100 / 252 = %.8f | +$%.6f | |"
   % (d0.date(), rate0 * 252 * 100, rate0, 100 * rate0))
for k in hand:
    w_("| %s | %s | %s |" % (k, ("%.6f" % hand[k]), ("%.6f" % engine[k])))
w_("\nArithmetic:")
w_("- Open = %.6f (adjusted). Cost rate = half-spread %.2f%% + slippage %.2f%% = %.2f%%." % (o, hs * 100, sl * 100, (hs + sl) * 100))
w_("- Execution price = %.6f × 1.0007 = %.6f." % (o, px_))
w_("- Shares = %.6f / %.6f = %.6f (fractional)." % (cash_open, px_, q))
w_("- Half-spread cost = shares × open × 0.0002 = $%.6f. Slippage = shares × open × 0.0005 = $%.6f. "
   "Commission = $0." % (q * o * hs, q * o * sl))
w_("- Check: notional + half-spread + slippage + commission = $%.6f = cash spent." % hand["total paid"])
w_("- Cash after the fill: $%.6f." % r.cash.iloc[1])
w_("\n**Sell side (from the equal-weight run):** %s sold %.6f %s at open %.6f. Execution price = open × (1 − 0.0007) "
   "= %.6f (engine %.6f). Half-spread $%.6f, slippage $%.6f, commission $0, net proceeds $%.6f."
   % (sell["date"].date(), sell["shares"], sell["ticker"], sell["ref_open"], s_px, sell["exec_price"],
      sell["half_spread_cost"], sell["slippage_cost"], sell["cash_flow"]))
ok = all(abs(hand[k] - engine[k]) < 1e-9 for k in hand) and abs(s_px - sell["exec_price"]) < 1e-9
w_("\nHand calculation equals the engine record on every line: **%s**." % ("yes" if ok else "NO"))
(PROJECT_ROOT / "reports" / "phase3_sanity.md").write_text("\n".join(L) + "\n")
print("\n".join(L))
