"""Private backup of paper/, live/ and briefs/ ONLY, to a PRIVATE GitHub repo (user decision 2026-10-23).

A separate git database (.backup.git, ignored by the main repository) uses the project folder as its work tree, but
only ever stages paper/, live/ and briefs/. Before every commit the full index is checked against that allowlist and the
run aborts if anything else (data/, src/, ...) is present. Credentials are never stored or handled here: the push uses
git's existing credential helper (macOS Keychain, per-repository because credential.useHttpPath=true) and never prompts.

Commands:
  init --remote URL     create .backup.git (once) with the noreply identity and the remote; no network access
  run                   stage the allowed folders, verify, commit if anything changed, push, confirm GitHub's main
Exit code 0 = BACKUP OK, 1 = BACKUP FAILED (reason printed; the Sunday run reports it in the brief).
"""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = ("paper/", "live/", "briefs/")
EXCLUDE = (":(exclude)live/events/cache/**",)    # Phase H: cached official web pages are re-fetchable; not backed up
NAME, EMAIL = "Garlen Woest", "324629888+GarlenWoest@users.noreply.github.com"
ET = ZoneInfo("America/New_York")


def git(gitdir, worktree, *args, check=True, timeout=120):
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
    r = subprocess.run(["git", "--git-dir", str(gitdir), "--work-tree", str(worktree), *args], cwd=worktree,
                       capture_output=True, text=True, env=env, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args[:2]), (r.stderr or r.stdout).strip()[:300]))
    return r


def init(gitdir, worktree, remote):
    if gitdir.exists():
        sys.exit("%s already exists" % gitdir)
    subprocess.run(["git", "init", "--bare", "-q", str(gitdir)], check=True)
    for k, v in (("core.bare", "false"), ("user.name", NAME), ("user.email", EMAIL), ("credential.useHttpPath", "true"),
                 ("commit.gpgsign", "false")):
        git(gitdir, worktree, "config", k, v)
    git(gitdir, worktree, "symbolic-ref", "HEAD", "refs/heads/main")
    git(gitdir, worktree, "remote", "add", "origin", remote)
    print("created %s (remote %s)" % (gitdir, remote))


def disallowed(paths):
    return [p for p in paths if p and not p.startswith(ALLOWED)]


def stage_and_verify(gitdir, worktree):
    present = [d.rstrip("/") for d in ALLOWED if (worktree / d).exists()]
    if present:
        git(gitdir, worktree, "add", "-A", "-f", "--", *present, ":(exclude)**/.DS_Store", *EXCLUDE)
    tracked = git(gitdir, worktree, "ls-files").stdout.splitlines()
    bad = disallowed(tracked)
    if bad:
        git(gitdir, worktree, "rm", "-r", "-q", "--cached", "--", *bad, check=False)
        raise RuntimeError("refused: files outside paper/, live/, briefs/ were staged: %s" % bad[:5])
    return tracked


def run(gitdir, worktree):
    if not gitdir.exists():
        raise RuntimeError("backup not initialised (run: init --remote URL)")
    tracked = stage_and_verify(gitdir, worktree)
    changed = git(gitdir, worktree, "diff", "--cached", "--quiet", check=False).returncode != 0
    has_head = git(gitdir, worktree, "rev-parse", "--verify", "-q", "HEAD", check=False).returncode == 0
    if changed or not has_head:
        stamp = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
        git(gitdir, worktree, "commit", "-q", "-m", "Snapshot of paper/, live/, briefs/ at %s (PAPER, FICTIONAL MONEY)" % stamp)
    head = git(gitdir, worktree, "rev-parse", "HEAD").stdout.strip()
    git(gitdir, worktree, "push", "-q", "origin", "main", timeout=90)
    remote = git(gitdir, worktree, "ls-remote", "origin", "refs/heads/main", timeout=60).stdout.split()
    if not remote or remote[0] != head:
        raise RuntimeError("pushed, but GitHub main is %s, not %s" % (remote[0][:7] if remote else "missing", head[:7]))
    return head, len(tracked), changed or not has_head


if __name__ == "__main__":
    a = sys.argv
    wt = Path(a[a.index("--work-tree") + 1]) if "--work-tree" in a else ROOT
    gd = Path(a[a.index("--git-dir") + 1]) if "--git-dir" in a else ROOT / ".backup.git"
    for p in (wt, gd):
        if not str(p.resolve()).startswith(str(ROOT.resolve())):
            sys.exit("paths must be inside the project")
    if len(a) > 1 and a[1] == "init":
        init(gd, wt, a[a.index("--remote") + 1])
    elif len(a) > 1 and a[1] == "run":
        try:
            head, n, new = run(gd, wt)
            print("BACKUP OK: %s %s; GitHub private main = %s (%d files)" % (
                "committed and pushed" if new else "nothing new; confirmed", head[:7], head[:7], n))
        except Exception as e:                      # report, never retry with other credentials
            print("BACKUP FAILED: %s" % str(e)[:300])
            sys.exit(1)
    else:
        sys.exit(__doc__)
