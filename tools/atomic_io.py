"""Crash-safe file writes for the monitoring scripts (live/, paper/). Plain Python, standard library only.

write_text(): the new content goes to a temporary file in the same folder, is flushed and fsynced, then atomically
  renamed over the target (os.replace). A crash at any moment leaves either the old file or the new one, never a
  truncated mix. The folder is fsynced afterwards so the rename itself survives a power loss.
append_text(): appends and fsyncs. An append is NOT atomic: a crash mid-write can leave a partial last line, so
  callers either track committed sizes (paper books) or read with read_jsonl(), which skips an unparsable last line.
Temporary files are named ".<name>.<random>.tmp"; the private backup excludes them.
"""
import json
import os
import tempfile
from pathlib import Path

TMP_SUFFIX = ".tmp"


def _fsync_dir(d):
    try:
        fd = os.open(d, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def write_text(path, text, encoding="utf-8"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".", suffix=TMP_SUFFIX)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    _fsync_dir(path.parent)


def write_json(path, obj, indent=1, **kw):
    write_text(path, json.dumps(obj, indent=indent, **kw))


def append_text(path, text, encoding="utf-8"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding=encoding, newline="") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())


def repair_tail(path):
    """If a line-oriented file does not end with a newline (an append torn by a crash), cut the unfinished last line
    so the next append starts on a clean line. Returns the number of bytes removed (0 if nothing was torn)."""
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return 0
    data = path.read_bytes()
    if data.endswith(b"\n"):
        return 0
    keep = data.rfind(b"\n") + 1
    os.truncate(path, keep)
    return len(data) - keep


def read_jsonl(path):
    """Records of a JSONL file. An unparsable LAST line (a write interrupted by a crash) is skipped; an unparsable
    line anywhere else is a real corruption and raises ValueError."""
    path = Path(path)
    if not path.exists():
        return []
    lines = [l for l in path.read_text().splitlines() if l.strip()]
    out = []
    for i, line in enumerate(lines):
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            if i == len(lines) - 1:
                break
            raise ValueError("%s: unparsable line %d of %d" % (path, i + 1, len(lines)))
    return out
