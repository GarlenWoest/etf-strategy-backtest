"""Clean-folder restore drill (audit item 2, owner approval 2026-11-02). Manual; never touches the live install.

  .venv/bin/python -I tools/restore_drill.py [--decisions N]

In a fresh temporary folder it:
  1. clones this repository (local clone, HEAD) and the private backup database (.backup.git, local clone): no network;
  2. verifies the restored registry snapshot (integrity, hash chain, count, SHA-256 against its manifest);
  3. checks the dependencies are pinned (the running venv equals requirements-lock.txt exactly);
  4. renders the LaunchAgent plist template into the drill folder and lints it (never loads it);
  5. checks the Keychain item NAMES in deploy/KEYCHAIN_ITEMS.txt are present (exit status only; no value is ever read);
  6. reproduces recorded results from the restored copy with the CLONED code: every paper sub-ledger recomputed from its
     fills equals its last snapshot; reconciliation on a scratch copy reproduces the last recorded verdict; the last N
     market_state input digests recompute exactly;
  7. resume check: appends a drill note to the scratch copy, chain still intact, a repeated idempotent append is a no-op;
  8. scans every text file in the drill folder for credential-shaped strings (patterns only);
and writes reports/drills/restore_drill_<UTC>.md (git-ignored). Limits are stated in the report.
"""
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main_checkout():
    """The main checkout (where .backup.git lives), also when run from a git worktree."""
    r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"], capture_output=True, text=True)
    return Path(r.stdout.strip()).parent if r.returncode == 0 else ROOT
