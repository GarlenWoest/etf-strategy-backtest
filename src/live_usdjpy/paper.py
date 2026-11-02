"""Paper order manager, internal simulator and reconciliation for the USD/JPY forward test (master prompt step 7).

PAPER / SHADOW ONLY: no broker, no orders anywhere outside this module's own records.

Order state machine (each state recorded once; idempotency key "order:<client_order_id>:<STATE>"):
  CREATED -> DENIED                                 (gate blocked: recorded, never sent anywhere)
  CREATED -> RELEASED -> SUBMITTED -> FILLED        (internal simulator fills at the scan's snapshot price)
                                   -> REJECTED / EXPIRED / CANCELED
client_order_id = first 16 hex of sha256(rule | setup | intent | decision slot): a re-run cannot create a second order.

Sub-ledgers: one per rule (F001, F002), $10,000 each, USD account. Balances (pre-registration conventions):
  cash      starting USD; earns nothing (the cash baseline is 0)
  usd_pos   USD leg of the open position (+ long USD/JPY, - short)
  jpy       JPY leg (- when long USD/JPY)
  equity = cash + usd_pos + jpy / S (S = USD/JPY mark)
Fill: buying USD at S x (1 + c), selling USD at S x (1 - c). Financing at every 17:00 ET roll (3 days on Wednesday):
  usd_pos x r_usd x d/360 ; jpy x r_jpy x d/365 ; cash -= |usd_pos| x admin_fee x d/365   (estimated, unverified)
Ledger state is a `position_snapshot` record after every change; fills and accruals are append-only records.
Reconciliation: (1) exact recomputation from fill and accrual records; (2) fx_engine_v2 replay of the same position
path, compared within the tolerance fixed in config before any comparison. Any mismatch -> HALTED + HIGH alert.
"""
import hashlib
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from src import clock as K
from src import fx_engine_v2 as V2

from . import lifecycle as LC

NY = ZoneInfo("America/New_York")
ORDER_STATES = ("CREATED", "DENIED", "RELEASED", "SUBMITTED", "FILLED", "REJECTED", "EXPIRED", "CANCELED")
ORDER_NEXT = {None: {"CREATED"}, "CREATED": {"DENIED", "RELEASED"}, "RELEASED": {"SUBMITTED", "CANCELED"},
              "SUBMITTED": {"FILLED", "REJECTED", "EXPIRED", "CANCELED"}}


def coid(rule, setup, intent, slot):
    return hashlib.sha256("|".join([rule, setup, intent, slot]).encode()).hexdigest()[:16]


def initial(rule, cfg):
    e = float(cfg["sizing"]["start_usd"])
    return {"rule": rule, "cash": e, "usd_pos": 0.0, "jpy": 0.0, "position": None, "peak_equity": e,
            "day_start_equity": e, "ny_date": None, "last_roll_utc": None, "last_mark": None, "experiment_stopped": False}


def state(registry, rule, cfg):
    recs = [r["payload"] for r in registry.records("position_snapshot") if r["payload"]["rule"] == rule]
    return dict(recs[-1]) if recs else initial(rule, cfg)


def equity(st, S):
    return st["cash"] + st["usd_pos"] + (st["jpy"] / S if S else 0.0)


def exposure_x(st, S):
    e = equity(st, S)
    return (st["usd_pos"] + 0.0) / e if e else 0.0           # USD leg as a multiple of equity (signed, pair direction)


def snapshot(registry, st, now, why):
    registry.append("position_snapshot", {**st, "why": why}, now=now)


def order_event(registry, oid, st_, info, now):
    registry.append("order_event", {"client_order_id": oid, "state": st_, **info}, idem_key="order:%s:%s" % (oid, st_), now=now)


def order_state(registry, oid):
    ev = [r["payload"]["state"] for r in registry.records("order_event") if r["payload"]["client_order_id"] == oid]
    return ev[-1] if ev else None


# ---------------------------------------------------------------- financing

def rolls_between(a, b):
    """17:00 ET rolls in (a, b], as (roll time, days financed)."""
    out = []
    d = a.astimezone(NY).date()
    end = b.astimezone(NY)
    while True:
        t = datetime.combine(d, time(17, 0), tzinfo=NY)
        if t > end:
            break
        if t > a.astimezone(NY) and d.weekday() < 5:
            out.append((t, K.rollover_days(d)))
        d += timedelta(days=1)
    return out


