"""USD/JPY forward system CLI (plain Python; no LLM; no orders; no broker).

  run                         what the LaunchAgent calls every 15 minutes: plans the run (scan / event poll / notify),
                              records gaps, catches up missed bars (DETECTED LATE), scores, writes the status page
  scan [--demo]               one scan now with OANDA practice (FX) + Alpaca IEX (SPY, GLD) data (v0.3 sources)
                              (--demo writes to the DEMO registry)
  kill --reason "<text>"      kill switch: HALTED now, flag file live/usdjpy/KILL_SWITCH, HIGH alert queued
  resume --confirm RESUME     manual re-enable only
  notify [--local-only]       queue the daily digest / liveness alerts if due, then deliver the outbox
                              (Pushover primary, ntfy fallback; --local-only uses only the local test file channel)
  test-alert --channel local|pushover|ntfy   send one clearly labelled TEST message through one channel
  score                       score closed paper positions (once each) and write the status page
                              live/usdjpy/STATUS.md (STATUS_DEMO.md with --demo)
  verify                      check the registry hash chain
  preflight                   readiness check now (READY / DEGRADED / BLOCKED with reasons); dry run, records nothing
  ticket SETUP_ID [--version N]   print a setup's copy-ready trade ticket (latest or a given version)
  backup snapshot|push|restore-test [--source published|local-git|offsite]|status
                              forward-registry snapshot (SQLite backup API, verified), restore test into tmp/, status
  status                      one-line state summary

Data (v0.3 amendment, 2026-10-29): OANDA v20 PRACTICE API (USD/JPY, GBP/USD; read-only pricing and candles) and
Alpaca market data (SPY, GLD; IEX). Yahoo is not used here (its terms prohibit automated collection). Financing
rates: FRED DTB3 and FRED IRSTCI01JPM156N (Japan call money, monthly), cached daily. Owner decision D1: trailing
windows may reach into 2024-2026 for computing live signals only; only digests and the values a rule used are stored,
in the registry under live/usdjpy/. Credentials are read from the Keychain at call time and never printed.
"""
import json
import subprocess
import sys
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from src import clock as K  # noqa: E402
from src.live_usdjpy import backup as BK  # noqa: E402
from src.live_usdjpy import gate as G  # noqa: E402
from src.live_usdjpy import lifecycle as LC  # noqa: E402
from src.live_usdjpy import notify as N  # noqa: E402
from src.live_usdjpy import scanner as S  # noqa: E402
from src.live_usdjpy.registry import Registry  # noqa: E402

CFG = yaml.safe_load((ROOT / "config.yaml").read_text())["live_usdjpy"]
BASE = ROOT / "live" / "usdjpy"
LOCK = BASE / "runner.lock"
LOGS = BASE / "logs"


def fetch_v03(now):
    """Completed daily bars and a snapshot from the v0.3 sources, keyed by their source symbols."""
    from src.live_usdjpy import sources as SR
    o, a = SR.Oanda(), SR.Alpaca()
    fx = {"USD_JPY": o.daily("USD_JPY"), "GBP_USD": o.daily("GBP_USD")}
    eq = a.daily(("SPY", "GLD"), now=now)
    snap = SR.snapshot(now, oanda=o, alpaca=a, fx_bars=fx, gld_bars=eq["GLD"])
    return {"USD_JPY": fx["USD_JPY"], "GBP_USD": fx["GBP_USD"], "SPY": eq["SPY"], "GLD": eq["GLD"]}, snap


def fetch_rates(now, st):
    """US 3-month T-bill (FRED DTB3) and Japan call money (FRED IRSTCI01JPM156N), annual decimals; cached per day."""
    day = now.date().isoformat()
    if st.get("rates_day") == day and st.get("rates"):
        return {k: tuple(v) for k, v in st["rates"].items()}
    import requests
    out = {}
    for key, sid in (("usd", "DTB3"), ("jpy", "IRSTCI01JPM156N")):
        try:
            r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s" % sid, timeout=30)
            rows = [l.split(",") for l in r.text.strip().splitlines()[1:]]
            rows = [x for x in rows if len(x) == 2 and x[1] not in (".", "")]
            out[key] = (float(rows[-1][1]) / 100.0, "FRED %s %s" % (sid, rows[-1][0]))
        except Exception as ex:
            out[key] = (None, "UNKNOWN (%s)" % type(ex).__name__)
    st["rates_day"], st["rates"] = day, {k: list(v) for k, v in out.items()}
    return out


