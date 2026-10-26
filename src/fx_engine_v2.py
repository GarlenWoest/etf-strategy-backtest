"""Currency-balance backtest engine, VERSION 2: for FUTURE pre-registered experiments only.

Version 1 (src/fx_engine.py) is unchanged and remains the engine of record for the frozen USD/JPY study 1
(V135-V142), so those results can always be reproduced. Nothing here changes any reported result.

Defects in v1 that v2 corrects (Priority 1 audit, 2026-10-26; reports/specialists/fx_engine_v2_comparison.md):
  D1 sizing ratchet. v1 sets the notional at entry and only shrinks it when it exceeds the cap; it never grows it
     back, so long holds drift below target (always-long USD/JPY: 0.32x by 2023). v2 re-sizes to the target at every
     decision (outside an optional tolerance `band`) and enforces the cap at every close.
  D2 K4 counting. v1's trade list mixes cap trims with direction changes. v2 labels every trade
     (open / close / reverse / resize / cap_trim); position_changes() counts only open, close and reverse.
  D3 implicit daily re-sizing. v1 books N x (1 - S[i-1]/S[i]) on a constant USD notional N, i.e. it silently
     re-sizes the yen leg every day at no cost. v2 holds currency balances, which do not change size by themselves,
     and marks them to market, as a broker does.

Accounting (USD account): two balances, `usd` and `units` of ONE foreign asset (JPY, GBP, gold ounces ...).
  P[i]      USD price of one unit of the asset (USD/JPY: 1/S, GBP/USD: S, gold: USD per ounce)
  exposure  units x P (signed USD; negative = short the asset); equity = usd + exposure
  accrual from close i-1 to close i over d calendar days (weekends and holidays included):
     usd   += usd x r_usd[i-1] x d / basis_usd           (a negative USD balance pays interest)
     units += units x r_asset[i-1] x d / basis_asset     (the asset's own interest; gold: lease rate, usually 0)
     usd   -= |exposure[i-1]| x markup_annual x d / 365  (dealer rollover markup, either side)
  Holding balances at their interest rates is the covered-interest-parity value of a rolled spot position; v1's
  carry formula is the constant-notional approximation of the same thing.
Execution: a target decided on data date t (only data known at t) executes at P[t + lag]. Each USD of exposure
traded pays `cost_one_way`. Target values are signed fractions of equity in the PAIR's direction (USD/JPY +1 =
long USD / short JPY); NaN = no decision that day (balances are held; only the cap applies).
Cap: after every close, |exposure| <= max_x x (1 + cap_tolerance) x equity; any excess is trimmed back to max_x
(a `cap_trim`, with costs).
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

ENGINE_VERSION = "fx_engine_v2 1.1 (2026-10-26)"
# Defaults approved by the user 2026-10-26, fixed before any new pre-registration (config.yaml specialists.engine_v2):
DEFAULT_BAND = 0.10            # re-size at a decision only if the exposure is > 10% of equity off target
DEFAULT_CAP_TOLERANCE = 0.05   # trim only above 1.05 x max_x, back to exactly max_x
CHANGE_KINDS = ("open", "close", "reverse")


@dataclass
class BalanceResult:
    equity: pd.Series
    exposure: pd.Series          # signed USD exposure to the PAIR direction at each close (+ = long the pair)
    exposure_x: pd.Series        # exposure / equity
    units: pd.Series             # asset balance (e.g. JPY; negative = short the asset)
    overlay: pd.Series           # daily return in excess of holding all equity in USD cash
    trades: pd.DataFrame         # date, kind, from_x, to_x, usd_traded, price, cost_usd
    meta: dict = field(default_factory=dict)


def run_balance(price, r_usd, r_asset, target, cost_one_way, markup_annual, start_equity, max_x=1.0, lag=1,
                band=DEFAULT_BAND, cap_tolerance=DEFAULT_CAP_TOLERANCE, basis_usd=360, basis_asset=365, invert=False, start=None, end=None):
    """price: USD price of one asset unit (or the pair quote if invert=True, e.g. USD/JPY yen per USD); r_usd, r_asset:
    annual decimals already lagged to what was known on each date; target: Series of signed exposure fractions in the
    pair's direction decided on each date (NaN = no decision). invert=True means the pair is USD/XXX (the asset is
    the quote currency): P = 1/price and a long pair position is a short asset balance.
    band: on a decision day with an unchanged direction, re-size only if |exposure_x - target| > band.
    cap_tolerance: trim only when |exposure| > max_x x (1 + cap_tolerance) x equity, back to exactly max_x; 0 = a strict
    cap at every close (many tiny trims). Defaults: DEFAULT_BAND and DEFAULT_CAP_TOLERANCE (user-approved)."""
    idx = price.index
    if start is not None:
        idx = idx[idx >= pd.Timestamp(start)]
    if end is not None:
        idx = idx[idx <= pd.Timestamp(end)]
    S = price.reindex(idx).to_numpy(float)
    ru = r_usd.reindex(idx).to_numpy(float)
    ra = r_asset.reindex(idx).to_numpy(float)
    if np.isnan(S).any() or np.isnan(ru).any() or np.isnan(ra).any() or (S <= 0).any():
        raise ValueError("missing or non-positive price, or missing rate, inside the simulation window")
    tg = target.reindex(price.index).shift(lag).reindex(idx).to_numpy(float)      # NaN = no decision
    ok = np.isnan(tg) | (np.abs(tg) <= max_x + 1e-12)
    if not ok.all():
        raise ValueError("targets must satisfy |target| <= max_x")
    if band < 0 or max_x <= 0 or cap_tolerance < 0:
        raise ValueError("band and cap_tolerance must be >= 0 and max_x > 0")
    P = 1.0 / S if invert else S
    sgn = -1.0 if invert else 1.0                      # pair exposure = sgn x asset exposure
    days = np.r_[0, np.diff(idx.values).astype("timedelta64[D]").astype(int)]
    n = len(idx)
    eq, ex, un, over = np.empty(n), np.empty(n), np.empty(n), np.zeros(n)
    trades = []
    usd, units = float(start_equity), 0.0

    def trade_to(i, want_x, kind_hint):
        nonlocal usd, units
        e = usd + units * P[i]
        cur = sgn * units * P[i]                       # pair exposure in USD
        c = cost_one_way
        delta = np.sign(want_x * e - cur)
        new = want_x * (e + c * delta * cur) / (1 + want_x * c * delta)   # exposure = want_x x equity AFTER costs
        traded = abs(new - cur)
        if traded <= 1e-12:
            return 0.0
        cost = c * traded
        units = sgn * new / P[i]
        usd = e - units * P[i] - cost
        if kind_hint == "cap_trim":
            kind = "cap_trim"
        elif cur == 0:
            kind = "open"
        elif new == 0:
            kind = "close"
        elif np.sign(cur) != np.sign(new):
            kind = "reverse"
        else:
            kind = "resize"
        trades.append((idx[i], kind, cur / e if e else 0.0, want_x, traded, S[i], cost))
        return cost

    for i in range(n):
        e_prev = usd + units * P[i - 1] if i > 0 else usd
        if i > 0:
            d = days[i]
            exp_prev = abs(units * P[i - 1])
            usd += usd * ru[i - 1] * d / basis_usd
            units += units * ra[i - 1] * d / basis_asset
            usd -= exp_prev * markup_annual * d / 365.0
        cost = 0.0
        e = usd + units * P[i]
        cur_x = sgn * units * P[i] / e if e > 0 else 0.0
        w = tg[i]
        if not np.isnan(w) and e > 0:
            if np.sign(w) != np.sign(cur_x) or (w != 0 and abs(cur_x - w) > band):
                cost += trade_to(i, float(w), "decision")
        e = usd + units * P[i]
        if e > 0 and abs(units * P[i]) > max_x * e * (1 + cap_tolerance + 1e-12):
            cost += trade_to(i, float(np.sign(sgn * units)) * max_x, "cap_trim")
        e = usd + units * P[i]
        eq[i], un[i] = e, units
        ex[i] = sgn * units * P[i]
        if i > 0 and e_prev > 0:
            over[i] = (e - e_prev * (1 + ru[i - 1] * days[i] / basis_usd)) / e_prev
    tr = pd.DataFrame(trades, columns=["date", "kind", "from_x", "to_x", "usd_traded", "price", "cost_usd"])
    eqs = pd.Series(eq, idx)
    return BalanceResult(eqs, pd.Series(ex, idx), pd.Series(ex, idx) / eqs, pd.Series(un, idx), pd.Series(over, idx), tr,
                         {"engine": ENGINE_VERSION, "cost_one_way": cost_one_way, "markup_annual": markup_annual,
                          "max_x": max_x, "lag": lag, "band": band, "cap_tolerance": cap_tolerance, "invert": invert,
                          "basis_usd": basis_usd, "basis_asset": basis_asset})


def position_changes(res, start=None, end=None):
    """Direction changes only (open, close, reverse); re-sizes and cap trims are not position changes (fixes D2)."""
    t = res.trades
    if start is not None:
        t = t[t["date"] >= pd.Timestamp(start)]
    if end is not None:
        t = t[t["date"] <= pd.Timestamp(end)]
    return int(t["kind"].isin(CHANGE_KINDS).sum())


def trade_counts(res):
    return {k: int((res.trades["kind"] == k).sum()) for k in CHANGE_KINDS + ("resize", "cap_trim")}


def holding_days(res):
    """Lengths (in data days) of each run of a constant non-zero direction."""
    d = np.sign(res.exposure.round(12))
    g = d.groupby(d.ne(d.shift(1)).cumsum()).agg(["first", "size"])
    return g.loc[g["first"] != 0, "size"]
