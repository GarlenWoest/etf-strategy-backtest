"""DTB3 replacement (owner approval 2026-11-02): 3-month Treasury bill secondary-market rate, daily, from the
Federal Reserve Board's own H.15 Data Download Program package (series RIFSGFSM03_N.B; FRED's DTB3 mirrors it).

Same method as tools/download_board_h10.py: the package is parsed in memory; observations dated 2024-01-01 or
later are counted and skipped unread; "ND" (no data) observations are blanked; the package is not kept.
Writes data/raw/board_h15/ (git-ignored) and appends to research/DATA_REGISTER.csv (FRED DTB3 marked SUPERSEDED).
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
URL = "https://www.federalreserve.gov/datadownload/Output.aspx?rel=H15&filetype=zip"
UA = {"User-Agent": "Mozilla/5.0 (trading-research data download; read-only research use)"}
CUT = "2024-01-01"
SID, NAME = "RIFSGFSM03_N.B", "board_h15_tbill_3m_secondary"
REGISTER = ROOT / "research" / "DATA_REGISTER.csv"


def sha(b):
    return hashlib.sha256(b).hexdigest()


raw = urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=180).read()
t = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
z = zipfile.ZipFile(io.BytesIO(raw))
if "H15_data.xml" not in z.namelist():
    sys.exit("unexpected package contents: %s" % z.namelist())
obs, dropped, inside = [], 0, False
for ev, el in ET.iterparse(io.BytesIO(z.read("H15_data.xml")), events=("start", "end")):
    tag = el.tag.split("}")[-1]
    if ev == "start" and tag == "Series":
        inside = el.attrib.get("SERIES_NAME") == SID
    elif ev == "end" and tag == "Obs" and inside:
        d = el.attrib.get("TIME_PERIOD", "")
        if d >= CUT:
            dropped += 1                               # holdout: counted, value never read
        else:
            st = el.attrib.get("OBS_STATUS", "")
            v = el.attrib.get("OBS_VALUE")
            obs.append((d, "" if (st == "ND" or v in (None, "NC", "ND")) else v, st))
    elif ev == "end" and tag == "Series":
        inside = False
    if ev == "end" and tag in ("Obs", "Series"):
        el.clear()
if not obs:
    sys.exit("series not found: %s" % SID)
obs.sort()
d = ROOT / "data" / "raw" / "board_h15"
if d.exists() and any(d.iterdir()):
    sys.exit("refusing to overwrite non-empty %s" % d)
d.mkdir(parents=True, exist_ok=True)
p = d / ("%s.csv" % NAME)
with open(p, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["date", "value", "obs_status"])
    w.writerows(obs)
s = sha(p.read_bytes())
meta = {"downloaded_at_utc": t, "url": URL, "package_sha256": sha(raw), "package_bytes": len(raw), "package_kept": False,
        "member": "H15_data.xml", "series": {SID: {"file": p.name, "description": "3-month Treasury bill, secondary market, discount basis, percent per year, daily",
        "rows": len(obs), "first": obs[0][0], "last": obs[-1][0], "holdout_rows_skipped_unread": dropped,
        "nd_rows_blanked": sum(1 for o in obs if o[2] == "ND"), "stored_sha256": s}}}
(d / "download_meta.json").write_text(json.dumps(meta, indent=1) + "\n")

reg = list(csv.DictReader(open(REGISTER)))
if not any(r["dataset_id"] == "fred_DTB3" for r in reg):
    m = json.loads((ROOT / "data/raw/usdjpy/download_meta.json").read_text())
    x = m["series"]["fred_DTB3"]
    reg.append({"dataset_id": "fred_DTB3", "approval": "USD/JPY study 2026-10-23", "source": "FRB H.15 via FRED", "url": "fredgraph.csv?id=DTB3",
                "licence": "FRED 'Public Domain: Citation Requested'; FRED Full Terms storage clause (R12 item 7)", "licence_evidence": "research/R12_VERIFICATION_2026-11-02.md",
                "retrieved_utc": m.get("downloaded_at_utc", ""), "stored_file": "data/raw/usdjpy/fred_DTB3.csv", "stored_sha256": x.get("sha256", ""),
                "original_sha256": "", "original_bytes": "", "rows": x.get("rows", ""), "first": x.get("first", ""), "last": x.get("last", ""),
                "holdout_rows_dropped": m.get("holdout_rows_dropped", {}).get("fred_DTB3", ""), "notes": "registered retroactively; used by Study 4 (results unchanged)",
                "status": "SUPERSEDED for new studies 2026-11-02 by %s: kept on disk, not to be used" % NAME})
reg.append({"dataset_id": NAME, "approval": "owner 2026-11-02 (DTB3 via Board H.15)", "source": "Board of Governors of the Federal Reserve System, H.15, Data Download Program (series %s)" % SID,
            "url": URL, "licence": "Federal Reserve Board publication (primary publisher); no licence text found on Board pages read 2026-11-02 [U]",
            "licence_evidence": "https://www.federalreserve.gov/data/data-download-fred-information.htm (read 2026-11-02)", "retrieved_utc": t,
            "stored_file": "data/raw/board_h15/%s.csv" % NAME, "stored_sha256": s, "original_sha256": sha(raw), "original_bytes": len(raw),
            "rows": len(obs), "first": obs[0][0], "last": obs[-1][0], "holdout_rows_dropped": dropped,
            "notes": "full H.15 package parsed in memory; 2024+ observations skipped unread; ND placeholders blanked; package not kept", "status": "ACTIVE (Study 5 source)"})
with open(REGISTER, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(reg[0].keys()))
    w.writeheader()
    w.writerows(reg)
print(SID, len(obs), obs[0][0], obs[-1][0], "holdout skipped", dropped, "ND blanked", meta["series"][SID]["nd_rows_blanked"])