def state_path(demo):
    return BASE / ("runner_state_demo.json" if demo else "runner_state.json")


def load_state(demo=False):
    try:
        return json.loads(state_path(demo).read_text())
    except Exception:
        return {}


def save_state(st, demo=False):
    sys.path.insert(0, str(ROOT / "tools"))
    from atomic_io import write_text
    write_text(state_path(demo), json.dumps(st, indent=1))


def rotate_logs(limit=5_000_000):
    for f in LOGS.glob("*.log") if LOGS.exists() else []:
        if f.stat().st_size > limit:
            f.write_text("[log truncated at %s; previous content exceeded %d bytes]\n" % (datetime.now(timezone.utc).isoformat(), limit))


def run(demo=False):
    """One LaunchAgent run (see src/live_usdjpy/runner.py for the plan). demo=True: DEMO registry, its own state
    file, notifications to the local test file only (never the phone)."""
    import fcntl
    import os
    from src.live_usdjpy import runner as RN
    from src.live_usdjpy import scorer as SC
    BASE.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    rotate_logs()
    lk = open(LOCK, "w")
    try:
        fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("RUN SKIPPED %s: the previous run is still active" % datetime.now(timezone.utc).isoformat(timespec="seconds"))
        return
    now = datetime.now(timezone.utc)
    st = load_state(demo)
    reg = registry(demo)
    mode = "demo" if demo else "forward"
    channels = [N.LocalFile(BASE / "outbox_local_demo.jsonl")] if demo else [N.Pushover(CFG["notifications"]["pushover"]), N.Ntfy(CFG["notifications"]["ntfy"])]
    done = []
    try:
        gap = RN.gap_record(st, now)
        if gap:
            reg.append("note", gap, idem_key="gap:%s" % gap["from_utc"], now=now)
            done.append("gap %.0f min recorded" % gap["minutes"])
        ev_p = ROOT / "live" / "events" / "events.json"
        events = json.loads(ev_p.read_text()) if ev_p.exists() else {"events": {}}
        today = now.astimezone(RN.NY).date().isoformat()
        rel = [datetime.fromisoformat(e["scheduled_time_utc"]) for e in (events.get("events") or {}).values()
               if e.get("scheduled_time_utc") and str(e.get("scheduled_date")) == today]
        from src.live_usdjpy import lifecycle as LCm, paper as PPm
        active = bool([s_ for s_ in LCm.open_setups(reg).values() if s_["state"] in ("triggered", "blocked", "entered")]) or \
            any(PPm.state(reg, r_, CFG)["position"] for r_ in CFG["rules"])
        tasks, why = RN.plan(now, st, active, rel)
        if "events" in tasks:
            env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": os.environ.get("HOME", "")}
            bls = N.secret("trading-research-bls-contact")
            if bls:
                env["BLS_CONTACT_EMAIL"] = bls
            r = subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "events.py"), "poll"], env=env,
                               capture_output=True, text=True, timeout=600)
            del env
            st["last_events_poll_utc"] = now.isoformat()
            events = json.loads(ev_p.read_text()) if ev_p.exists() else events
            done.append("events poll exit %d%s" % (r.returncode, "" if bls else " (BLS contact not configured: BLS skipped)"))
        if "scan" in tasks:
            from src.live_usdjpy import preflight as PF
            fetch_error = None
            try:
                bars, snap = fetch_v03(now)
            except Exception as ex:                                  # fail closed below; observation and reporting go on
                bars, snap, fetch_error = None, None, "%s: %s" % (type(ex).__name__, str(ex)[:160])
            rates = fetch_rates(now, st)
            pf = PF.check(now, reg, snap, bars, events, st, CFG["preflight"], fetch_error=fetch_error,
                          kill_on=G.kill_flag_path(BASE).exists(),
                          backup_problems=[] if demo else BK.problems(reg, now, CFG["backup"], ROOT),
                          channels_configured=any(ch.configured() for ch in channels))
            PF.record(reg, now, pf, CFG["preflight"], "%s:%s" % (mode, now.strftime("%Y%m%dT%H%M")))
            done.append("preflight %s" % PF.summary(pf)[:300])
            st["last_preflight"] = {"verdict": pf["verdict"], "at_utc": pf["at_utc"], "summary": PF.summary(pf)[:600]}
        if "scan" in tasks and bars is not None:
            reasons = {}
            for c_ in pf["checks"]:
                for b_ in c_["blocks"]:
                    reasons.setdefault(b_, []).append("%s: %s" % (c_["check"], c_["detail"]))
            out = S.run_scan(reg, now, S.ScanInputs(snapshot=snap, bars=bars, events_store=events, mode=mode,
                                                    rates=rates, fx_prefiltered=True, blocks=tuple(pf["blocks"]),
                                                    block_reasons=reasons), CFG, BASE)
            st["last_scan_utc"] = now.isoformat()
            ujb = S.completed(bars.get("USD_JPY"), "complete", now)
            st["last_bar_seen"] = ujb.index[-1].date().isoformat() if ujb is not None and len(ujb) else st.get("last_bar_seen")
            st["last_snapshot"] = {"generated_utc": snap.get("generated_utc"), "status": snap.get("status"),
                                   "observations": [{k: o.get(k) for k in ("specialist", "role", "freshness", "source_ts_utc")}
                                                    for o in snap.get("observations", [])]}
            SC.score_closed(reg, CFG, now)
            sys.path.insert(0, str(ROOT / "tools"))
            from atomic_io import write_text
            write_text(BASE / ("STATUS_DEMO.md" if demo else "STATUS.md"), SC.status_page(reg, CFG, now, snap, BASE, mode))
            done.append("scan %s" % json.dumps({k: out.get(k) for k in ("evaluations", "transitions", "gate", "watch", "reconciled", "duplicate",
                                                                      "deferred_evaluation", "position_monitoring", "tickets") if k in out}, default=str))
        if not demo:                                                # forward registry only: verified snapshot once a day
            bcfg = CFG["backup"]
            if BK.due(reg, now, bcfg):
                res = BK.snapshot(reg, now, bcfg, ROOT)
                BK.record(reg, now, res)
                done.append("backup %s" % ("OK (%s records)" % res["records"] if res["ok"] else "FAILED: %s" % res.get("error")))
                if res["ok"] and bcfg.get("daily_offsite_push"):        # owner decision 2026-10-30 (option c)
                    push = BK.offsite_push(ROOT, now)
                    BK.record(reg, now, push)
                    done.append("off-site push %s" % ("OK" if push["ok"] else "FAILED: %s" % push.get("result")))
            if BK.health(reg, now, bcfg, ROOT):
                done.append("backup health problem alerted")
        if not demo:
            from src.live_usdjpy import releases as RLm
            rel_new = RLm.queue(reg, now, events, CFG["official_release_alerts"])
            if rel_new:
                done.append("official release alerts %d" % len(rel_new))
        ncfg = CFG["notifications"]
        snap_for_digest = st.get("last_snapshot") or {}
        pos = [r_ for r_ in CFG["rules"] if PPm.state(reg, r_, CFG)["position"]]
        N.queue_digest(reg, now, ncfg, snap_for_digest, positions=", ".join(pos) or "none",
                       extra=None if demo else BK.summary_line(reg, now, CFG["backup"], ROOT))
        sent = N.dispatch(reg, now, channels, ncfg)                 # deliver first: a digest queued this run counts
        if N.check_liveness(reg, now, ncfg, fx_open=K.fx_market_open(now), position_open=bool(pos)):
            sent += N.dispatch(reg, now, channels, ncfg)           # deliver any liveness alert raised just now
        if not demo:                                                # Pushover emergency receipts (HIGH alerts only)
            rec_ = N.poll_receipts(reg, now, channels[0])
            if rec_:
                done.append("receipts %s" % ", ".join(r for _, r in rec_))
        done.append("notify %d action(s)" % len(sent))
        st["last_run_utc"] = now.isoformat()
        st.pop("last_error", None)
        save_state(st, demo)
        print("RUN OK %s | %s | %s" % (now.isoformat(timespec="seconds"), "; ".join(why) or "notify only", "; ".join(done)))
    except Exception as ex:
        msg = "%s: %s" % (type(ex).__name__, str(ex)[:200])
        try:
            reg.append("notification", LC.alert("HIGH", "RUNNER ERROR: %s" % type(ex).__name__,
                                                **{"class": "RISK/SYSTEM ALERT", "event_time_et": LC.et(now), "why_sent": msg}),
                       idem_key="runner-error:%s:%s" % (type(ex).__name__, now.strftime("%Y%m%dT%H")), now=now)
            N.dispatch(reg, now, channels, CFG["notifications"])
        except Exception:
            pass
        st["last_run_utc"] = now.isoformat()
        st["last_error"] = msg
        save_state(st, demo)
        print("RUN ERROR %s | %s" % (now.isoformat(timespec="seconds"), msg))
        sys.exit(1)
    finally:
        reg.close()
        fcntl.flock(lk, fcntl.LOCK_UN)
        lk.close()


