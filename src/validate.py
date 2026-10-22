"""Phase 5 validation tools: trade statistics, walk-forward, bootstrap, Deflated Sharpe Ratio.

Definitions used throughout (documented in reports/phase5_validation.md):
  - Out-of-sample (OOS) for a fixed variant = the validation window 2019-01-01..2023-12-31,
    sliced from one continuous run that starts at dates.evaluation_start (positions carry
    over from 2018 exactly as they would live). Walk-forward results are reported per
    strategy group alongside.
  - A trade = one holding episode in one instrument: from the fill that takes its shares
    above zero to the fill that takes them back to zero. Top-ups and trims inside an
    episode belong to it. Episodes are assigned to the window that contains their exit;
    an episode still open at the window end is marked to market at the last close.
"""
import math

import numpy as np
import pandas as pd
from scipy import stats

from src import metrics as M

EULER_GAMMA = 0.5772156649015329


# ---------------------------------------------------------------- trades

def trade_episodes(result, prices):
    """List of dicts {ticker, entry, exit, cost, proceeds, pnl, ret, open} from an engine Result."""
    eps = []
    tr = result.trades.sort_values(["date"], kind="stable")
    for t, g in tr.groupby("ticker", sort=False):
        sh, cost, proc, entry = 0.0, 0.0, 0.0, None
        for _, r in g.iterrows():
            if r["side"] == "buy":
                if sh <= 1e-12:
                    entry, cost, proc = r["date"], 0.0, 0.0
                sh += r["shares"]
                cost += -r["cash_flow"]
            else:
                sh -= r["shares"]
                proc += r["cash_flow"]
                if sh <= 1e-9:
                    sh = 0.0
                    eps.append({"ticker": t, "entry": entry, "exit": r["date"], "cost": cost, "proceeds": proc,
                                "pnl": proc - cost, "ret": (proc - cost) / cost if cost > 0 else np.nan, "open": False})
                    entry = None
        if sh > 1e-12 and entry is not None:
            last = result.equity.index[-1]
            mv = sh * prices[t].at[last, "Close"]
            eps.append({"ticker": t, "entry": entry, "exit": last, "cost": cost, "proceeds": proc + mv,
                        "pnl": proc + mv - cost, "ret": (proc + mv - cost) / cost, "open": True})
    return eps


def trade_stats(episodes, start, end):
    e = [x for x in episodes if pd.Timestamp(start) <= x["exit"] <= pd.Timestamp(end)]
    wins = [x["ret"] for x in e if x["pnl"] > 0]
    losses = [x["ret"] for x in e if x["pnl"] <= 0]
    gp = sum(x["pnl"] for x in e if x["pnl"] > 0)
    gl = -sum(x["pnl"] for x in e if x["pnl"] < 0)
    return {"n_round_trips": len(e), "n_completed": sum(not x["open"] for x in e),
            "win_rate": len(wins) / len(e) if e else float("nan"),
            "avg_win": float(np.mean(wins)) if wins else float("nan"),
            "avg_loss": float(np.mean(losses)) if losses else float("nan"),
            "profit_factor": gp / gl if gl > 0 else (float("inf") if gp > 0 else float("nan"))}


def window_metrics(result, prices, cash, start, end, episodes=None):
    """Every Phase 5 metric for one window of a continuous run."""
    e = result.equity.loc[start:end]
    # start the window from the prior close so the first day's return is included
    prior = result.equity.loc[:start].iloc[:-1]
    if len(prior):
        e = pd.concat([prior.iloc[[-1]], e])
    w = result.weights.loc[start:end]
    tr = result.trades[(result.trades["date"] >= pd.Timestamp(start)) & (result.trades["date"] <= pd.Timestamp(end))]
    avg_eq = float(e.mean())
    yrs = M.years(e.index)
    out = M.summary(e, cash)
    out.update({"time_in_market": float((w.sum(axis=1) > 0.01).mean()),
                "turnover_per_year": float(tr["notional_at_open"].sum() / avg_eq / yrs) if yrs > 0 else float("nan"),
                "costs_paid_usd": float((tr["half_spread_cost"] + tr["slippage_cost"] + tr["commission"]).sum()),
                "costs_pct_of_avg_equity_per_year": float((tr["half_spread_cost"] + tr["slippage_cost"]).sum()
                                                          / avg_eq / yrs) if yrs > 0 else float("nan"),
                "fill_days": int(tr["date"].nunique()),
                "total_return": float(e.iloc[-1] / e.iloc[0] - 1)})
    if episodes is None:
        episodes = trade_episodes(result, prices)
    out.update(trade_stats(episodes, start, end))
    return out


