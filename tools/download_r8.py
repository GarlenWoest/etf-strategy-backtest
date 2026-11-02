"""R8 downloads (owner approval 2026-11-02): FRED DEXUSUK and Ken French daily research factors.

Holdout rule: nothing dated 2024-01-01 or later is kept or read.
  - FRED: requested with coed=2023-12-31, so no 2024+ rows are transferred; asserted after parsing.
  - Ken French: the zip holds the full history; it is parsed in memory, rows dated >= 2024-01-01 are
    counted and discarded without being parsed into numbers, and the zip itself is not kept
    (its SHA-256 and size are recorded).
No returns or statistics are computed. Writes data/raw/r8_<name>/ (git-ignored), download_meta.json there,
and appends rows to research/DATA_REGISTER.csv.
"""
import csv
import hashlib
import io
import json
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CUT = "2024-01-01"
UA = {"User-Agent": "trading-research data download (read-only research use)"}
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXUSUK&cosd=1971-01-01&coed=2023-12-31"
KF_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip"
REGISTER = ROOT / "research" / "DATA_REGISTER.csv"
FIELDS = ["dataset_id", "approval", "source", "url", "licence", "licence_evidence", "retrieved_utc", "stored_file",
          "stored_sha256", "original_sha256", "original_bytes", "rows", "first", "last", "holdout_rows_dropped", "notes"]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
        return r.read(), now()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def new_dir(name):
    d = ROOT / "data" / "raw" / name
    if d.exists() and any(d.iterdir()):
        sys.exit("refusing to overwrite non-empty %s" % d)
    d.mkdir(parents=True, exist_ok=True)
    return d


rows = []

# ---------------------------------------------------------------- FRED DEXUSUK
raw, t = fetch(FRED_URL)
df = pd.read_csv(io.BytesIO(raw))
if df.shape[1] != 2:
    sys.exit("FRED format changed: %s" % list(df.columns))
df.columns = ["Date", "DEXUSUK"]
df["Date"] = pd.to_datetime(df["Date"])
assert (df["Date"] < CUT).all(), "FRED returned 2024+ rows"
df["DEXUSUK"] = pd.to_numeric(df["DEXUSUK"], errors="coerce")       # "." marks missing days
d = new_dir("r8_fred_dexusuk")
p = d / "fred_DEXUSUK.csv"
df.to_csv(p, index=False)
fred_meta = {"downloaded_at_utc": t, "url": FRED_URL, "original_sha256": sha(raw), "original_bytes": len(raw),
             "rows": len(df), "non_missing": int(df["DEXUSUK"].notna().sum()), "first": str(df["Date"].min().date()),
             "last": str(df["Date"].max().date()), "holdout_rows_dropped": 0, "stored_sha256": sha(p.read_bytes()),
             "description": "US dollars per pound sterling, Fed H.10 noon buying rate in New York, daily (FRB via FRED)"}
(d / "download_meta.json").write_text(json.dumps(fred_meta, indent=1) + "\n")
rows.append(dict(dataset_id="fred_DEXUSUK", approval="R8 2026-11-02", source="Board of Governors of the Federal Reserve System, H.10, via FRED (St. Louis Fed)",
                 url=FRED_URL, licence="UNVERIFIED [OV]: FRED series page did not load (timeout, 2026-11-02); H.10 is a Federal Reserve release; check FRED's DEXUSUK notes/copyright line before any publication",
                 licence_evidence="none read", retrieved_utc=t, stored_file="data/raw/r8_fred_dexusuk/fred_DEXUSUK.csv",
                 stored_sha256=fred_meta["stored_sha256"], original_sha256=fred_meta["original_sha256"], original_bytes=len(raw),
                 rows=fred_meta["rows"], first=fred_meta["first"], last=fred_meta["last"], holdout_rows_dropped=0,
                 notes="requested with coed=2023-12-31 (no 2024+ transfer); not yet validated (gaps, stale runs, H.10 calendar)"))

# ---------------------------------------------------------------- Ken French daily factors
raw, t = fetch(KF_URL)
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    names = z.namelist()
    if len(names) != 1 or not names[0].lower().endswith(".csv"):
        sys.exit("unexpected zip contents: %s" % names)
    text = z.read(names[0]).decode("latin-1")
keep, dropped, header = [], 0, None
for line in text.splitlines():
    cells = [c.strip() for c in line.split(",")]
    if header is None:
        if cells and cells[0] == "" and "Mkt-RF" in cells:
            header = ["date"] + cells[1:]
        continue
    if not cells[0].isdigit() or len(cells[0]) != 8:
        if keep or dropped:
            break                                      # end of the daily table (copyright footer)
        continue
    if cells[0] >= CUT.replace("-", ""):
        dropped += 1                                   # holdout row: counted, never parsed into numbers
        continue
    keep.append([cells[0]] + cells[1:])
if header is None or not keep:
    sys.exit("Ken French file format not recognised")
kf = pd.DataFrame(keep, columns=header)
kf["date"] = pd.to_datetime(kf["date"], format="%Y%m%d")
for c in header[1:]:
    kf[c] = pd.to_numeric(kf[c], errors="raise") / 100.0           # file is in percent
assert (kf["date"] < CUT).all()
d = new_dir("r8_kenfrench_daily")
p = d / "kf_factors_daily.csv"
kf.to_csv(p, index=False)
kf_meta = {"downloaded_at_utc": t, "url": KF_URL, "zip_member": names[0], "original_sha256": sha(raw), "original_bytes": len(raw),
           "original_kept": False, "rows": len(kf), "first": str(kf["date"].min().date()), "last": str(kf["date"].max().date()),
           "holdout_rows_dropped": dropped, "columns": header, "units": "decimal daily returns (file percent / 100)",
           "stored_sha256": sha(p.read_bytes()),
           "description": "Fama/French 3 research factors, daily: Mkt-RF, SMB, HML, RF (US market total return = Mkt-RF + RF)"}
(d / "download_meta.json").write_text(json.dumps(kf_meta, indent=1) + "\n")
rows.append(dict(dataset_id="kf_factors_daily", approval="R8 2026-11-02", source="Kenneth R. French Data Library (Tuck/Dartmouth), Fama/French 3 Factors [Daily]",
                 url=KF_URL, licence="Copyright Eugene F. Fama and Kenneth R. French; free download; no explicit licence or terms text on the library page [OV for redistribution]",
                 licence_evidence="data_library.html footer read 2026-11-02", retrieved_utc=t, stored_file="data/raw/r8_kenfrench_daily/kf_factors_daily.csv",
                 stored_sha256=kf_meta["stored_sha256"], original_sha256=kf_meta["original_sha256"], original_bytes=len(raw),
                 rows=kf_meta["rows"], first=kf_meta["first"], last=kf_meta["last"], holdout_rows_dropped=dropped,
                 notes="zip parsed in memory; 2024+ rows counted and discarded unread; original zip not kept"))

new = not REGISTER.exists()
with open(REGISTER, "a", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=FIELDS)
    if new:
        w.writeheader()
    w.writerows(rows)
for r in rows:
    print("%s: %s rows %s..%s, holdout rows dropped %s, stored sha256 %s" % (r["dataset_id"], r["rows"], r["first"], r["last"], r["holdout_rows_dropped"], r["stored_sha256"][:16]))