def accrue(registry, st, now, S, rates, cfg_costs, scenario="base", cfg=None):
    """Apply financing for every roll since the last one.

    Policy v1 (2026-11-02, compliance fix + amendment v0.4; `cfg["financing"]["policy"]`): each roll is resolved with
    its OWN rates (src/live_usdjpy/financing.py: the latest observation dated on or before the roll, original date and
    age kept). VALID / VALID_ZERO / LATE (carried forward, flagged) are booked. If either leg is STALE or MISSING the
    roll is recorded as `financing_unresolved` with the position legs at the roll and NOTHING is booked: a missing rate
    is never 0%. `true_up()` books it later from acceptable data as an appended `financing_trueup` record.
    `rates`: the financing cache (fin_state) or, from older callers/tests, {"usd": (rate or None, info), ...}.
    Policy "legacy": the pre-2026-11-02 behaviour (a missing rate accrues 0), kept only for rollback."""
    from . import financing as FIN
    if st["position"] is None or not st["last_roll_utc"]:
        st["last_roll_utc"] = now.astimezone(timezone.utc).isoformat()
        return
    last = datetime.fromisoformat(st["last_roll_utc"])
    fee = cfg_costs[scenario]["financing_admin_fee_annual"]
    legacy = (cfg or {}).get("financing", {}).get("policy") == "legacy"
    tuple_rates = all(isinstance(v, (tuple, list)) for v in (rates or {}).values())
    for t, d in rolls_between(last, now):
        if legacy:
            ru, rj = rates.get("usd", (None, "UNKNOWN")), rates.get("jpy", (None, "UNKNOWN"))
            res = {"usd": {"state": "LEGACY", "value": ru[0] or 0.0, "info": ru[1]}, "jpy": {"state": "LEGACY", "value": rj[0] or 0.0, "info": rj[1]}}
        elif tuple_rates:
            res = {k: FIN.from_legacy(rates, k, t) for k in ("usd", "jpy")}
        else:
            res = {k: FIN.resolve(rates, k, t, cfg, now=now) for k in ("usd", "jpy")}
        bookable = legacy or all(r["state"] in FIN.BOOKABLE for r in res.values())
        common = {"rule": st["rule"], "roll_et": t.isoformat(), "days": d, "label": "estimated, unverified",
                  "policy": "legacy" if legacy else "v1", "r_usd_detail": res["usd"], "r_jpy_detail": res["jpy"]}
        if bookable:
            ru_v, rj_v = res["usd"]["value"], res["jpy"]["value"]
            a_usd = st["usd_pos"] * ru_v * d / 360.0
            a_jpy = st["jpy"] * rj_v * d / 365.0
            a_fee = abs(st["usd_pos"]) * fee * d / 365.0
            st["usd_pos"] += a_usd
            st["jpy"] += a_jpy
            st["cash"] -= a_fee
            registry.append("fill", dict(common, type="financing", usd_interest=a_usd, jpy_interest=a_jpy, admin_fee_usd=a_fee,
                                         r_usd=ru_v, r_usd_info=res["usd"].get("info") or FIN_info(res["usd"]),
                                         r_jpy=rj_v, r_jpy_info=res["jpy"].get("info") or FIN_info(res["jpy"])),
                            idem_key="accrual:%s:%s" % (st["rule"], t.isoformat()), now=now)
        else:
            registry.append("fill", dict(common, type="financing_unresolved", usd_pos_at_roll=st["usd_pos"], jpy_at_roll=st["jpy"],
                                         admin_fee_annual=fee, setup_id=(st["position"] or {}).get("setup_id"),
                                         reason="; ".join(r["reason"] for r in res.values() if r["state"] not in FIN.BOOKABLE),
                                         note="UNRESOLVED: nothing booked for this roll (never 0%); a TRUE-UP follows when acceptable data exists"),
                            idem_key="accrual:%s:%s" % (st["rule"], t.isoformat()), now=now)
        st["last_roll_utc"] = t.astimezone(timezone.utc).isoformat()


def FIN_info(res):
    from . import financing as FIN
    return FIN.info_line(res) if res.get("series") else ("%s (legacy rate input)" % res.get("legacy_info", "UNKNOWN"))


def unresolved(registry, rule):
    """financing_unresolved records of `rule` without a TRUE-UP yet."""
    done = {r["payload"]["roll_et"] for r in registry.records("fill")
            if r["payload"]["rule"] == rule and r["payload"]["type"] == "financing_trueup"}
    return [r["payload"] for r in registry.records("fill") if r["payload"]["rule"] == rule
            and r["payload"]["type"] == "financing_unresolved" and r["payload"]["roll_et"] not in done]


