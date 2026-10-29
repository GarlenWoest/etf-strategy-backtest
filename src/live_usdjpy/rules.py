"""Frozen forward-test rules F001 (RO-REV v0.2) and F002 (TSM12 v0.2) as pure functions.

Specification: research/USDJPY_FORWARD_TEST_PREREG.md (frozen 2026-10-29, sha256 in config.yaml). Parameters come
from config.yaml live_usdjpy.rules, which a test pins to the document. No I/O, no clock reads: every input is passed
in, so a rule's output depends only on its inputs and the result can be replayed.

Inputs (`RuleInputs`):
  fx, spy      pandas Series of COMPLETED daily closes indexed by date (only bars complete at decision time)
  t_now        aware datetime of the scan
  live_price   current USD/JPY snapshot price (indicative), used as the entry reference
  events       event-monitor records (for the F001 policy-decision exclusion)
  holidays     set of dates that are Japanese or US bank holidays
Output: Signal(kind = "CANDIDATE" | "NO_TRADE" | "WATCHING" | "NOT_DUE", ...). EXPERIMENTAL SHADOW SIGNALS.
"""
import math
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

LABEL = "EXPERIMENTAL SHADOW SIGNAL (forward test; not validated; not financial advice)"


@dataclass
class RuleInputs:
    fx: pd.Series
    spy: pd.Series
    live_price: float
    events: list = field(default_factory=list)
    holidays: set = field(default_factory=set)


@dataclass
class Signal:
    rule_id: str
    version: str
    kind: str
    bar_date: str
    setup_id: str = ""
    direction: int = 0
    entry_ref: float = None
    invalidation: float = None
    target: float = None
    expiry_rule: str = ""
    reason: str = ""
    values: dict = field(default_factory=dict)
    label: str = LABEL

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def zscore_last(closes, window):
    """z of the last daily log return against the std of the `window` returns before it (None if too short)."""
    lr = np.log(closes.astype(float)).diff().dropna()
    if len(lr) < window + 1:
        return None, None, None
    prior = lr.iloc[-window - 1:-1]
    sd = float(prior.std())
    r = float(lr.iloc[-1])
    return (r / sd if sd > 0 else None), r, sd


def policy_decision_on(day, events):
    out = []
    for e in events:
        title = e.get("title", "")
        if not ("FOMC" in title and "statement" in title.lower() or "BoJ" in title and "statement" in title.lower()):
            continue
        d = e.get("scheduled_date") or (e.get("scheduled_time_utc") or "")[:10]
        if str(d) == day.isoformat():
            out.append(title)
    return out


def f001(inp, p):
    """RO-REV v0.2. Long USD/JPY after a joint risk-off day (USD/JPY and SPY both <= -2 sigma60)."""
    if len(inp.fx) == 0:
        return Signal("F001", p["version"], "NO_TRADE", "", reason="no completed USD/JPY bars")
    t = inp.fx.index[-1].date()
    base = dict(rule_id="F001", version=p["version"], bar_date=t.isoformat())
    if pd.Timestamp(t) not in inp.spy.index:
        return Signal(kind="NO_TRADE", reason="no completed SPY bar for %s (US market closed)" % t, **base)
    zf, rf, sf = zscore_last(inp.fx, p["vol_window"])
    zs, rs, ss = zscore_last(inp.spy.loc[:pd.Timestamp(t)], p["vol_window"])
    vals = {"z_usdjpy": zf, "r_usdjpy": rf, "sd60_usdjpy": sf, "z_spy": zs, "r_spy": rs, "sd60_spy": ss}
    if zf is None or zs is None:
        return Signal(kind="NO_TRADE", reason="fewer than 61 completed bars", values=vals, **base)
    hit_fx, hit_spy = zf <= p["trigger_z"], zs <= p["trigger_z"]
    if not (hit_fx and hit_spy):
        if hit_fx or hit_spy:
            return Signal(kind="WATCHING", setup_id="F001-%s" % t, values=vals, **base,
                          reason="one leg at or below %.1f sigma (USD/JPY z %.2f, SPY z %.2f); no trigger" % (p["trigger_z"], zf, zs))
        return Signal(kind="NO_TRADE", values=vals, **base,
                      reason="no joint risk-off day (USD/JPY z %.2f, SPY z %.2f; trigger %.1f)" % (zf, zs, p["trigger_z"]))
    excl = []
    pd_titles = policy_decision_on(t, inp.events)
    if pd_titles:
        excl.append("scheduled policy decision on %s (%s)" % (t, "; ".join(pd_titles)))
    if t in inp.holidays:
        excl.append("bank holiday on %s (conservative temporary guard)" % t)
    if excl:
        return Signal(kind="NO_TRADE", setup_id="F001-%s" % t, values=vals, **base,
                      reason="trigger excluded by the pre-registration: " + "; ".join(excl))
    if not inp.live_price:
        return Signal(kind="NO_TRADE", setup_id="F001-%s" % t, values=vals, **base, reason="trigger, but no live price")
    e, ar = inp.live_price, abs(rf)
    return Signal(kind="CANDIDATE", setup_id="F001-%s" % t, direction=1, entry_ref=e,
                  invalidation=e * (1 - p["invalidation_mult"] * ar), target=e * (1 + p["target_mult"] * ar),
                  expiry_rule="exit at the first scan %d FX trading days after entry" % p["expiry_fx_days"],
                  reason="joint risk-off day %s: USD/JPY z %.2f, SPY z %.2f" % (t, zf, zs), values=vals, **base)


