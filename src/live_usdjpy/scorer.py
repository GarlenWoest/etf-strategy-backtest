"""Forward-test scorer and status page (master prompt step 8, 2026-10-29). Plain Python; deterministic.

Scores every closed paper position exactly once (`outcome` record type "scored", idempotency key "scored:<setup>")
and then moves the setup to `resolved`. Predictions (evaluation records) are never touched: scores are separate
records that point to them, so a prediction is provably unchanged after its outcome (the hash chain).

Per signal (pre-registration sections 3-5): net return under base and stress costs; baselines over the same window
and size: cash (0), always long, historical sample mean (frozen sign +1), simple trend (sign of price vs its 20-day
average at entry), and for F001 a placebo (up to 10 eligible non-trigger days from the forward record, seed 20261029);
directional accuracy; error against the no-change forecast (= the realised move). Calibration: UNKNOWN (no rule
produces probabilities). Every table carries the power banner; no statistics are computed below 30 resolved signals.
"""
import math
import random
from datetime import datetime, timedelta, timezone
from statistics import mean, median
from zoneinfo import ZoneInfo

from . import lifecycle as LC
from . import paper as PP

NY = ZoneInfo("America/New_York")
BANNER = ("POWER: n = %d resolved signal(s) for %s. Fewer than 30 resolved signals: nothing here is statistically "
          "meaningful. Pre-registered formal evaluation: F001 at 69 signals, F002 at 120 months, or 2036-10-31 "
          "(at about 1.2 F001 signals a year, 30 take about 25 years).")


def pair_pnl(direction, notional, s1, s2, c, fin_days, r_usd, r_jpy, fee):
    """USD P&L of `notional` USD in the pair's direction, entered at s1 and exited at s2 with the fill convention,
    plus estimated financing over `fin_days` (same conventions as the simulator, approximate for baselines)."""
    if direction == 0 or notional == 0:
        return 0.0
    buy, sell = (1 + c), (1 - c)
    if direction > 0:
        jpy = -notional * s1 * buy + notional * s2 * sell
    else:
        jpy = notional * s1 * sell - notional * s2 * buy
    fin = notional * (direction * ((r_usd or 0) * 365 / 360 - (r_jpy or 0)) - fee) * fin_days / 365.0
    return jpy / s2 + fin


def financing_for(registry, rule, entry_utc, exit_utc):
    acc = [r["payload"] for r in registry.records("fill") if r["payload"]["rule"] == rule and r["payload"]["type"] == "financing"
           and entry_utc < datetime.fromisoformat(r["payload"]["roll_et"]).astimezone(timezone.utc).isoformat() <= exit_utc]
    days = sum(a["days"] for a in acc)
    usd = sum(a["usd_interest"] + 0.0 for a in acc)
    fee = sum(a["admin_fee_usd"] for a in acc)
    jpy = sum(a["jpy_interest"] for a in acc)
    ru = next((a["r_usd"] for a in acc if a["r_usd"] is not None), None)
    rj = next((a["r_jpy"] for a in acc if a["r_jpy"] is not None), None)
    return {"days": days, "usd_interest": usd, "jpy_interest": jpy, "admin_fee_usd": fee, "r_usd": ru, "r_jpy": rj,
            "known": ru is not None and rj is not None}


def daily_closes(registry):
    """Daily USD/JPY closes as recorded by the scanner (one per completed bar date), from market_state records."""
    out = {}
    for r in registry.records("market_state"):
        bars_ = r["payload"].get("bars") or {}
        b = bars_.get("USD_JPY") or bars_.get("JPY=X") or {}        # Yahoo-era key in records before 2026-10-30
        if b.get("last_date") and b.get("last_close"):
            out[b["last_date"]] = b["last_close"]
    return dict(sorted(out.items()))


def sma20_at(registry, when_utc):
    best = None
    for r in registry.records("market_state"):
        if r["created_utc"] <= when_utc and r["payload"].get("usdjpy_sma20"):
            best = r["payload"]
    return best