def true_up(registry, st, now, S, rates, cfg):
    """Book UNRESOLVED rolls whose rates are now acceptable, with the exact amount for each ORIGINAL roll date (position
    legs as recorded at that roll). Applied to the open position's legs, or, if the position has been closed since,
    to USD cash with the JPY part converted at the current mark S (recorded). The unresolved record is never edited."""
    from . import financing as FIN
    if (cfg or {}).get("financing", {}).get("policy") == "legacy" or not rates or all(isinstance(v, (tuple, list)) for v in rates.values()):
        return []
    out = []
    for u in unresolved(registry, st["rule"]):
        t = datetime.fromisoformat(u["roll_et"])
        res = {k: FIN.resolve(rates, k, t, cfg, now=now) for k in ("usd", "jpy")}
        if not all(r["state"] in FIN.BOOKABLE for r in res.values()):
            continue
        d = u["days"]
        a_usd = u["usd_pos_at_roll"] * res["usd"]["value"] * d / 360.0
        a_jpy = u["jpy_at_roll"] * res["jpy"]["value"] * d / 365.0
        a_fee = abs(u["usd_pos_at_roll"]) * u["admin_fee_annual"] * d / 365.0
        to_legs = st["position"] is not None and st["position"].get("setup_id") == u.get("setup_id")
        if to_legs:
            st["usd_pos"] += a_usd
            st["jpy"] += a_jpy
            st["cash"] -= a_fee
        else:
            if not S:
                continue
            st["cash"] += a_usd + a_jpy / S - a_fee
        registry.append("fill", {"type": "financing_trueup", "rule": st["rule"], "roll_et": u["roll_et"], "days": d,
                                 "usd_interest": a_usd, "jpy_interest": a_jpy, "admin_fee_usd": a_fee,
                                 "applied_to": "position legs" if to_legs else "USD cash (position closed; JPY converted at mid)",
                                 "conversion_mid": None if to_legs else S, "r_usd": res["usd"]["value"], "r_jpy": res["jpy"]["value"],
                                 "r_usd_detail": res["usd"], "r_jpy_detail": res["jpy"], "label": "TRUE-UP of an UNRESOLVED roll; estimated, unverified"},
                        idem_key="trueup:%s:%s" % (st["rule"], u["roll_et"]), now=now)
        out.append(u["roll_et"])
    if out:
        snapshot(registry, st, now, "financing true-up %s" % ", ".join(out))
    return out


# ---------------------------------------------------------------- fills

def _fill(registry, st, oid, side_usd, notional, S, c, now, kind):
    """side_usd +1 = buy USD (pay JPY), -1 = sell USD. Notional in USD."""
    price = S * (1 + c) if side_usd > 0 else S * (1 - c)
    st["usd_pos"] += side_usd * notional
    st["jpy"] -= side_usd * notional * price
    registry.append("fill", {"type": "trade", "rule": st["rule"], "client_order_id": oid, "kind": kind, "side_usd": side_usd,
                             "notional_usd": notional, "mid": S, "price": price, "cost_rate": c, "label": "internal simulator; indicative mid"},
                    idem_key="fill:%s" % oid, now=now)
    return price


def enter(registry, cfg, rule, setup_id, sig, size_x, S, now, slot, fields):
    """Entry for a gate-approved setup. Returns the client order id (or None if this setup already has one)."""
    oid = coid(rule, setup_id, "entry", slot)
    if any(r["payload"].get("setup_id") == setup_id and r["payload"].get("intent") == "entry" for r in registry.records("order_event")):
        return None
    st = state(registry, rule, cfg)
    if st["position"] is not None or st["experiment_stopped"]:
        return None
    eq = equity(st, S)
    notional = size_x * eq
    c = cfg["costs"]["base"]["one_way"]
    info = {"rule": rule, "setup_id": setup_id, "intent": "entry", "direction": sig["direction"], "size_x": size_x,
            "notional_usd": notional, "mode": "shadow (internal simulator)"}
    for s_ in ("CREATED", "RELEASED", "SUBMITTED"):
        order_event(registry, oid, s_, info, now)
    price = _fill(registry, st, oid, sig["direction"], notional, S, c, now, "open")
    order_event(registry, oid, "FILLED", {**info, "fill_price": price}, now)
    st["position"] = {"setup_id": setup_id, "direction": sig["direction"], "notional_usd": notional, "entry_mid": S,
                      "entry_price": price, "entry_utc": now.astimezone(timezone.utc).isoformat(),
                      "entry_ny_date": now.astimezone(NY).date().isoformat(), "invalidation": sig["invalidation"],
                      "target": sig.get("target"), "bar_date": sig["bar_date"], "size_x": size_x, "equity_at_entry": eq}
    st["last_roll_utc"] = now.astimezone(timezone.utc).isoformat()
    st["last_mark"] = S
    snapshot(registry, st, now, "entry %s" % setup_id)
    risk = abs(S - sig["invalidation"]) / S * notional
    LC.transition(registry, setup_id, "entered", {"client_order_id": oid, "fill_price": price, "notional_usd": notional},
                  dict(fields, size="%.3fx of the $%.0f sub-ledger ($%.2f notional)" % (size_x, eq, notional),
                       max_planned_loss="$%.2f at the invalidation level (%.2f%% of equity; gaps can exceed it)" % (risk, 100 * risk / eq)),
                  now, title="%s ENTERED (paper, shadow)" % setup_id)
    return oid


