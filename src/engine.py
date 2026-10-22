"""Backtester: daily bars, signal at close, fill at the next open.

Timeline for trading day t (all prices are the adjusted clean series):
  1. Interest: cash held overnight earns the prior day's daily T-bill rate,
     cash *= 1 + rate[t-1].
  2. Open: orders decided at the close of t-1 execute at open[t]. Sells run first, then
     buys, each at open x (1 -/+ cost), where cost = (half_spread + slippage) x cost_mult.
     Target value = weight x equity marked at open[t]. If costs leave too little cash for
     every buy, buys are scaled down pro rata (no margin, cash never negative).
     Orders under min_order_usd are skipped, except a sale that fully closes a position.
  3. Close: equity = cash + sum(shares x close[t]). The risk state updates on this close.
     Then the strategy's target for t (computed only from data up to close[t]) passes
     through the risk layer, becoming the order for open[t+1].
A rebalance happens on a day when the (risk-adjusted) target differs from the last one,
or when the strategy's `rebalance` flag is True.

Long only. No margin. Fractional shares. Commission is a config value (0).
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.risk import RiskState


@dataclass
class Result:
    equity: pd.Series
    cash: pd.Series
    shares: pd.DataFrame
    weights: pd.DataFrame
    mode: pd.Series
    trades: pd.DataFrame
    switch_date: object = None
    switch_count: int = 0
    kill_date: object = None
    meta: dict = field(default_factory=dict)

    @property
    def exposure(self):
        return self.weights.sum(axis=1)


def cost_rate(ticker, cfg, leveraged, cost_mult=1.0):
    """(half_spread, slippage) as fractions, already multiplied by cost_mult."""
    c = cfg["costs"]
    hs = c["half_spread"]["leveraged" if ticker in leveraged else "unleveraged"]
    return hs * cost_mult, c["slippage"] * cost_mult


def run_backtest(prices, targets, cash_rate, cfg, rebalance=None, cost_mult=1.0,
                 start_capital=None, risk_layer=True, start=None, end=None):
    """Simulate a strategy.

    prices     {ticker: DataFrame with Open, High, Low, Close} on a shared DatetimeIndex
    targets    DataFrame of target weights (rows = dates, cols = tickers), each row decided
               at that date's close using data up to that close; row sums <= 1, rest is cash
    cash_rate  Series of daily T-bill rates on the same index
    rebalance  optional bool Series: force a rebalance to the target decided at that close
    start/end  simulation window; capital is deployed from the first open after `start`
    """
    tickers = list(targets.columns)
    leveraged = set(cfg["instruments"]["leveraged"])
    idx = targets.index
    if start is not None:
        idx = idx[idx >= pd.Timestamp(start)]
    if end is not None:
        idx = idx[idx <= pd.Timestamp(end)]
    for t in tickers:
        missing = idx.difference(prices[t].index)
        if len(missing):
            raise ValueError("%s has no prices on %d simulation days" % (t, len(missing)))
    O = np.column_stack([prices[t]["Open"].reindex(idx).to_numpy(float) for t in tickers])
    C = np.column_stack([prices[t]["Close"].reindex(idx).to_numpy(float) for t in tickers])
    if np.isnan(O).any() or np.isnan(C).any():
        raise ValueError("NaN prices inside the simulation window")
    W = targets.reindex(idx).fillna(0.0).to_numpy(float)
    if (W < -1e-12).any() or (W.sum(axis=1) > 1 + 1e-9).any():
        raise ValueError("targets must be long-only with row sums <= 1")
    reb = np.zeros(len(idx), bool) if rebalance is None else rebalance.reindex(idx).fillna(False).to_numpy(bool)
    rate = cash_rate.reindex(idx).to_numpy(float)
    if np.isnan(rate).any():
        raise ValueError("cash rate missing inside the simulation window")
    costs = [cost_rate(t, cfg, leveraged, cost_mult) for t in tickers]
    commission = float(cfg["costs"]["commission_usd"])
    min_order = float(cfg["capital"]["min_order_usd"])
    cap0 = float(cfg["capital"]["starting_usd"] if start_capital is None else start_capital)

    risk = RiskState(cfg, leveraged, enabled=risk_layer)
    n, k = len(idx), len(tickers)
    sh = np.zeros(k)
    cash = cap0
    eq_s, cash_s, mode_s = np.empty(n), np.empty(n), []
    sh_s, w_s = np.empty((n, k)), np.empty((n, k))
    trades = []
    order = None                 # target weights to execute at the next open
    last_target = None

    for i in range(n):
        d = idx[i]
        if i > 0:
            cash *= 1.0 + rate[i - 1]
        if order is not None:
            o = O[i]
            eq_open = cash + float(sh @ o)
            tgt_val = order * eq_open
            cur_val = sh * o
            # sells first
            for j in range(k):
                diff = tgt_val[j] - cur_val[j]
                if diff >= 0 or sh[j] <= 0:
                    continue
                full = order[j] <= 0
                q = sh[j] if full else min(sh[j], -diff / o[j])
                gross = q * o[j]
                if gross < min_order and not full:
                    continue
                hs, sl = costs[j]
                px = o[j] * (1 - hs - sl)
                cash += q * px - commission
                sh[j] -= q
                if full:
                    sh[j] = 0.0
                trades.append((d, tickers[j], "sell", q, o[j], px, gross, q * o[j] * hs, q * o[j] * sl,
                               commission, q * px - commission))
            # then buys, scaled to available cash
            want = np.array([max(tgt_val[j] - sh[j] * o[j], 0.0) for j in range(k)])
            want[want < min_order] = 0.0
            fees = commission * np.count_nonzero(want)
            if want.sum() + fees > cash:
                scale = max(cash - fees, 0.0) / want.sum() if want.sum() > 0 else 0.0
                want *= scale
                want[want < min_order] = 0.0
            for j in range(k):
                if want[j] <= 0:
                    continue
                hs, sl = costs[j]
                px = o[j] * (1 + hs + sl)
                q = want[j] / px
                sh[j] += q
                cash -= want[j] + commission
                trades.append((d, tickers[j], "buy", q, o[j], px, q * o[j], q * o[j] * hs, q * o[j] * sl,
                               commission, -(want[j] + commission)))
            if cash < -1e-9:
                raise RuntimeError("cash went negative on %s" % d.date())
            cash = max(cash, 0.0)
            order = None
        c = C[i]
        eq = cash + float(sh @ c)
        eq_s[i], cash_s[i] = eq, cash
        sh_s[i] = sh
        w_s[i] = (sh * c) / eq if eq > 0 else 0.0
        risk.on_close(d, eq)
        mode_s.append(risk.mode if not risk.killed else risk.mode + "_killed")
        if i < n - 1:
            raw = dict(zip(tickers, W[i]))
            adj = risk.apply(raw)
            tgt = np.array([adj[t] for t in tickers])
            if last_target is None or reb[i] or not np.allclose(tgt, last_target, atol=1e-12):
                order = tgt
                last_target = tgt

    tr = pd.DataFrame(trades, columns=["date", "ticker", "side", "shares", "ref_open", "exec_price", "notional_at_open",
                                       "half_spread_cost", "slippage_cost", "commission", "cash_flow"])
    return Result(equity=pd.Series(eq_s, idx, name="equity"), cash=pd.Series(cash_s, idx, name="cash"),
                  shares=pd.DataFrame(sh_s, idx, tickers), weights=pd.DataFrame(w_s, idx, tickers),
                  mode=pd.Series(mode_s, idx, name="mode"), trades=tr, switch_date=risk.switch_date,
                  switch_count=risk.switch_count, kill_date=risk.kill_date,
                  meta={"cost_mult": cost_mult, "start_capital": cap0, "risk_layer": risk_layer})
