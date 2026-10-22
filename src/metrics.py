"""Performance statistics on a daily equity curve.

Phase 3 provides the basics used by the engine checks. Phase 5 adds the rest
(trade statistics, turnover, bootstrap and Deflated Sharpe Ratio).
Conventions: daily data, 252 periods a year; CAGR uses calendar time
(days / 365.25) between the first and last equity dates.
"""
import numpy as np
import pandas as pd

PERIODS = 252


def years(index):
    return (index[-1] - index[0]).days / 365.25


def cagr(equity):
    e = equity.dropna()
    return float((e.iloc[-1] / e.iloc[0]) ** (1 / years(e.index)) - 1)


def drawdown(equity):
    e = equity.dropna()
    return e / e.cummax() - 1


def max_drawdown(equity):
    return float(drawdown(equity).min())


def max_drawdown_duration(equity):
    """Longest stretch, in trading days, spent below a prior peak."""
    under = drawdown(equity) < 0
    runs = under.groupby((~under).cumsum()).cumsum()
    return int(runs.max()) if len(runs) else 0


def daily_returns(equity):
    return equity.pct_change().dropna()


def ann_vol(equity):
    return float(daily_returns(equity).std() * np.sqrt(PERIODS))


def sharpe(equity, cash_rate):
    """Annualized Sharpe of daily excess returns over the daily T-bill rate earned
    the same night (prior day's rate)."""
    r = daily_returns(equity)
    ex = r - cash_rate.shift(1).reindex(r.index).fillna(0.0)
    sd = ex.std()
    return float(ex.mean() / sd * np.sqrt(PERIODS)) if sd > 0 else float("nan")


def sortino(equity, cash_rate):
    r = daily_returns(equity)
    ex = r - cash_rate.shift(1).reindex(r.index).fillna(0.0)
    down = np.sqrt((np.minimum(ex, 0) ** 2).mean())
    return float(ex.mean() / down * np.sqrt(PERIODS)) if down > 0 else float("nan")


def calmar(equity):
    mdd = max_drawdown(equity)
    return float(cagr(equity) / -mdd) if mdd < 0 else float("nan")


def summary(equity, cash_rate):
    return {"cagr": cagr(equity), "ann_vol": ann_vol(equity), "sharpe": sharpe(equity, cash_rate),
            "sortino": sortino(equity, cash_rate), "max_drawdown": max_drawdown(equity),
            "max_dd_duration_days": max_drawdown_duration(equity), "calmar": calmar(equity)}