def placebo_f001(registry, pos, cfg, seed=20261029, k=10):
    """Same entry, levels (as % of entry) and expiry on up to k eligible non-trigger days, from recorded closes
    before the signal's bar date. Returns (mean return as a fraction of sub-ledger equity, n used)."""
    closes = daily_closes(registry)
    trig = {r["payload"]["bar_date"] for r in registry.records("evaluation")
            if r["payload"].get("type") == "rule_signal" and r["payload"].get("rule_id") == "F001" and r["payload"]["kind"] != "NO_TRADE"}
    days = [d for d in closes if d < pos["bar_date"] and d not in trig]
    if not days:
        return None, 0
    rnd = random.Random("%d:%s" % (seed, pos["setup_id"]))
    pick = rnd.sample(days, min(k, len(days)))
    inv = abs(pos["entry_mid"] - pos["invalidation"]) / pos["entry_mid"]
    tgt = abs(pos["target"] - pos["entry_mid"]) / pos["entry_mid"] if pos.get("target") else None
    keys = list(closes)
    c = cfg["costs"]["base"]["one_way"]
    rets = []
    for d in pick:
        i = keys.index(d)
        s1 = closes[d]
        s2 = s1
        for j in range(i + 1, min(i + 1 + cfg["rules"]["F001"]["expiry_fx_days"], len(keys))):
            s2 = closes[keys[j]]
            if pos["direction"] * (s2 - s1) / s1 <= -inv or (tgt and pos["direction"] * (s2 - s1) / s1 >= tgt):
                break
        rets.append(pair_pnl(pos["direction"], pos["notional_usd"], s1, s2, c, 0, 0, 0, 0) / pos["equity_at_entry"])
    return mean(rets), len(rets)


def score_closed(registry, cfg, now):
    """Score every closed position not yet scored; move its setup to `resolved`. Returns the new scores."""
    base, stress = cfg["costs"]["base"], cfg["costs"]["stress"]
    new = []
    for r in registry.records("outcome"):
        p = r["payload"]
        if p.get("type") != "closed_position" or registry.get_by_key("scored:%s" % p["setup_id"]):
            continue
        rule, E = p["rule"], p["equity_at_entry"]
        fin = financing_for(registry, rule, p["entry_utc"], p["exit_utc"])
        net_base = (p["equity_after"] - E) / E
        extra = ((stress["one_way"] - base["one_way"]) * 2 * p["notional_usd"]
                 + (stress["financing_admin_fee_annual"] - base["financing_admin_fee_annual"]) * p["notional_usd"] * fin["days"] / 365.0)
        net_stress = net_base - extra / E
        s1, s2, N, d = p["entry_mid"], p["exit_mid"], p["notional_usd"], p["direction"]
        bl = lambda direction: pair_pnl(direction, N, s1, s2, base["one_way"], fin["days"], fin["r_usd"], fin["r_jpy"],
                                        base["financing_admin_fee_annual"]) / E
        sm = sma20_at(registry, p["entry_utc"])
        trend_dir = (1 if s1 > sm["usdjpy_sma20"] else -1) if sm else None
        plc = placebo_f001(registry, p, cfg) if rule == "F001" else (None, 0)
        sess = (sm or {}).get("usdjpy_sessions") or []
        sc = {"type": "scored", "rule": rule, "setup_id": p["setup_id"], "bar_date": p["bar_date"], "direction": d,
              "entry_utc": p["entry_utc"], "exit_utc": p["exit_utc"], "exit_reason": p["exit_reason"],
              "net_return_base": net_base, "net_return_stress": net_stress,
              "financing": {**fin, "label": "estimated, unverified" if fin["known"] else "UNKNOWN rates: fee only"},
              "costs_usd_base": base["one_way"] * 2 * N,
              "baselines": {"cash": 0.0, "always_long": bl(1), "historical_sample_mean": bl(cfg["baselines"]["historical_sample_mean"]["sign"]),
                            "simple_trend": bl(trend_dir) if trend_dir else None, "placebo_F001": plc[0], "placebo_n": plc[1]},
              "direction_correct": (s2 - s1) * d > 0, "no_change_error": abs(s2 - s1) / s1,
              "calibration": "UNKNOWN (no probabilities)", "session_at_entry": ", ".join(sess) or "UNKNOWN",
              "event_in_window": "not yet computed (needs the event store in the scorer; pending)",
              "label": "FORWARD TEST (shadow, internal simulator, indicative prices); not validated"}
        registry.append("outcome", sc, idem_key="scored:%s" % p["setup_id"], now=now)
        LC.transition(registry, p["setup_id"], "resolved", {"net_return_base": net_base},
                      {"setup_id": p["setup_id"], "market": "USDJPY", "class": "PAPER POSITION UPDATE",
                       "trigger": "resolved: net %.3f%% (base costs), %.3f%% (stress)" % (100 * net_base, 100 * net_stress),
                       "validation_status": "FORWARD TEST %s: EXPERIMENTAL, NOT VALIDATED" % rule}, now)
        new.append(sc)
    return new