def exit_position(registry, cfg, rule, S, now, slot, reason):
    st = state(registry, rule, cfg)
    pos = st["position"]
    if pos is None:
        return None
    oid = coid(rule, pos["setup_id"], "exit", slot)
    if order_state(registry, oid) == "FILLED":
        return None
    c = cfg["costs"]["base"]["one_way"]
    info = {"rule": rule, "setup_id": pos["setup_id"], "intent": "exit", "reason": reason, "notional_usd": abs(st["usd_pos"])}
    for s_ in ("CREATED", "RELEASED", "SUBMITTED"):
        order_event(registry, oid, s_, info, now)
    price = _fill(registry, st, oid, -1 if st["usd_pos"] > 0 else 1, abs(st["usd_pos"]), S, c, now, "close")
    order_event(registry, oid, "FILLED", {**info, "fill_price": price}, now)
    eq_after = equity(st, S)
    st["cash"] += st["usd_pos"] + st["jpy"] / S          # flat: both legs ~0; fold residual JPY into USD cash at the mark
    st["usd_pos"], st["jpy"] = 0.0, 0.0
    closed = dict(pos, exit_mid=S, exit_price=price, exit_utc=now.astimezone(timezone.utc).isoformat(), exit_reason=reason,
                  equity_after=eq_after)
    st["position"] = None
    st["last_mark"] = S
    snapshot(registry, st, now, "exit %s (%s)" % (pos["setup_id"], reason))
    registry.append("outcome", {"type": "closed_position", "rule": rule, **closed}, idem_key="closed:%s" % pos["setup_id"], now=now)
    LC.transition(registry, pos["setup_id"], "exited", {"reason": reason, "exit_price": price},
                  {"setup_id": pos["setup_id"], "market": "USDJPY", "class": "PAPER POSITION UPDATE", "trigger": reason,
                   "reference_price": S, "validation_status": "FORWARD TEST %s: EXPERIMENTAL, NOT VALIDATED" % rule}, now,
                  title="%s EXITED (paper, shadow): %s" % (pos["setup_id"], reason))
    return oid