def last_fx_weekday_of_month(d):
    nxt = (pd.Timestamp(d) + pd.offsets.MonthEnd(0)).date()
    while nxt.weekday() >= 5:
        nxt = date.fromordinal(nxt.toordinal() - 1)
    return nxt


def f002(inp, p):
    """TSM12 v0.2 (low-prior control). At the last FX weekday of each month: sign of the 12-month log return,
    with a +/-2% dead band."""
    if len(inp.fx) == 0:
        return Signal("F002", p["version"], "NO_TRADE", "", reason="no completed USD/JPY bars")
    t = inp.fx.index[-1].date()
    base = dict(rule_id="F002", version=p["version"], bar_date=t.isoformat())
    month_end = last_fx_weekday_of_month(t)
    back = inp.fx.loc[:pd.Timestamp(t) - pd.DateOffset(months=p["lookback_months"])]
    vals = {}
    if len(back):
        r12 = math.log(float(inp.fx.iloc[-1]) / float(back.iloc[-1]))
        vals = {"r12_log": r12, "from_date": back.index[-1].date().isoformat()}
    if t != month_end:
        days_left = sum(1 for k in range(1, 8) if date.fromordinal(t.toordinal() + k) <= month_end
                        and date.fromordinal(t.toordinal() + k).weekday() < 5)
        if vals and days_left <= 3 and min(abs(vals["r12_log"] - p["dead_band_log_return"]),
                                           abs(vals["r12_log"] + p["dead_band_log_return"])) < 0.005:
            return Signal(kind="WATCHING", setup_id="F002-%s" % month_end.strftime("%Y-%m"), values=vals, **base,
                          reason="12-month return %.2f%% within 0.5 pp of a threshold, %d FX day(s) before the decision"
                          % (100 * vals["r12_log"], days_left))
        return Signal(kind="NOT_DUE", values=vals, **base, reason="not the month's last FX weekday (%s)" % month_end)
    if not vals:
        return Signal(kind="NO_TRADE", **base, reason="less than 12 months of completed bars")
    sid = "F002-%s" % t.strftime("%Y-%m")
    r12 = vals["r12_log"]
    if abs(r12) <= p["dead_band_log_return"]:
        return Signal(kind="NO_TRADE", setup_id=sid, values=vals, **base,
                      reason="12-month log return %.2f%% inside the +/-%.0f%% dead band: no position" % (100 * r12, 100 * p["dead_band_log_return"]))
    _, _, sd = zscore_last(inp.fx, p["vol_window"])
    if sd is None or not inp.live_price:
        return Signal(kind="NO_TRADE", setup_id=sid, values=vals, **base, reason="no volatility estimate or live price")
    d = 1 if r12 > 0 else -1
    e = inp.live_price
    stop = e * (1 - d * p["stop_monthly_sd_mult"] * sd * math.sqrt(21))
    vals["sd60"] = sd
    return Signal(kind="CANDIDATE", setup_id=sid, direction=d, entry_ref=e, invalidation=stop, target=None,
                  expiry_rule="re-evaluated at the next month-end; an unchanged sign is a new signal",
                  reason="month-end %s: 12-month log return %.2f%% -> %s" % (t, 100 * r12, "long" if d > 0 else "short"),
                  values=vals, **base)


RULES = {"F001": f001, "F002": f002}