def scorecard(registry, cfg):
    rows = {}
    scored = [r["payload"] for r in registry.records("outcome") if r["payload"].get("type") == "scored"]
    for rule in cfg["rules"]:
        s = [x for x in scored if x["rule"] == rule]
        n = len(s)
        nb = [x["net_return_base"] for x in s]
        wins, losses = [v for v in nb if v > 0], [v for v in nb if v <= 0]
        bl = lambda k: [x["baselines"][k] for x in s if x["baselines"].get(k) is not None]
        rows[rule] = {
            "n": n, "mean_base": mean(nb) if nb else None, "median_base": median(nb) if nb else None,
            "mean_stress": mean([x["net_return_stress"] for x in s]) if s else None,
            "hit_rate_trades": len(wins) / n if n else None, "avg_win": mean(wins) if wins else None,
            "avg_loss": mean(losses) if losses else None,
            "dir_accuracy": mean([1.0 if x["direction_correct"] else 0.0 for x in s]) if s else None,
            "baseline_means": {k: (mean(bl(k)) if bl(k) else None) for k in ("cash", "always_long", "historical_sample_mean", "simple_trend", "placebo_F001")},
            "statistics": "not computed: n < 30" if n < cfg["evaluation"]["min_resolved_for_claims"] else "see formal evaluation",
            "calibration": "UNKNOWN", "banner": BANNER % (n, rule)}
    setups = {}
    for r in registry.records("setup_transition"):
        setups.setdefault(r["payload"]["setup_id"], []).append(r["payload"]["state"])
    counts = {"detected": len(setups), "triggered": sum("triggered" in v for v in setups.values()),
              "blocked": sum("blocked" in v for v in setups.values()), "entered": sum("entered" in v for v in setups.values()),
              "resolved": sum("resolved" in v for v in setups.values()),
              "no_trade_evaluations": sum(1 for r in registry.records("evaluation")
                                          if r["payload"].get("type") == "rule_signal" and r["payload"]["kind"] == "NO_TRADE")}
    return rows, counts


def fmt(v, pct=True):
    if v is None:
        return "—"
    return "%.3f%%" % (100 * v) if pct else "%s" % v