def manage(registry, cfg, now, S, rates, slot, new_f002_bar=None, can_fill=True):
    """Each scan, per rule: accrue financing, mark, daily-loss/drawdown bookkeeping, scan-based exits.
    `can_fill` False (FX market closed, or no LIVE price): an exit condition is recorded as EXIT PENDING with one alert
    and filled at the first scan with a live price after the reopen (weekend gap taken as it comes), never at a price
    nobody could trade. Returns {rule: (state, info)} from gate.derive_state on the sub-ledger."""
    from . import gate as G
    out = {}
    ny_date = now.astimezone(NY).date().isoformat()
    for rule in cfg["rules"]:
        st = state(registry, rule, cfg)
        accrue(registry, st, now, S, rates, cfg["costs"], cfg=cfg)
        true_up(registry, st, now, S, rates, cfg)
        eq = equity(st, S)
        if st["ny_date"] != ny_date:
            st["ny_date"], st["day_start_equity"] = ny_date, eq
        st["peak_equity"] = max(st["peak_equity"], eq)
        st["last_mark"] = S
        snapshot(registry, st, now, "mark")
        pos = st["position"]
        reason = None
        if pos:
            d = pos["direction"]
            if d * (S - pos["invalidation"]) <= 0:
                reason = "invalidation reached at a scan (%.3f vs %.3f); next-scan fill, not a stop order" % (S, pos["invalidation"])
            elif pos.get("target") and d * (S - pos["target"]) >= 0:
                reason = "target reached at a scan (%.3f vs %.3f)" % (S, pos["target"])
            elif rule == "F001" and _fx_days_since(pos["entry_ny_date"], now) >= cfg["rules"]["F001"]["expiry_fx_days"]:
                reason = "expiry: %d FX trading days after entry" % cfg["rules"]["F001"]["expiry_fx_days"]
            elif rule == "F002" and new_f002_bar and new_f002_bar > pos["bar_date"]:
                reason = "expiry: next month-end evaluation (%s)" % new_f002_bar
        book = G.Book(equity=eq, peak_equity=st["peak_equity"], day_start_equity=st["day_start_equity"],
                      positions={rule: exposure_x(st, S)} if pos else {})
        s_, info = G.derive_state(book, cfg["risk_limits"], None, False, now)
        if info["close_all"] and pos:
            reason = "risk limit: sub-ledger drawdown %.2f%% <= -5%%: close everything, experiment stopped" % (100 * info["drawdown"])
        if pos and pos.get("exit_pending") and can_fill:          # the earlier decision stands (it came first)
            reason = "%s (deferred while the market was closed; filled at the first live price)" % pos["exit_pending"]
        if reason and not can_fill:
            if not pos.get("exit_pending"):
                st["position"] = dict(pos, exit_pending=reason)
                snapshot(registry, st, now, "exit pending: no tradable price (market closed or price not LIVE)")
                registry.append("notification", LC.alert(
                    "NORMAL", "%s EXIT PENDING (market closed)" % pos["setup_id"],
                    **{"class": "PAPER POSITION UPDATE", "market": "USDJPY", "setup_id": pos["setup_id"],
                       "trigger": reason, "event_time_et": LC.et(now),
                       "why_sent": "exit condition met while no tradable price exists; fills at the first live price after the reopen"}),
                    idem_key="notif:exit-pending:%s" % pos["setup_id"], now=now)
            reason = None
        if reason:
            exit_position(registry, cfg, rule, S, now, slot, reason)
        if info["experiment_stopped"]:
            st = state(registry, rule, cfg)
            if not st["experiment_stopped"]:
                st["experiment_stopped"] = True
                snapshot(registry, st, now, "experiment stopped (drawdown <= -5%)")
                registry.append("notification", LC.alert("HIGH", "%s sub-ledger STOPPED: drawdown <= -5%%" % rule,
                                                         **{"class": "RISK/SYSTEM ALERT", "event_time_et": LC.et(now),
                                                            "why_sent": "pre-registered experiment stop; owner decision needed"}),
                                idem_key="notif:stop:%s" % rule, now=now)
        out[rule] = (s_, info)
    return out


def _fx_days_since(entry_ny_date, now):
    a = datetime.fromisoformat(entry_ny_date).date() if isinstance(entry_ny_date, str) else entry_ny_date
    b = now.astimezone(NY).date()
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


# ---------------------------------------------------------------- reconciliation

def recompute(registry, rule, cfg):
    """Independent recomputation of a sub-ledger from append-only fill/financing records (no snapshot is read)."""
    cash, usd_pos, jpy = float(cfg["sizing"]["start_usd"]), 0.0, 0.0
    for r in registry.records("fill"):
        p = r["payload"]
        if p["rule"] != rule:
            continue
        if p["type"] == "trade":
            usd_pos += p["side_usd"] * p["notional_usd"]
            jpy -= p["side_usd"] * p["notional_usd"] * p["price"]
            if p["kind"] == "close":
                cash += usd_pos + jpy / p["mid"]
                usd_pos, jpy = 0.0, 0.0
        elif p["type"] == "financing" or (p["type"] == "financing_trueup" and p.get("conversion_mid") is None):
            usd_pos += p["usd_interest"]
            jpy += p["jpy_interest"]
            cash -= p["admin_fee_usd"]
        elif p["type"] == "financing_trueup":                      # booked to cash after the position was closed
            cash += p["usd_interest"] + p["jpy_interest"] / p["conversion_mid"] - p["admin_fee_usd"]
        # financing_unresolved: no balance effect by design
    return {"cash": cash, "usd_pos": usd_pos, "jpy": jpy}


