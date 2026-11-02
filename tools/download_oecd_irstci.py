"""v0.5 candidate check (owner approval 2026-11-02): OECD SDMX JPN.M.IRSTCI (immediate rate, call money / interbank,
Japan, monthly), pre-2024 only (endPeriod=2023-12, cut server-side; asserted). Registers the file with SHA-256 in
research/DATA_REGISTER.csv. Data quality only: no returns, no rule evaluation."""
import csv
import hashlib
import io
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path(subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                           capture_output=True, text=True).stdout.strip()).parent
URL = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0/JPN.M.IRSTCI.PA._Z._Z._Z._Z.N"
       "?endPeriod=2023-12&format=csvfilewithlabels")
UA = {"User-Agent": "Mozilla/5.0 (trading-research data check; read-only research use)"}

d = MAIN / "data" / "raw" / "oecd_irstci"
if d.exists() and any(d.iterdir()):
    sys.exit("refusing to overwrite %s" % d)
raw = urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=120).read()
t = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
df = pd.read_csv(io.BytesIO(raw))
assert (df["TIME_PERIOD"].astype(str) < "2024-01").all(), "2024+ rows returned"
d.mkdir(parents=True, exist_ok=True)
p = d / "oecd_JPN_M_IRSTCI_to_2023-12.csv"
p.write_bytes(raw)
R = MAIN / "research" / "DATA_REGISTER.csv"
old = list(csv.DictReader(open(R)))
old.append({"dataset_id": "oecd_JPN_M_IRSTCI", "approval": "owner 2026-11-02 (v0.5 candidate check)",
            "source": "OECD Data Explorer SDMX API, OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0, key JPN.M.IRSTCI.PA._Z._Z._Z._Z.N", "url": URL,
            "licence": "see licence_evidence", "licence_evidence": "", "retrieved_utc": t, "stored_file": str(p.relative_to(MAIN)),
            "stored_sha256": hashlib.sha256(raw).hexdigest(), "original_sha256": hashlib.sha256(raw).hexdigest(), "original_bytes": len(raw),
            "rows": len(df), "first": str(df["TIME_PERIOD"].min()), "last": str(df["TIME_PERIOD"].max()), "holdout_rows_dropped": 0,
            "notes": "endPeriod=2023-12 server-side (no 2024+ transfer); comparison only", "status": "ACTIVE (comparison only)"})
with open(R, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(old[0].keys()))
    w.writeheader(); w.writerows(old)
print(len(df), df["TIME_PERIOD"].min(), df["TIME_PERIOD"].max(), hashlib.sha256(raw).hexdigest()[:16])
print(sorted(df.columns)[:30])