def status_page(registry, cfg, now, snapshot=None, base_dir=None, mode="forward"):
    from . import gate as G
    rows, counts = scorecard(registry, cfg)
    runs = registry.records("scan_run")
    last = runs[-1]["payload"] if runs else None
    recon = registry.records("reconciliation")
    notifs = registry.records("notification")
    dl = registry.records("delivery")
    sent = sum(1 for d in dl if d["payload"]["result"] == "sent")
    failed = sum(1 for d in dl if d["payload"]["result"] in ("failed", "rejected", "unknown"))
    by_ch = {}
    for d in dl:
        if d["payload"]["result"] == "sent":
            by_ch[d["payload"]["channel"]] = by_ch.get(d["payload"]["channel"], 0) + 1
    st = G.current_state(registry) or {"state": "ACTIVE"}
    kill = G.kill_flag_path(base_dir).exists() if base_dir else False
    L = ["# USD/JPY forward system: status (%s)" % ("DEMO" if mode == "demo" else "FORWARD"), "",
         "_Generated %s. EXPERIMENTAL SHADOW SYSTEM: paper only, internal simulator, indicative prices; no broker, no "
         "orders; nothing here is validated or financial advice._" % LC.et(now), "",
         "## System", "",
         "| Item | Value |", "|---|---|",
         "| Trading state | %s%s |" % (st["state"], " (%s)" % "; ".join(st.get("why", [])) if st.get("why") else ""),
         "| Kill switch | %s |" % ("ON" if kill else "off"),
         "| Last scan | %s |" % (LC.et(last["completed_utc"]) if last else "none yet"),
         "| Scans recorded | %d |" % len(runs),
         "| Scheduler | LaunchAgent at :02, :17, :32, :47; full scan hourly while FX is open, after each 17:00 ET bar, and every run while a setup or position is open |",
         "| Registry chain | %s (%d records) |" % ("intact" if registry.verify() is None else "BROKEN", registry.count()),
         "| Last reconciliation | %s |" % (("OK" if recon[-1]["payload"]["ok"] else "MISMATCH") + " " + LC.et(recon[-1]["created_utc"]) if recon else "none yet"),
         "| Notifications | %d queued in total; accepted by channel: %s; %d failed/unknown (the local channel is a test file, not a phone) |" % (
             len(notifs), ", ".join("%s %d" % (ch, n) for ch, n in sorted(by_ch.items())) or "none", failed),
         ""]
    obs = {o["specialist"]: o for o in (snapshot or {}).get("observations", []) if o.get("role") == "primary"}
    L += ["## Markets", "", "| Market | Price (indicative) | Freshness | Status | Role |", "|---|---|---|---|---|"]
    for spec, name, role in (("usdjpy", "USD/JPY", "forward test (shadow paper)"), ("gold", "Gold (GLD reference)", "observation alerts only"),
                             ("gbpusd", "GBP/USD", "monitoring only")):
        o = obs.get(spec, {})
        L.append("| %s | %s | %s | %s | %s |" % (name, o.get("last", "UNKNOWN"), o.get("freshness", "UNKNOWN"),
                                                 ((snapshot or {}).get("status") or {}).get(spec, "UNKNOWN"), role))
    L += ["", "## Open paper positions (shadow sub-ledgers, $%d each)" % cfg["sizing"]["start_usd"], "",
          "| Rule | Setup | Direction | Notional | Entry | Invalidation | Target | Equity |", "|---|---|---|---|---|---|---|---|"]
    S = obs.get("usdjpy", {}).get("last")
    anyopen = False
    for rule in cfg["rules"]:
        p = PP.state(registry, rule, cfg)
        if p["position"]:
            anyopen = True
            q = p["position"]
            L.append("| %s | %s | %s | $%.2f | %.3f | %.3f | %s | $%.2f |" % (rule, q["setup_id"], "long" if q["direction"] > 0 else "short",
                     q["notional_usd"], q["entry_price"], q["invalidation"], "%.3f" % q["target"] if q.get("target") else "none",
                     PP.equity(p, S or q["entry_mid"])))
    if not anyopen:
        L.append("| — | none | | | | | | |")
    L += ["", "## Opportunity history", "",
          "Detected setups %(detected)d · triggered %(triggered)d · blocked %(blocked)d · entered %(entered)d · resolved %(resolved)d · NO TRADE evaluations %(no_trade_evaluations)d" % counts,
          "", "| Setup | States | Notifications | Delivered |", "|---|---|---|---|"]
    by = {}
    for r in registry.records("setup_transition"):
        by.setdefault(r["payload"]["setup_id"], []).append(r["payload"]["state"])
    for sid, states in list(by.items())[-20:]:
        ns = [n for n in notifs if (n["payload"].get("fields") or {}).get("setup_id") == sid]
        dv = sum(1 for n in ns if any(d["payload"]["notification_id"] == n["record_id"] and d["payload"]["result"] == "sent" for d in dl))
        L.append("| %s | %s | %d | %d |" % (sid, " → ".join(states), len(ns), dv))
    if not by:
        L.append("| none yet | | | |")
    watch = registry.records("market_watch")
    L += ["", "MARKET WATCH triggers recorded: %d (alerted %d)." % (len(watch), sum(1 for w in watch if w["payload"].get("alerted"))), "",
          "## Scorecard (forward test; shadow; indicative prices; costs and financing estimated, unverified)", ""]
    for rule, r in rows.items():
        L += ["**%s** (%s; rules v%s: pre-registration v0.2 with the v0.3 source amendment)" % (
                  rule, cfg["forward_trials"][rule].split(" v0.2")[0] + cfg["forward_trials"][rule].split(" v0.2", 1)[-1],
                  cfg["rules"][rule]["version"]), "", "> %s" % r["banner"], "",
              "| Metric | Value |", "|---|---|",
              "| Resolved signals | %d |" % r["n"],
              "| Mean net return per signal (base / stress costs) | %s / %s |" % (fmt(r["mean_base"]), fmt(r["mean_stress"])),
              "| Median net return (base) | %s |" % fmt(r["median_base"]),
              "| Trade-level hit rate · average win · average loss | %s · %s · %s |" % (fmt(r["hit_rate_trades"]), fmt(r["avg_win"]), fmt(r["avg_loss"])),
              "| Directional accuracy | %s |" % fmt(r["dir_accuracy"]),
              "| Baselines, mean per signal (cash · always long · sample mean · simple trend · placebo) | %s |" % " · ".join(
                  fmt(r["baseline_means"][k]) for k in ("cash", "always_long", "historical_sample_mean", "simple_trend", "placebo_F001")),
              "| Statistics | %s |" % r["statistics"], "| Calibration | %s |" % r["calibration"], ""]
    return "\n".join(L) + "\n"