def period_path(equity, start, end):
    """Equity over [start, end] rescaled to $100 at the close before start."""
    prior = equity.loc[:start].iloc[:-1]
    e = equity.loc[start:end]
    base = prior.iloc[-1] if len(prior) else e.iloc[0]
    path = pd.concat([prior.iloc[[-1]], e]) if len(prior) else e
    return 100.0 * path / base


# ---------------------------------------------------------------- walk-forward

def walk_forward(returns, cash, first_test_year, last_test_year, train_years=5):
    """returns: DataFrame of daily returns, one column per parameter value of ONE group.
    For each test year Y pick the column with the highest Sharpe over the previous
    train_years calendar years, then use its returns in Y. Returns (stitched daily returns,
    {Y: chosen column}). Ties go to the first column. Switching parameters at a year boundary
    is assumed costless (the continuous runs already carry their own trading costs)."""
    pieces, chosen = [], {}
    for y in range(first_test_year, last_test_year + 1):
        tr = returns.loc["%d-01-01" % (y - train_years):"%d-12-31" % (y - 1)]
        rf = cash.shift(1).reindex(tr.index).fillna(0.0)
        ex = tr.sub(rf, axis=0)
        sh = ex.mean() / ex.std()
        best = sh.idxmax()
        chosen[y] = best
        pieces.append(returns.loc["%d-01-01" % y:"%d-12-31" % y, best])
    return pd.concat(pieces), chosen


def sharpe_from_returns(r, cash):
    ex = r - cash.shift(1).reindex(r.index).fillna(0.0)
    return float(ex.mean() / ex.std() * np.sqrt(252)) if ex.std() > 0 else float("nan")


# ---------------------------------------------------------------- bootstrap and DSR

def bootstrap_sharpe_ci(excess, n_resamples, seed, alpha=0.05, chunk=1000):
    """Percentile CI of the annualized Sharpe from i.i.d. resampling of daily excess returns."""
    x = np.asarray(excess, float)
    rng = np.random.default_rng(seed)
    out = np.empty(n_resamples)
    for s in range(0, n_resamples, chunk):
        m = min(chunk, n_resamples - s)
        b = x[rng.integers(0, len(x), size=(m, len(x)))]
        sd = b.std(axis=1, ddof=1)
        out[s:s + m] = np.where(sd > 0, b.mean(axis=1) / sd * np.sqrt(252), np.nan)
    return float(np.nanpercentile(out, 100 * alpha / 2)), float(np.nanpercentile(out, 100 * (1 - alpha / 2)))


def expected_max_sharpe(var_sr, n_trials):
    """Bailey & Lopez de Prado (2014): expected maximum of n_trials Sharpe estimates under
    the null of zero true Sharpe, given the cross-trial variance var_sr (same units as SR)."""
    z = stats.norm.ppf
    return math.sqrt(var_sr) * ((1 - EULER_GAMMA) * z(1 - 1.0 / n_trials)
                                + EULER_GAMMA * z(1 - 1.0 / (n_trials * math.e)))


def probabilistic_sharpe(sr, sr_benchmark, t, skew, kurt):
    """PSR: probability that the true (per-period) Sharpe exceeds sr_benchmark.
    sr in per-period units (daily), kurt = ordinary (non-excess) kurtosis."""
    den = 1 - skew * sr + (kurt - 1) / 4.0 * sr ** 2
    return float(stats.norm.cdf((sr - sr_benchmark) * math.sqrt(t - 1) / math.sqrt(den)))


