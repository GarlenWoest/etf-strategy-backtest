"""Drop every row dated on or after the holdout start from user-supplied CSVs.

Usage: .venv/bin/python tools/truncate_holdout.py data/raw/crosscheck_stooq

For each *.csv directly in the folder:
  1. read it as text, find the date column (header 'Date' or 'Data'), parse dates;
  2. write a copy with only rows dated before dates.holdout_start into <folder>/pre2024/;
  3. re-read the copy and verify: same header, every date < cutoff, row count matches;
  4. only then delete the original.
If anything is unexpected (no date column, unparseable date) it stops before
deleting anything for that file. Output names the file, the kept row count and
the kept date range only; nothing from the holdout period is printed.
"""
import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import load_config  # noqa: E402

DATE_HEADERS = ("date", "data")


def parse(s):
    s = s.strip()
    if len(s) == 8 and s.isdigit():                      # 20231229
        return date(int(s[:4]), int(s[4:6]), int(s[6:]))
    return date.fromisoformat(s[:10])                     # 2023-12-29


def main(folder):
    cutoff = date.fromisoformat(load_config()["dates"]["holdout_start"])
    folder = Path(folder)
    out = folder / "pre2024"
    out.mkdir(exist_ok=True)
    files = sorted(p for p in folder.glob("*.csv") if p.is_file())
    if not files:
        print("no CSV files in %s" % folder)
        return 1
    for src in files:
        with open(src, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh))
        header, body = rows[0], [r for r in rows[1:] if r]
        cols = [i for i, h in enumerate(header) if h.strip().lower() in DATE_HEADERS]
        if len(cols) != 1:
            print("STOP %s: cannot identify one date column in header; nothing deleted" % src.name)
            return 2
        c = cols[0]
        try:
            keep = [r for r in body if parse(r[c]) < cutoff]
        except ValueError:
            print("STOP %s: unparseable date; nothing deleted" % src.name)
            return 2
        dst = out / src.name
        with open(dst, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(keep)
        with open(dst, newline="", encoding="utf-8") as fh:
            check = list(csv.reader(fh))
        ok = check[0] == header and len(check) - 1 == len(keep) and \
            all(parse(r[c]) < cutoff for r in check[1:] if r)
        if not ok:
            print("STOP %s: verification of truncated copy failed; original kept" % src.name)
            return 3
        src.unlink()
        first = keep[0][c] if keep else "-"
        last = keep[-1][c] if keep else "-"
        print("%s: kept %d rows (%s to %s); original deleted" % (src.name, len(keep), first, last))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "data/raw/crosscheck_stooq"))