def registry(demo):
    return Registry(ROOT / (CFG["demo_registry"] if demo else CFG["registry"]))


def main(a):
    cmd = a[1] if len(a) > 1 else ""
    demo = "--demo" in a
    if cmd == "run":
        run(demo)
    elif cmd == "scan":
        now = datetime.now(timezone.utc)
        ev_p = ROOT / "live" / "events" / "events.json"
        events = json.loads(ev_p.read_text()) if ev_p.exists() else {"events": {}}
        bars, snap = fetch_v03(now)
        reg = registry(demo)
        out = S.run_scan(reg, now, S.ScanInputs(snapshot=snap, bars=bars, events_store=events, mode="demo" if demo else "forward",
                                                rates=fetch_rates(now, {}), fx_prefiltered=True), CFG, BASE)
        reg.close()
        print("SCAN %s: %s" % ("DEMO" if demo else "FORWARD", json.dumps(out, default=str)))
    elif cmd == "kill":
        reg = registry(demo)
        f = G.kill(reg, BASE, a[a.index("--reason") + 1] if "--reason" in a else "manual kill switch")
        reg.close()
        print("KILL SWITCH ON: new paper entries halted; flag %s; HIGH alert queued" % f.relative_to(ROOT))
    elif cmd == "resume":
        reg = registry(demo)
        G.resume(reg, BASE, a[a.index("--confirm") + 1] if "--confirm" in a else "")
        reg.close()
        print("RESUMED: state ACTIVE (manual)")
    elif cmd in ("notify", "test-alert"):
        now = datetime.now(timezone.utc)
        ncfg = CFG["notifications"]
        reg = registry(demo)
        local = N.LocalFile(BASE / ("outbox_local_demo.jsonl" if demo else "outbox_local.jsonl"))
        named = {"local": local, "pushover": N.Pushover(ncfg["pushover"]), "ntfy": N.Ntfy(ncfg["ntfy"])}
        if cmd == "test-alert":
            ch = named[a[a.index("--channel") + 1]]
            reg.append("notification", LC.alert("NORMAL", "TEST message from trading-research (%s)" % ch.name,
                                                summary="TEST | %s channel works | no action needed" % ch.name,
                                                **{"class": "TEST", "event_time_et": LC.et(now),
                                                   "why_sent": "channel test requested by the owner"}),
                       idem_key="test:%s:%s" % (ch.name, now.strftime("%Y%m%dT%H%M")), now=now)
            channels = [ch]
        else:
            snap_p = ROOT / "live" / "intel" / "latest.json"
            snap = json.loads(snap_p.read_text()) if snap_p.exists() else {}
            N.queue_digest(reg, now, ncfg, snap)
            channels = [local] if "--local-only" in a else [named[ncfg["primary"]], named[ncfg["fallback"]]]
        out = N.dispatch(reg, now, channels, ncfg)
        if cmd == "notify" and N.check_liveness(reg, now, ncfg, fx_open=K.fx_market_open(now)):
            out += N.dispatch(reg, now, channels, ncfg)
        for nid, outcome in out:
            print("NOTIFY %s: %s" % (nid, outcome))
        reg.close()
    elif cmd == "score":
        from src.live_usdjpy import scorer as SC
        sys.path.insert(0, str(ROOT / "tools"))
        from atomic_io import write_text
        now = datetime.now(timezone.utc)
        reg = registry(demo)
        new = SC.score_closed(reg, CFG, now)
        snap_p = ROOT / "live" / "intel" / "latest.json"
        snap = json.loads(snap_p.read_text()) if snap_p.exists() else {}
        page = BASE / ("STATUS_DEMO.md" if demo else "STATUS.md")
        write_text(page, SC.status_page(reg, CFG, now, snap, BASE, "demo" if demo else "forward"))
        reg.close()
        print("SCORE OK: %d newly scored; status page %s" % (len(new), page.relative_to(ROOT)))
    elif cmd == "verify":
        reg = registry(demo)
        v = reg.verify()
        print("REGISTRY %s: %s (%d records)" % ("DEMO" if demo else "FORWARD", "chain intact" if v is None else "BROKEN: " + v,
                                               reg.count()))
        reg.close()
        sys.exit(0 if v is None else 1)
    elif cmd == "status":
        reg = registry(demo)
        st = G.current_state(reg) or {"state": "ACTIVE"}
        runs = reg.records("scan_run")
        print("STATE %s | kill switch %s | scans %d | last scan %s | records %d" % (
            st["state"], "ON" if G.kill_flag_path(BASE).exists() else "off", len(runs),
            runs[-1]["payload"]["completed_utc"] if runs else "none", reg.count()))
        reg.close()
    elif cmd == "preflight":                        # dry run: fetch, check, print; records nothing
        from src.live_usdjpy import preflight as PF
        now = datetime.now(timezone.utc)
        reg = registry(demo)
        ev_p = ROOT / "live" / "events" / "events.json"
        events = json.loads(ev_p.read_text()) if ev_p.exists() else {}
        err = None
        try:
            bars, snap = fetch_v03(now)
        except Exception as ex:
            bars, snap, err = None, None, "%s: %s" % (type(ex).__name__, str(ex)[:160])
        pf = PF.check(now, reg, snap, bars, events, load_state(demo), CFG["preflight"], fetch_error=err,
                      kill_on=G.kill_flag_path(BASE).exists(), backup_problems=BK.problems(reg, now, CFG["backup"], ROOT))
        for c_ in pf["checks"]:
            print("%-9s %-20s %s" % (c_["status"], c_["check"], c_["detail"]))
        print("PREFLIGHT %s" % PF.summary(pf))
        reg.close()
    elif cmd == "ticket":                           # print the latest (or --version n) copy-ready ticket of a setup
        from src.live_usdjpy import alerts as AL
        reg = registry(demo)
        sid = a[2] if len(a) > 2 else ""
        tk = [r["payload"] for r in reg.records("ticket") if r["payload"]["setup_id"] == sid]
        if "--version" in a:
            tk = [t for t in tk if t["version"] == int(a[a.index("--version") + 1])]
        print(tk[-1]["text"] if tk else "no ticket for %r (tickets exist once a setup triggers)" % sid)
        reg.close()
    elif cmd == "backup":
        sub = a[2] if len(a) > 2 else "status"
        bcfg = CFG["backup"]
        reg = registry(False)
        now = datetime.now(timezone.utc)
        if sub == "snapshot":                       # manual snapshot; takes the runner's lock so no scan writes meanwhile
            import fcntl
            with open(LOCK, "w") as lk:
                fcntl.flock(lk, fcntl.LOCK_EX)
                res = BK.snapshot(reg, now, bcfg, ROOT)
                BK.record(reg, now, res)
            print("BACKUP SNAPSHOT %s: %s" % ("OK" if res["ok"] else "FAILED", json.dumps(
                {k: res.get(k) for k in ("records", "integrity", "chain", "sha256", "published", "error")})))
        elif sub == "push":                           # manual off-site push (same as the runner's daily push), under the lock
            import fcntl
            with open(LOCK, "w") as lk:
                fcntl.flock(lk, fcntl.LOCK_EX)
                res = BK.offsite_push(ROOT, now)
                BK.record(reg, now, res)
            print("OFF-SITE PUSH %s: %s" % ("OK" if res["ok"] else "FAILED", res["result"]))
        elif sub == "restore-test":
            src = a[a.index("--source") + 1] if "--source" in a else "published"
            res = BK.restore_test(ROOT, bcfg, reg, source=src)
            BK.record(reg, now, res)
            print("RESTORE TEST %s: %s" % ("PASS" if res["ok"] else "FAIL", json.dumps(
                {k: res.get(k) for k in ("source", "records", "integrity", "chain", "matches_live_prefix", "temp_folder_removed", "error")})))
        else:
            print(BK.summary_line(reg, now, bcfg, ROOT))
        reg.close()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
