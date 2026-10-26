"""FX backtest engine for the specialists (expansion plan step 6). The original src/engine.py is unchanged.

Account: USD-based virtual ledger (config specialists.ledgers). Cash earns the US short rate (as in the earlier
studies, so Sharpe ratios are excess returns over T-bills). A position is an FX overlay on the pair BASE/QUOTE with
USD as base (USD/JPY: yen per USD):
  sign +1 = long USD / short JPY, -1 = short USD / long JPY, 0 = flat.
Notional is set in USD at entry: |N| = max_gross_notional_x x equity (no leverage beyond 1x). It is re-sized only
when the target changes or when |N| would exceed the cap (a trade, with costs).
Daily accounting from data date i-1 to i (calendar days d between them, so weekends and holidays accrue):
  spot P&L      = sign x N x (1 - S[i-1] / S[i])                       (exact for a USD-based account)
  carry         = sign x N x (r_usd[i-1] x d/360 - r_quote[i-1] x d/365) (rollover at the rate differential)
  markup        = -|sign| x N x markup_annual x d/365                   (dealer rollover markup, either side)
  cash interest = equity[i-1] x r_usd[i-1] x d/360
Execution: the target decided on data date t (using only data available on t) is executed at S[t+1] (or later,
`lag` extra days). Each traded USD notional pays `cost_one_way` (half-spread + slippage as a fraction of notional).
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class FXResult:
    equity: pd.Series
    position: pd.Series          # sign held at the end of each day
    notional: pd.Series          # USD notional (signed) held at the end of each day
    overlay: pd.Series           # daily overlay return = equity return minus cash return
    trades: pd.DataFrame
    meta: dict = field(default_factory=dict)


def run_fx(spot, r_usd, r_quote, target, cost_one_way, markup_annual, start_equity, max_x=1.0, lag=1,
           start=None, end=None, resize=None):
    """spot, r_usd, r_quote: Series on the same daily index (rates as annual decimals, already lagged to what was
    known on each date); target: Series of -1/0/+1 decided on each date (NaN = keep previous decision)."""
    idx = spot.index
    if start is not None:
        idx = idx[idx >= pd.Timestamp(start)]
    if end is not None:
        idx = idx[idx <= pd.Timestamp(end)]
    S = spot.reindex(idx).to_numpy(float)
    ru = r_usd.reindex(idx).to_numpy(float)
    rq = r_quote.reindex(idx).to_numpy(float)
    if np.isnan(S).any() or np.isnan(ru).any() or np.isnan(rq).any():
        raise ValueError("missing spot or rate inside the simulation window")
    tg = target.reindex(spot.index).ffill().shift(lag).reindex(idx).fillna(0.0).to_numpy(float)
    # optional DIAGNOSTIC re-sizing: on days flagged in `resize` (decision days, shifted by `lag` like the targets),
    # an open position is reset to max_x x equity, paying costs on the change. Default None = frozen behaviour.
    rs = np.zeros(len(idx), bool) if resize is None else \
        resize.reindex(spot.index).fillna(False).astype(bool).shift(lag).reindex(idx).fillna(False).to_numpy(bool)
    if not np.isin(tg, (-1.0, 0.0, 1.0)).all():
        raise ValueError("targets must be -1, 0 or +1")
    days = np.r_[0, np.diff(idx.values).astype("timedelta64[D]").astype(int)]
    n = len(idx)
    eq = np.empty(n)
    pos = np.zeros(n)
    notl = np.zeros(n)
    over = np.zeros(n)
    trades = []
    e, sign, N = float(start_equity), 0.0, 0.0
    for i in range(n):
        if i > 0:
            d = days[i]
            cash_int = e * ru[i - 1] * d / 360.0
            pnl = sign * N * (1.0 - S[i - 1] / S[i]) if sign else 0.0
            carry = sign * N * (ru[i - 1] * d / 360.0 - rq[i - 1] * d / 365.0) if sign else 0.0
            mk = -abs(sign) * N * markup_annual * d / 365.0
            e_new = e + cash_int + pnl + carry + mk
            over[i] = (pnl + carry + mk) / e if e > 0 else 0.0
            e = e_new
        want = tg[i]
        cap = max_x * e
        if want != sign or (sign and N > cap * (1 + 1e-12)):
            traded = (N if sign else 0.0) + (cap if want else 0.0) if want != sign else (N - cap)
            cost = cost_one_way * traded
            e -= cost
            trades.append((idx[i], sign, want, traded, S[i], cost))
            sign = want
            N = max_x * e if want else 0.0
            if i > 0 and e > 0:
                over[i] -= cost / (e + cost)
        elif sign and rs[i] and abs(N - max_x * e) > 1e-9:
            new_n = max_x * e
            cost = cost_one_way * abs(new_n - N)
            e -= cost
            trades.append((idx[i], sign, sign, abs(new_n - N), S[i], cost))
            N = max_x * e
            if i > 0 and e > 0:
                over[i] -= cost / (e + cost)
        eq[i] = e
        pos[i] = sign
        notl[i] = sign * N
    tr = pd.DataFrame(trades, columns=["date", "from", "to", "usd_traded", "spot", "cost_usd"])
    return FXResult(pd.Series(eq, idx), pd.Series(pos, idx), pd.Series(notl, idx), pd.Series(over, idx), tr,
                    {"cost_one_way": cost_one_way, "markup_annual": markup_annual, "max_x": max_x, "lag": lag})


def round_trips(res):
    """Completed or open holding episodes (entry from flat or a sign change counts as a new episode)."""
    p = res.position
    starts = ((p != 0) & (p != p.shift(1).fillna(0))).sum()
    return int(starts)