def v2_replay(registry, rule, cfg):
    """Replay the realised position path through fx_engine_v2 (lag 0, trades at each fill's mid, cost c per USD traded,
    calendar-day accrual). Returns its P&L in excess of USD cash, or None if there is nothing to replay."""
    marks = []
    for r in registry.records("position_snapshot"):
        p = r["payload"]
        if p["rule"] == rule and p.get("last_mark"):
            marks.append((pd.Timestamp(r["created_utc"]).tz_convert(None).normalize(), p["last_mark"],
                          (p["position"]["direction"] * p["position"]["size_x"]) if p["position"] else 0.0))
    if len(marks) < 2:
        return None
    df = pd.DataFrame(marks, columns=["d", "S", "x"]).groupby("d").last()
    if unresolved(registry, rule):
        return "DEFERRED"                     # an UNRESOLVED roll is booked on neither side until its TRUE-UP
    acc = [r["payload"] for r in registry.records("fill") if r["payload"]["rule"] == rule
           and r["payload"]["type"] in ("financing", "financing_trueup") and r["payload"].get("r_usd") is not None]
    if (cfg.get("financing", {}).get("policy") == "legacy"):
        ru = next((a["r_usd"] for a in acc), 0.0)
        rj = next((a["r_jpy"] for a in acc), 0.0)
    else:                                     # the same per-roll rates the ledger booked, by roll date (UTC-normalized)
        by_d = {}
        for a in acc:
            by_d[pd.Timestamp(datetime.fromisoformat(a["roll_et"]).astimezone(timezone.utc)).tz_convert(None).normalize()] = (a["r_usd"], a["r_jpy"])
        if by_d:
            rs = pd.DataFrame(by_d, index=["u", "j"]).T.sort_index()
            rs = rs.reindex(rs.index.union(df.index)).ffill().bfill().reindex(df.index)
            ru, rj = rs["u"].astype(float), rs["j"].astype(float)
        else:
            ru, rj = 0.0, 0.0                 # no financing booked on either side
    tgt = df["x"].where(df["x"].ne(df["x"].shift()), other=float("nan"))
    tgt.iloc[0] = df["x"].iloc[0]
    e0 = float(cfg["sizing"]["start_usd"])
    ru_s = ru if isinstance(ru, pd.Series) else pd.Series(ru, df.index)
    rj_s = rj if isinstance(rj, pd.Series) else pd.Series(rj, df.index)
    res = V2.run_balance(df["S"], ru_s, rj_s, tgt, cfg["costs"]["base"]["one_way"],
                         cfg["costs"]["base"]["financing_admin_fee_annual"], e0, max_x=1.0, lag=0, band=0.0, invert=True)
    cash_growth = e0 * float((1 + ru_s.iloc[:-1].values * pd.Series(df.index).diff().dt.days.iloc[1:].values / 360).prod())
    return float(res.equity.iloc[-1]) - cash_growth


def reconcile(registry, cfg, now, S):
    rc = cfg["paper"]["reconciliation"]
    report, ok = {}, True
    for rule in cfg["rules"]:
        st = state(registry, rule, cfg)
        rec = recompute(registry, rule, cfg)
        diff = max(abs(rec[k] - st[k]) for k in ("cash", "usd_pos", "jpy"))
        exact_ok = diff <= rc["exact_tolerance_usd"] * max(1.0, abs(st["jpy"]) / 1e4)
        ledger_pnl = equity(st, S) - cfg["sizing"]["start_usd"]
        v2 = v2_replay(registry, rule, cfg)
        tol = rc["v2_parity_tolerance_frac"] * cfg["sizing"]["start_usd"]
        deferred = v2 == "DEFERRED"
        parity_ok = True if (v2 is None or deferred) else abs(ledger_pnl - v2) <= tol
        report[rule] = {"exact_max_diff": diff, "exact_ok": exact_ok, "ledger_pnl": ledger_pnl, "v2_pnl": None if deferred else v2,
                        "v2_tolerance_usd": tol, "parity_ok": parity_ok,
                        "parity_note": ("deferred: %d UNRESOLVED financing roll(s) pending TRUE-UP; exact recomputation still checked"
                                        % len(unresolved(registry, rule))) if deferred else None}
        ok = ok and exact_ok and parity_ok
    registry.append("reconciliation", {"ok": ok, "report": report}, now=now)
    if not ok:
        registry.append("risk_state", {"state": "HALTED", "why": ["reconciliation mismatch: %s" % report],
                                       "ny_date": now.astimezone(NY).date().isoformat()}, now=now)
        registry.append("notification", LC.alert("HIGH", "RECONCILIATION MISMATCH: paper entries halted",
                                                 **{"class": "RISK/SYSTEM ALERT", "event_time_et": LC.et(now),
                                                    "why_sent": str(report)[:500]}), now=now)
    return ok, report
