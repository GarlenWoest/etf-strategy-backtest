"""Study 3: long-history validation of the two near-miss families (P2 multi-asset trend, S3 time-series momentum).

Monthly data only (see tools/download_longhist.py). Assets and the series behind them:
  stocks       Ken French US market total return (Mkt-RF + RF), month-end, 1926-07+
  bonds        total return built from yields: FRED LTGOVTBD (long-term Treasuries, ~20y, monthly average) to 1953-04,
               FRED GS10 (10-year, monthly average) from 1953-05
  commodities  AQR "Commodities for the Long Run" equal-weight futures excess return + T-bill (collateral), month-end
  gold         World Bank Pink Sheet gold $/oz, MONTHLY AVERAGE; in the universe from 1971-10 (first return with both
               months after the 1971-08-15 float)
  cash         Ken French 1-month T-bill (RF)
Conventions: weights decided at a month-end close from data up to that close earn the next month's return; the
rebalance trades at that close (monthly data has no next open). Costs are charged on turnover at each rebalance.
"""
import numpy as np
import pandas as pd

from src import PROJECT_ROOT

RAW = PROJECT_ROOT / "data" / "raw" / "longhist"
ASSETS = ["stocks", "bonds", "commodities", "gold"]
END = "2018-12-31"
GOLD_START = "1971-10-31"


def _s(name):
    return pd.read_csv(RAW / ("%s.csv" % name), index_col=0, parse_dates=True).iloc[:, 0]


def bond_price(coupon, yld, years):
    n, h = 2.0 * years, yld / 2.0
    return coupon / 2.0 * (1 - (1 + h) ** (-n)) / h + (1 + h) ** (-n)


def bond_returns(yield_pct, maturity):
    y = yield_pct / 100.0
    y0 = y.shift(1)
    return (bond_price(y0, y, maturity - 1.0 / 12) - 1 + y0 / 12).dropna()


def load_returns(end=END):
    """Monthly total returns (DataFrame: stocks, bonds, commodities, gold) and the T-bill return (Series)."""
    rf = _s("tbill_kf_rf")
    stocks = _s("stocks_kf_total_return")
    lt = bond_returns(_s("fred_LTGOVTBD"), 20.0)
    g10 = bond_returns(_s("fred_GS10"), 10.0)
    bonds = pd.concat([lt.loc[:"1953-04-30"], g10.loc["1953-05-31":]])
    comm = _s("commodities_aqr_excess_return").add(rf, fill_value=np.nan).dropna()
    g = _s("gold_worldbank_usd_oz_monthly_avg")
    gold = g.pct_change().loc[GOLD_START:]
    r = pd.DataFrame({"stocks": stocks, "bonds": bonds, "commodities": comm, "gold": gold})
    r = r.loc["1926-07-31":end]
    return r, rf.reindex(r.index)


# ---------------------------------------------------------------- costs (Hurst, Ooi & Pedersen 2017, Appendix B)

COST_TABLE = {           # one-way, fraction of notional traded
    "stocks":      [(1992, 0.0034), (2002, 0.0011), (9999, 0.0007)],
    "bonds":       [(1992, 0.0006), (2002, 0.0002), (9999, 0.0007)],
    "commodities": [(1992, 0.0058), (2002, 0.0019), (9999, 0.0010)],
    "gold":        [(1992, 0.0058), (2002, 0.0019), (9999, 0.0010)],
}


def one_way_cost(asset, year):
    for last, c in COST_TABLE[asset]:
        if year <= last:
            return c


# ---------------------------------------------------------------- signals (weights decided at month-end t)

def tr_index(r):
    """Total-return index per asset; NaN before an asset's first return (it is not yet in the universe)."""
    idx = (1 + r.fillna(0)).cumprod()
    return idx.where(r.notna().cummax())


def p2_weights(r, months):
    """P2 rule: 1/k in each available asset whose month-end total-return index is above the mean of its last
    `months` month-end values (including the current one); k = assets available at t; the rest in T-bills."""
    px = tr_index(r)
    above = px > px.rolling(months, min_periods=months).mean()
    k = px.notna().sum(axis=1).replace(0, np.nan)
    return above.astype(float).div(k, axis=0).fillna(0.0)


def s3_weights(r, asset, months):
    """S3 rule, monthly: 100% in `asset` when its trailing `months`-month total return is > 0, else T-bills."""
    px = tr_index(r)[asset]
    w = pd.DataFrame(0.0, index=r.index, columns=r.columns)
    w[asset] = (px / px.shift(months) - 1 > 0).astype(float)
    return w


def equal_weight(r):
    k = r.notna().sum(axis=1)
    return r.notna().astype(float).div(k, axis=0)


def sixty_forty(r):
    w = pd.DataFrame(0.0, index=r.index, columns=r.columns)
    w["stocks"], w["bonds"] = 0.6, 0.4
    return w


def buy_and_hold(r, asset):
    w = pd.DataFrame(0.0, index=r.index, columns=r.columns)
    w[asset] = r[asset].notna().astype(float)
    return w


# ---------------------------------------------------------------- simulation

def simulate(r, rf, w, cost_mult=1.0, lag=0):
    """Monthly portfolio returns. w.loc[t] (decided at close t, optionally lagged `lag` extra months) earns r.loc[t+1].
    Rebalanced every month-end to w; turnover = sum |w_target - w_drifted| over risky assets, each side charged
    one_way_cost(asset, year of t) x cost_mult. Uninvested weight earns rf. Returns (net returns, turnover, cost)."""
    w = w.shift(lag).fillna(0.0)
    rr = r.fillna(0.0)
    cols = list(r.columns)
    years = r.index.year
    ctab = np.array([[one_way_cost(a, y) for a in cols] for y in years]) * cost_mult
    W = w[cols].to_numpy()
    R = rr.to_numpy()
    F = rf.to_numpy()
    n = len(r)
    out, turn, cst = np.full(n, np.nan), np.zeros(n), np.zeros(n)
    drift = np.zeros(len(cols))
    for t in range(n - 1):
        tgt = W[t]
        tv = np.abs(tgt - drift)
        turn[t] = tv.sum()
        cst[t] = (tv * ctab[t]).sum()
        cash = 1 - tgt.sum()
        gross = (tgt * (1 + R[t + 1])).sum() + cash * (1 + F[t + 1])
        out[t + 1] = gross * (1 - cst[t]) - 1
        val = tgt * (1 + R[t + 1])
        drift = val / gross if gross > 0 else np.zeros(len(cols))
    return pd.Series(out, r.index), pd.Series(turn, r.index), pd.Series(cst, r.index)


def sharpe(ret, rf):
    ex = (ret - rf.reindex(ret.index)).dropna()
    return float(ex.mean() / ex.std(ddof=1) * np.sqrt(12)) if ex.std(ddof=1) > 0 else float("nan")


def cagr(ret):
    ret = ret.dropna()
    return float((1 + ret).prod() ** (12 / len(ret)) - 1)


def max_dd(ret):
    e = (1 + ret.dropna()).cumprod()
    return float((e / e.cummax() - 1).min())


def worst_rolling(ret, months=120):
    """Worst annualized return over any `months`-month window, with its end month."""
    lr = np.log1p(ret.dropna())
    roll = lr.rolling(months).sum()
    ann = np.expm1(roll * 12 / months)
    return float(ann.min()), ann.idxmin()
