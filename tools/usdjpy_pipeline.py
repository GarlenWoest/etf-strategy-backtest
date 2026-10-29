"""USD/JPY forward system CLI (plain Python; no LLM; no orders; no broker).

  scan [--demo]               refresh the market snapshot, fetch completed daily bars, run one scan
                              (--demo writes to the DEMO registry; the forward registry starts at activation, step 9)
  kill --reason "<text>"      kill switch: HALTED now, flag file live/usdjpy/KILL_SWITCH, HIGH alert queued
  resume --confirm RESUME     manual re-enable only
  notify [--local-only]       queue the daily digest / liveness alerts if due, then deliver the outbox
                              (Pushover primary, ntfy fallback; --local-only uses only the local test file channel)
  test-alert --channel local|pushover|ntfy   send one clearly labelled TEST message through one channel
  verify                      check the registry hash chain
  status                      one-line state summary

Daily bars come from Yahoo Finance via yfinance (indicative; not executable). Owner decision D1 (2026-10-29): trailing
windows may reach into 2024-2026 for computing live signals only; they are held in memory and only digests and the
values a rule used are stored, in the registry under live/usdjpy/. Nothing is written outside live/usdjpy/ except the
snapshot that tools/market_intel.py itself writes to live/intel/.
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
from src.live_usdjpy import gate as G  # noqa: E402
from src.live_usdjpy import lifecycle as LC  # noqa: E402
from src.live_usdjpy import notify as N  # noqa: E402
from src.live_usdjpy import scanner as S  # noqa: E402
from src.live_usdjpy.registry import Registry  # noqa: E402

CFG = yaml.safe_load((ROOT / "config.yaml").read_text())["live_usdjpy"]
BASE = ROOT / "live" / "usdjpy"
SYMBOLS = ["JPY=X", "SPY", "GLD", "GBPUSD=X"]


def fetch_bars(now):
    import pandas as pd
    import yfinance as yf
    df = yf.download(SYMBOLS, start=(now - timedelta(days=620)).date().isoformat(), auto_adjust=False, progress=False,
                     threads=False)
    out = {}
    for s in SYMBOLS:
        c = df["Close"][s].dropna()
        c.index = pd.to_datetime(c.index).tz_localize(None).normalize()
        out[s] = c
    return out


def registry(demo):
    return Registry(ROOT / (CFG["demo_registry"] if demo else CFG["registry"]))


def main(a):
    cmd = a[1] if len(a) > 1 else ""
    demo = "--demo" in a
    if cmd == "scan":
        now = datetime.now(timezone.utc)
        r = subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "market_intel.py"), "snapshot"],
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            print("SCAN WARNING: snapshot refresh failed (exit %d); using the last snapshot on file" % r.returncode)
        snap = json.loads((ROOT / "live" / "intel" / "latest.json").read_text())
        ev_p = ROOT / "live" / "events" / "events.json"
        events = json.loads(ev_p.read_text()) if ev_p.exists() else {"events": {}}
        bars = fetch_bars(now)
        reg = registry(demo)
        out = S.run_scan(reg, now, S.ScanInputs(snapshot=snap, bars=bars, events_store=events,
                                                mode="demo" if demo else "forward"), CFG, BASE)
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
                                                **{"class": "RISK/SYSTEM ALERT", "event_time_et": LC.et(now),
                                                   "why_sent": "channel test requested by the owner"}),
                       idem_key="test:%s:%s" % (ch.name, now.strftime("%Y%m%dT%H%M")), now=now)
            channels = [ch]
        else:
            snap_p = ROOT / "live" / "intel" / "latest.json"
            snap = json.loads(snap_p.read_text()) if snap_p.exists() else {}
            N.queue_digest(reg, now, ncfg, snap)
            N.check_liveness(reg, now, ncfg, fx_open=K.fx_market_open(now))
            channels = [local] if "--local-only" in a else [named[ncfg["primary"]], named[ncfg["fallback"]]]
        for nid, outcome in N.dispatch(reg, now, channels, ncfg):
            print("NOTIFY %s: %s" % (nid, outcome))
        reg.close()
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
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
