"""D-FRED (owner approval 2026-11-02): H.10 noon buying rates from the Federal Reserve Board's own Data
Download Program, replacing the FRED copies for Study 5.

Series: RXI$US_N.B.UK (US dollars per pound, daily) and RXI_N.B.JA (yen per US dollar, daily).
Holdout rule: the DDP H.10 package holds the full history. It is parsed in memory; observations dated
2024-01-01 or later are counted and skipped without reading their values; the package itself is not
kept (its SHA-256 and size are recorded). No returns or statistics are computed.
Writes data/raw/board_h10/ (git-ignored) and updates research/DATA_REGISTER.csv (new rows; the FRED copies
are marked SUPERSEDED, kept on disk, not to be used).
"""
import csv
import hashlib
import io
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.federalreserve.gov/datadownload/Output.aspx?rel=H10&filetype=zip"
UA = {"User-Agent": "Mozilla/5.0 (trading-research data download; read-only research use)"}
CUT = "2024-01-01"
SERIES = {"RXI$US_N.B.UK": ("board_h10_usd_per_gbp", "USD per GBP, H.10 noon buying rate NY, daily"),
          "RXI_N.B.JA": ("board_h10_jpy_per_usd", "JPY per USD, H.10 noon buying rate NY, daily")}
REGISTER = ROOT / "research" / "DATA_REGISTER.csv"


def sha(b):
    return hashlib.sha256(b).hexdigest()


raw = urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=180).read()
t = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
z = zipfile.ZipFile(io.BytesIO(raw))
if "H10_data.xml" not in z.namelist():
    sys.exit("unexpected package contents: %s" % z.namelist())
out = {k: [] for k in SERIES}
dropped = {k: 0 for k in SERIES}
current = None
for ev, el in ET.iterparse(io.BytesIO(z.read("H10_data.xml")), events=("start", "end")):
    tag = el.tag.split("}")[-1]
    if ev == "start" and tag == "Series":
        current = el.attrib.get("SERIES_NAME") if el.attrib.get("SERIES_NAME") in SERIES else None
    elif ev == "end" and tag == "Obs" and current:
        d = el.attrib.get("TIME_PERIOD", "")
        if d >= CUT:
            dropped[current] += 1                      # holdout: counted, value never read
        else:
            out[current].append((d, el.attrib.get("OBS_VALUE"), el.attrib.get("OBS_STATUS", "")))
    elif ev == "end" and tag == "Series":
        current = None
    if ev == "end" and tag in ("Obs", "Series"):
        el.clear()
d = ROOT / "data" / "raw" / "board_h10"
if d.exists() and any(d.iterdir()):
    sys.exit("refusing to overwrite non-empty %s" % d)
d.mkdir(parents=True, exist_ok=True)
meta = {"downloaded_at_utc": t, "url": URL, "package_sha256": sha(raw), "package_bytes": len(raw), "package_kept": False,
        "member": "H10_data.xml", "series": {}}
rows = []
for sid, (name, desc) in SERIES.items():
    obs = sorted(out[sid])
    if not obs:
        sys.exit("series not found: %s" % sid)
    p = d / ("%s.csv" % name)
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "value", "obs_status"])
        for o in obs:
            w.writerow([o[0], "" if (o[2] == "ND" or o[1] in (None, "NC", "ND")) else o[1], o[2]])   # ND = no data (holiday); its OBS_VALUE is a negative placeholder
    s = sha(p.read_bytes())
    meta["series"][sid] = {"file": p.name, "description": desc, "rows": len(obs), "first": obs[0][0], "last": obs[-1][0],
                           "holdout_rows_skipped_unread": dropped[sid], "stored_sha256": s}
    rows.append({"dataset_id": name, "approval": "D-FRED 2026-11-02", "source": "Board of Governors of the Federal Reserve System, H.10, Data Download Program (series %s)" % sid,
                 "url": URL, "licence": "Federal Reserve Board publication (primary publisher); no licence text on the H.10 or DDP pages read 2026-11-02 [U]",
                 "licence_evidence": "https://www.federalreserve.gov/releases/h10/ ; https://www.federalreserve.gov/data/data-download-fred-information.htm (read 2026-11-02)",
                 "retrieved_utc": t, "stored_file": "data/raw/board_h10/%s" % p.name, "stored_sha256": s, "original_sha256": sha(raw),
                 "original_bytes": len(raw), "rows": len(obs), "first": obs[0][0], "last": obs[-1][0], "holdout_rows_dropped": dropped[sid],
                 "notes": "full H.10 package parsed in memory; 2024+ observations skipped unread; package not kept", "status": "ACTIVE (Study 5 source)"})
(d / "download_meta.json").write_text(json.dumps(meta, indent=1) + "\n")

# register: add status column; mark FRED copies superseded; add the FRED DEXJPUS copy as superseded
old = list(csv.DictReader(open(REGISTER)))
for r in old:
    r.setdefault("status", "")
    if r["dataset_id"] == "fred_DEXUSUK":
        r["status"] = "SUPERSEDED 2026-11-02 by board_h10_usd_per_gbp (D-FRED): kept on disk, not to be used"
    elif not r["status"]:
        r["status"] = "ACTIVE"
if not any(r["dataset_id"] == "fred_DEXJPUS" for r in old):
    m = json.loads((ROOT / "data/raw/usdjpy/download_meta.json").read_text())
    s = m["series"]["fred_DEXJPUS"]
    old.append({"dataset_id": "fred_DEXJPUS", "approval": "USD/JPY study 2026-10-23", "source": "FRB H.10 via FRED", "url": "fredgraph.csv?id=DEXJPUS",
                "licence": "FRED 'Public Domain: Citation Requested' tag; FRED Full Terms storage clause (see R12 item 7)", "licence_evidence": "research/R12_VERIFICATION_2026-11-02.md",
                "retrieved_utc": m.get("downloaded_at_utc", ""), "stored_file": "data/raw/usdjpy/fred_DEXJPUS.csv", "stored_sha256": s.get("sha256", ""),
                "original_sha256": "", "original_bytes": "", "rows": s.get("rows", ""), "first": s.get("first", ""), "last": s.get("last", ""),
                "holdout_rows_dropped": m.get("holdout_rows_dropped", {}).get("fred_DEXJPUS", ""),
                "notes": "registered retroactively; used by Study 4 (results unchanged)",
                "status": "SUPERSEDED for new studies 2026-11-02 by board_h10_jpy_per_usd (D-FRED): kept on disk, not to be used"})
fields = list(old[0].keys()) if "status" in old[0] else list(old[0].keys()) + ["status"]
with open(REGISTER, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=fields)
    w.writeheader()
    w.writerows(old + rows)
for sid, v in meta["series"].items():
    print(sid, v["rows"], v["first"], v["last"], "holdout skipped", v["holdout_rows_skipped_unread"])