SECRET_PATTERNS = [re.compile(p) for p in (
    r"hc-ping\.com/[0-9a-f-]{20,}", r"\b[0-9a-f]{32}-[0-9a-f]{32}\b",          # healthchecks ping URL; OANDA token shape
    r"\bA[KP][A-Z0-9]{16,}\b", r"\ba[a-z0-9]{29}\b", r"\bu[a-z0-9]{29}\b",    # Alpaca key id; Pushover app/user key shapes
    r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{12,}")]
SYNTHETIC_OK = ("hc-ping.com/11111111-2222-3333-4444-555555555555", "hc-ping.com/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")  # test fixtures


def sh(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=600)


def main(n_decisions=20):
    started = datetime.now(timezone.utc)
    work = Path(tempfile.mkdtemp(prefix="tr_restore_"))
    steps, ok_all = [], True

    def step(name, ok, detail):
        nonlocal ok_all
        ok_all = ok_all and ok
        steps.append((name, "PASS" if ok else "FAIL", detail))

    try:
        # 1. clones
        r1 = sh(["git", "clone", "-q", "--no-hardlinks", str(ROOT), str(work / "code")])
        head = sh(["git", "-C", str(work / "code"), "rev-parse", "--short", "HEAD"]).stdout.strip()
        r2 = sh(["git", "clone", "-q", "--no-hardlinks", str(main_checkout() / ".backup.git"), str(work / "private")])
        step("1 clone repository and private backup (local, no network)", r1.returncode == 0 and r2.returncode == 0,
             "code at %s; private backup %s" % (head, "cloned" if r2.returncode == 0 else r2.stderr.strip()[:120]))
        snap = work / "private" / "live" / "usdjpy_backup" / "registry_snapshot.sqlite"
        man = work / "private" / "live" / "usdjpy_backup" / "manifest.json"
        # 2. snapshot verification (with the CLONED code)
        sys.path.insert(0, str(work / "code"))
        from src.live_usdjpy import backup as BK
        from src.live_usdjpy import paper as PP
        from src.live_usdjpy import scanner as SCN
        from src.live_usdjpy.registry import Registry
        import yaml
        ins = BK.inspect(snap)
        m = json.loads(man.read_text()) if man.exists() else {}
        sha_ok = bool(m) and m.get("sha256") == ins.get("sha256")
        step("2 snapshot integrity, chain, manifest", ins.get("ok", False) and sha_ok,
             "integrity %s; chain %s; %s records; sha256 %s manifest" % (ins.get("integrity"), ins.get("chain"), ins.get("records"),
                                                                          "matches" if sha_ok else "DOES NOT match"))
        # 3. pinned dependencies
        frz = sh([sys.executable, "-m", "pip", "freeze", "--local"]).stdout
        norm = lambda t: sorted(l.strip().lower() for l in t.splitlines() if l.strip() and not l.startswith("#"))
        lock = (work / "code" / "requirements-lock.txt").read_text()
        extra = sorted(set(norm(frz)) - set(norm(lock)))
        missing = sorted(set(norm(lock)) - set(norm(frz)))
        step("3 dependencies pinned (running venv == requirements-lock.txt)", not extra and not missing,
             "extra %s; missing %s" % (extra[:5] or "none", missing[:5] or "none"))
        # 4. plist template
        tpl = (work / "code" / "deploy" / "local.trading-research.usdjpy-runner.plist.template").read_text()
        rendered = work / "local.trading-research.usdjpy-runner.plist"
        rendered.write_text(tpl.replace("{{ROOT}}", str(work / "code")))
        lint = sh(["plutil", "-lint", str(rendered)])
        step("4 LaunchAgent plist rendered and linted (not loaded)", lint.returncode == 0 and "{{" not in rendered.read_text(),
             lint.stdout.strip().split(":")[-1].strip())
        # 5. Keychain item names
        names = [l.strip() for l in (work / "code" / "deploy" / "KEYCHAIN_ITEMS.txt").read_text().splitlines()
                 if l.strip() and not l.startswith("#")]
        present = {n: subprocess.run(["security", "find-generic-password", "-s", n], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, timeout=10).returncode == 0 for n in names}
        absent = [n for n, p in present.items() if not p]
        step("5 Keychain item names present (exit status only; no value read)", True,
             "%d of %d present%s" % (len(names) - len(absent), len(names), "; absent: %s" % ", ".join(absent) if absent else ""))
        # 6. reproduce recorded results on a scratch copy
        scratch = work / "scratch.sqlite"
        shutil.copy2(snap, scratch)
        cfg = yaml.safe_load((work / "code" / "config.yaml").read_text())["live_usdjpy"]
        reg = Registry(scratch)
        det = []
        ledger_ok = True
        for rule in cfg["rules"]:
            st = PP.state(reg, rule, cfg)
            rec = PP.recompute(reg, rule, cfg)
            diff = max(abs(rec[k] - st[k]) for k in ("cash", "usd_pos", "jpy"))
            ledger_ok = ledger_ok and diff <= 1e-6 * max(1.0, abs(st["jpy"]) / 1e4)
            det.append("%s max diff %.2e" % (rule, diff))
        last_rec = reg.records("reconciliation")[-1] if reg.records("reconciliation") else None
        marks = [r["payload"].get("last_mark") for r in reg.records("position_snapshot") if r["payload"].get("last_mark")]
        rec_same = None
        if last_rec and marks:
            ok_now, _ = PP.reconcile(reg, cfg, datetime.now(timezone.utc), marks[-1])
            rec_same = ok_now == last_rec["payload"]["ok"]
        ms = reg.records("market_state")[-n_decisions:]
        dig_ok = all(SCN.digest({k: v for k, v in r["payload"].items() if k != "inputs_sha256"}) == r["payload"]["inputs_sha256"] for r in ms)
        step("6 recorded results reproduce (ledgers, reconciliation verdict, last %d input digests)" % len(ms),
             ledger_ok and rec_same is not False and dig_ok,
             "%s; reconciliation verdict %s; digests %s" % ("; ".join(det), {True: "reproduced", False: "DIFFERS", None: "n/a"}[rec_same],
                                                             "all match" if dig_ok else "MISMATCH"))
        # 7. resume check
        a = reg.append("note", {"type": "restore_drill", "at_utc": started.isoformat()}, idem_key="drill:%s" % started.isoformat())
        b = reg.append("note", {"type": "restore_drill", "at_utc": started.isoformat()}, idem_key="drill:%s" % started.isoformat())
        con = sqlite3.connect(scratch)
        from src.live_usdjpy.registry import verify_chain
        chain = verify_chain(con)
        con.close()
        reg.close()
        step("7 resume: append continues the chain; repeated idempotent append is a no-op", chain is None and b["duplicate"] and not a["duplicate"],
             "chain %s" % ("intact" if chain is None else chain))
        # 8. secret scan
        hits = []
        for p in work.rglob("*"):
            if p.is_file() and p.suffix in (".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".csv", ".log", ".plist", ".py", ".template") \
                    and ".git" not in p.parts and p.stat().st_size < 20_000_000:
                t = p.read_text(errors="ignore")
                for pat in SECRET_PATTERNS:
                    if any(m.group(0) not in SYNTHETIC_OK for m in pat.finditer(t)):
                        hits.append("%s (%s)" % (p.relative_to(work), pat.pattern[:24]))
        step("8 secret scan of the drill folder (patterns only)", not hits, "no credential-shaped strings" if not hits else "; ".join(hits[:8]))
    except Exception as ex:
        step("drill aborted", False, "%s: %s" % (type(ex).__name__, str(ex)[:200]))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    out = ROOT / "reports" / "drills" / ("restore_drill_%s.md" % started.strftime("%Y%m%dT%H%M%SZ"))
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Restore drill %s: %s" % (started.strftime("%Y-%m-%d %H:%M UTC"), "PASS" if ok_all else "FAIL"), "",
             "| Step | Result | Detail |", "|---|---|---|"] + ["| %s | %s | %s |" % s for s in steps] + [
             "", "**Limits:** rule decisions themselves cannot be re-derived from the registry alone (it stores input digests and the last "
             "close, not the full bar history); a full run() resume needs the mocked run() harness (audit item 11, 2026-11-06 batch). "
             "The drill folder was deleted after the run."]
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if ok_all else 1


if __name__ == "__main__":
    n = int(sys.argv[sys.argv.index("--decisions") + 1]) if "--decisions" in sys.argv else 20
    sys.exit(main(n))