def deflated_sharpe(excess, all_daily_sharpes, n_trials):
    """DSR for one strategy's daily excess returns, deflated for n_trials with the
    cross-trial variance of daily Sharpe estimates all_daily_sharpes."""
    x = np.asarray(excess, float)
    sr = x.mean() / x.std(ddof=1)
    sr0 = expected_max_sharpe(float(np.var(all_daily_sharpes, ddof=1)), n_trials)
    return probabilistic_sharpe(sr, sr0, len(x), float(stats.skew(x)), float(stats.kurtosis(x, fisher=False))), sr0


def effective_trials(returns):
    """Participation-ratio estimate of the number of independent trials from the
    correlation matrix of trial returns: (sum eigenvalues)^2 / sum(eigenvalues^2)."""
    c = np.corrcoef(np.asarray(returns, float).T)
    ev = np.linalg.eigvalsh(np.nan_to_num(c))
    return float(ev.sum() ** 2 / (ev ** 2).sum())


# ---------------------------------------------------------------- Phase 7A Monte Carlo

def monte_carlo(ret, cash_rate, size, monthly, cap_after, cfg, n_paths, block, years, seed):
    """Block-bootstrap Monte Carlo of a $100 account.

    ret, cash_rate : aligned arrays of daily strategy returns and daily T-bill rates (one sample
                     period); resampled jointly in circular blocks of `block` days.
    size           : fraction of the account in the strategy below the target (rest earns T-bills),
                     held constant every day.
    monthly        : dollars added every 21 trading days (after that day's ruin check).
    cap_after      : strategy exposure once the target has been reached (Phase 7B caps); the
                     Phase 7B kill switch (drawdown from the post-switch peak) moves the account
                     to cash for good. The 2% per-trade rule is not modelled (not designed yet).
    Paths are not stopped at $20 or at the target: they keep running for the value-at-horizon
    figures; first-passage events are recorded separately.
    Returns a dict of arrays/statistics.
    """
    ret = np.asarray(ret, float)
    rc = np.asarray(cash_rate, float)
    T = len(ret)
    n_days = int(round(years * 252))
    start_cap = float(cfg["capital"]["starting_usd"])
    target = float(cfg["capital"]["target_usd"])
    ruin = float(cfg["capital"]["ruin_usd"])
    kill = float(cfg["risk"]["phase_7b"]["drawdown_kill_from_post_threshold_peak"])
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, T, size=(n_paths, n_days // block + 1))
    eq = np.full(n_paths, start_cap)
    switched = np.zeros(n_paths, bool)
    killed = np.zeros(n_paths, bool)
    peak = np.zeros(n_paths)
    t_reach = np.full(n_paths, np.inf)
    t_ruin = np.full(n_paths, np.inf)
    snaps = {}
    snap_days = {int(round(y * 252)): y for y in (1, 2, 3)}
    for d in range(n_days):
        j = (starts[:, d // block] + d % block) % T
        r, c = ret[j], rc[j]
        expo = np.where(switched, np.where(killed, 0.0, cap_after), size)
        eq *= 1.0 + expo * r + (1.0 - expo) * c
        newly_ruined = (eq <= ruin) & np.isinf(t_ruin)
        t_ruin[newly_ruined] = d + 1
        if monthly and (d + 1) % 21 == 0:
            eq += monthly
        hit = (eq >= target) & ~switched
        t_reach[hit] = d + 1
        switched |= hit
        peak = np.where(switched, np.maximum(peak, eq), peak)
        killed |= switched & (eq <= peak * (1 - kill))
        if (d + 1) in snap_days:
            snaps[snap_days[d + 1]] = eq.copy()
    reach_first = t_reach < t_ruin
    ruin_first = t_ruin < t_reach
    ty = t_reach / 252.0
    return {"p_reach_before_ruin": float(reach_first.mean()), "p_ruin_first": float(ruin_first.mean()),
            "p_neither": float((~reach_first & ~ruin_first).mean()),
            "p_reach_within": {y: float((ty <= y).mean()) for y in (1, 2, 3, 5, 10, years)},
            "time_to_target_years": {q: float(np.percentile(ty, q)) for q in (10, 50, 90)},
            "values": {y: {q: float(np.percentile(v, q)) for q in (10, 50, 90)} for y, v in snaps.items()},
            "p_killed": float(killed.mean()), "horizon_years": years, "n_paths": n_paths}
