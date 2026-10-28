"""Private backup: only paper/, live/, briefs/ are ever committed; anything else is refused. Uses a local bare repo as
the remote (no network, no credentials)."""
import importlib.util
import shutil
import subprocess

import pytest

from src import PROJECT_ROOT

spec = importlib.util.spec_from_file_location("bk", PROJECT_ROOT / "tools" / "backup_private.py")
BK = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BK)
T = PROJECT_ROOT / "tmp" / "test_backup"


@pytest.fixture
def setup():
    shutil.rmtree(T, ignore_errors=True)
    wt, remote, gd = T / "wt", T / "remote.git", T / "wt" / ".backup.git"
    for f, txt in {"data/raw/prices.csv": "x", "src/code.py": "y", "research_log.csv": "z", "paper/state.json": "{}",
                   "paper/book_b_journal.md": "# j", "paper/.DS_Store": "junk", "live/heartbeat.json": "{}",
                   "briefs/2026-10-25.md": "# b", ".gitignore": "data/raw/*\npaper/\nlive/\nbriefs/\n.backup.git/\n"}.items():
        (wt / f).parent.mkdir(parents=True, exist_ok=True)
        (wt / f).write_text(txt)
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(remote)], check=True)
    BK.init(gd, wt, str(remote))
    yield wt, remote, gd
    shutil.rmtree(T, ignore_errors=True)


def test_only_allowed_folders_are_pushed(setup):
    wt, remote, gd = setup
    head, n, new = BK.run(gd, wt)
    files = subprocess.run(["git", "--git-dir", str(remote), "ls-tree", "-r", "--name-only", "main"],
                           capture_output=True, text=True, check=True).stdout.split()
    assert sorted(files) == ["briefs/2026-10-25.md", "live/heartbeat.json", "paper/book_b_journal.md", "paper/state.json"]
    assert new and n == 4
    log = subprocess.run(["git", "--git-dir", str(remote), "log", "--format=%ae %ce", "main"], capture_output=True,
                         text=True, check=True).stdout.split()
    assert set(log) == {BK.EMAIL}


def test_second_run_without_changes_commits_nothing(setup):
    wt, remote, gd = setup
    h1, _, _ = BK.run(gd, wt)
    h2, _, new = BK.run(gd, wt)
    assert h1 == h2 and not new


def test_anything_outside_the_allowlist_is_refused(setup):
    wt, remote, gd = setup
    BK.git(gd, wt, "add", "-f", "data/raw/prices.csv")          # simulate an accidental stage
    with pytest.raises(RuntimeError, match="refused"):
        BK.run(gd, wt)
    assert "data/raw/prices.csv" not in BK.git(gd, wt, "ls-files").stdout   # and it was unstaged again
    head, n, _ = BK.run(gd, wt)
    assert n == 4


def test_disallowed_helper():
    assert BK.disallowed(["paper/a", "data/b", "briefs/c", "src/x.py"]) == ["data/b", "src/x.py"]


def test_push_failure_is_reported_not_retried(setup):
    wt, remote, gd = setup
    shutil.rmtree(remote)                                         # remote unreachable
    with pytest.raises(RuntimeError, match="git push"):
        BK.run(gd, wt)


def test_event_cache_is_not_backed_up(setup):
    wt, remote, gd = setup
    (wt / "live" / "events" / "cache").mkdir(parents=True)
    (wt / "live" / "events" / "cache" / "page.txt").write_text("<html>official page</html>")
    (wt / "live" / "events" / "events.json").write_text("{}")
    BK.run(gd, wt)
    files = subprocess.run(["git", "--git-dir", str(remote), "ls-tree", "-r", "--name-only", "main"],
                           capture_output=True, text=True, check=True).stdout.split()
    assert "live/events/events.json" in files and not [f for f in files if "/cache/" in f]
