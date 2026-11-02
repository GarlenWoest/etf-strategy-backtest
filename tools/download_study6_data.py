"""Study 6 data (owner approval 2026-11-02, decision 5; after the STATS_POLICY v1.1 freeze). Pre-2024 only.

A. Ken French Data Library: Developed and Developed ex US 3 Factors [Daily]. The zip is parsed in memory; rows dated
   2024-01-01 or later are counted and discarded unread; the zip is not kept.
B. OECD SDMX, endPeriod cut server-side (asserted): short rates IR3TIB and IRSTCI (monthly) and CPI index
   (monthly and quarterly; AUS/NZL publish CPI quarterly) for the G10 areas.
C. Board H.10 (Data Download Program package): the other G10 noon buying rates (AUD, CAD, EUR, NZD, CHF, SEK, NOK,
   no DEM series in the current package, so EUR starts 1999). Parsed in memory; 2024+ observations skipped unread; package not kept.

Writes data/raw/study6/ (git-ignored) and appends rows to research/DATA_REGISTER.csv. Data only: no returns,
statistics or rule evaluation. Run with: .venv/bin/python -I tools/download_study6_data.py
"""
import csv
import hashlib
import io
import json
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path(subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                           capture_output=True, text=True).stdout.strip()).parent
UA = {"User-Agent": "Mozilla/5.0 (trading-research data download; read-only research use)"}
APPROVAL = "owner 2026-11-02 (decision 5, Study 6 downloads)"
OUT = MAIN / "data" / "raw" / "study6"
REGISTER = ROOT / "research" / "DATA_REGISTER.csv"
KF_LIC = ("Copyright Eugene F. Fama and Kenneth R. French; free download; no explicit licence or terms text on the "
          "library page [OV for redistribution]")
OECD_LIC = ("OECD Terms & Conditions, section 'Data' [V, read 2026-11-02]: extract, download, copy, adapt, distribute "
            "for any purpose with OECD citation; third-party restrictions possible")
BOARD_LIC = "Federal Reserve Board publication (primary publisher); no licence text on the H.10 or DDP pages read 2026-11-02 [U]"
AREAS = "USA+JPN+GBR+CAN+AUS+NZL+CHE+SWE+NOR+DEU+EA20"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def get(url, timeout=180):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ken_french(name, url):
    raw = get(url)
    t = now()
    z = zipfile.ZipFile(io.BytesIO(raw))
    (member,) = [m for m in z.namelist() if m.lower().endswith(".csv")]
    lines = z.read(member).decode("latin-1").splitlines()
    hdr = next(i for i, ln in enumerate(lines) if ln.replace(" ", "").startswith(",Mkt-RF"))
    cols = ["date"] + [c.strip() for c in lines[hdr].split(",")[1:]]
    rows, dropped = [], 0
    for ln in lines[hdr + 1:]:
        f = [x.strip() for x in ln.split(",")]
        if not f[0].isdigit() or len(f[0]) != 8:
            break                                           # end of the daily block (annual or notes follow)
        if f[0] >= "20240101":
            dropped += 1                                    # holdout: counted, values never parsed
            continue
        rows.append(["%s-%s-%s" % (f[0][:4], f[0][4:6], f[0][6:])] + ["%.6f" % (float(x) / 100) for x in f[1:]])
    p = OUT / ("%s.csv" % name)
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        w.writerows(rows)
    return {"dataset_id": name, "source": "Kenneth R. French Data Library (Tuck/Dartmouth), %s" % member, "url": url,
            "licence": KF_LIC, "licence_evidence": "data_library.html footer read 2026-11-02", "retrieved_utc": t,
            "stored_file": str(p.relative_to(MAIN)), "stored_sha256": sha(p.read_bytes()), "original_sha256": sha(raw),
            "original_bytes": len(raw), "rows": len(rows), "first": rows[0][0], "last": rows[-1][0],
            "holdout_rows_dropped": dropped,
            "notes": "zip parsed in memory; 2024+ rows counted and discarded unread; zip not kept; decimal daily returns (file % / 100)"}


def oecd(name, flow, key, end, start=None):
    url = "https://sdmx.oecd.org/public/rest/data/%s/%s?endPeriod=%s%s&format=csvfilewithlabels" % (
        flow, key, end, "&startPeriod=%s" % start if start else "")
    raw = get(url)
    t = now()
    rdr = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    periods = [r["TIME_PERIOD"] for r in rdr]
    if not periods:
        sys.exit("no rows: %s" % key)
    if any(p >= "2024" for p in periods):
        sys.exit("2024+ rows returned for %s: nothing written" % key)
    p = OUT / ("%s.csv" % name)
    p.write_bytes(raw)
    cover = {}
    for r in rdr:
        a = r["REF_AREA"]
        lo, hi = cover.get(a, (r["TIME_PERIOD"], r["TIME_PERIOD"]))
        cover[a] = (min(lo, r["TIME_PERIOD"]), max(hi, r["TIME_PERIOD"]))
    return {"dataset_id": name, "source": "OECD Data Explorer SDMX API, %s, key %s" % (flow, key), "url": url,
            "licence": OECD_LIC, "licence_evidence": "https://www.oecd.org/en/about/terms-conditions.html", "retrieved_utc": t,
            "stored_file": str(p.relative_to(MAIN)), "stored_sha256": sha(raw), "original_sha256": sha(raw),
            "original_bytes": len(raw), "rows": len(rdr), "first": min(periods), "last": max(periods), "holdout_rows_dropped": 0,
            "notes": "endPeriod=%s server-side (no 2024+ transfer); coverage %s" % (
                end, "; ".join("%s %s..%s" % (a, lo, hi) for a, (lo, hi) in sorted(cover.items())))}, cover


H10 = {"RXI$US_N.B.AL": ("board_h10_usd_per_aud", "USD per AUD"), "RXI_N.B.CA": ("board_h10_cad_per_usd", "CAD per USD"),
       "RXI$US_N.B.EU": ("board_h10_usd_per_eur", "USD per EUR"), "RXI$US_N.B.NZ": ("board_h10_usd_per_nzd", "USD per NZD"),
       "RXI_N.B.SZ": ("board_h10_chf_per_usd", "CHF per USD"), "RXI_N.B.SD": ("board_h10_sek_per_usd", "SEK per USD"),
       "RXI_N.B.NO": ("board_h10_nok_per_usd", "NOK per USD")}   # DEM: not in the current H.10 package (checked 2026-11-02)


def board_h10():
    url = "https://www.federalreserve.gov/datadownload/Output.aspx?rel=H10&filetype=zip"
    raw = get(url)
    t = now()
    z = zipfile.ZipFile(io.BytesIO(raw))
    out = {k: [] for k in H10}
    dropped = {k: 0 for k in H10}
    names, cur = set(), None
    for ev, el in ET.iterparse(io.BytesIO(z.read("H10_data.xml")), events=("start", "end")):
        tag = el.tag.split("}")[-1]
        if ev == "start" and tag == "Series":
            names.add(el.attrib.get("SERIES_NAME"))
            cur = el.attrib.get("SERIES_NAME") if el.attrib.get("SERIES_NAME") in H10 else None
        elif ev == "end" and tag == "Obs" and cur:
            d = el.attrib.get("TIME_PERIOD", "")
            if d >= "2024-01-01":
                dropped[cur] += 1                           # holdout: counted, value never read
            else:
                out[cur].append((d, el.attrib.get("OBS_VALUE"), el.attrib.get("OBS_STATUS", "")))
        elif ev == "end" and tag == "Series":
            cur = None
        if ev == "end" and tag in ("Obs", "Series"):
            el.clear()
    missing = [k for k in H10 if not out[k]]
    if missing:
        sys.exit("H.10 series not found: %s; daily series in package: %s" % (missing, sorted(n for n in names if n and ".B." in n)))
    regs = []
    for sid, (name, desc) in H10.items():
        obs = sorted(out[sid])
        p = OUT / ("%s.csv" % name)
        with open(p, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["date", "value", "obs_status"])
            for o in obs:
                w.writerow([o[0], "" if (o[2] == "ND" or o[1] in (None, "NC", "ND")) else o[1], o[2]])
        nd = sum(1 for o in obs if o[2] == "ND")
        regs.append({"dataset_id": name, "source": "Board of Governors of the Federal Reserve System, H.10, Data Download Program (series %s, %s, daily)" % (sid, desc),
                     "url": url, "licence": BOARD_LIC, "licence_evidence": "https://www.federalreserve.gov/releases/h10/ (read 2026-11-02)",
                     "retrieved_utc": t, "stored_file": str(p.relative_to(MAIN)), "stored_sha256": sha(p.read_bytes()),
                     "original_sha256": sha(raw), "original_bytes": len(raw), "rows": len(obs), "first": obs[0][0], "last": obs[-1][0],
                     "holdout_rows_dropped": dropped[sid],
                     "notes": "full H.10 package parsed in memory; 2024+ observations skipped unread; package not kept; ND placeholder values blanked (%d rows)" % nd})
    return regs


def main():
    if OUT.exists() and any(OUT.iterdir()):
        sys.exit("refusing to overwrite non-empty %s" % OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    regs, cover = board_h10(), {}                # first: fails fast if a series name is wrong
    kf = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    regs.append(ken_french("kf_developed_3f_daily", kf + "Developed_3_Factors_Daily_CSV.zip"))
    regs.append(ken_french("kf_developed_ex_us_3f_daily", kf + "Developed_ex_US_3_Factors_Daily_CSV.zip"))
    fin, prc = "OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0", "OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0"
    for name, flow, key, end in [("oecd_g10_M_IR3TIB", fin, "%s.M.IR3TIB.PA._Z._Z._Z._Z.N" % AREAS, "2023-12"),
                                 ("oecd_g10_M_IRSTCI", fin, "%s.M.IRSTCI.PA._Z._Z._Z._Z.N" % AREAS, "2023-12"),
                                 ("oecd_g10_M_CPI", prc, "%s.M.N.CPI.IX._T.N._Z" % AREAS, "2023-12"),
                                 ("oecd_g10_Q_CPI", prc, "%s.Q.N.CPI.IX._T.N._Z" % AREAS, "2023-Q4")]:
        r, c = oecd(name, flow, key, end)
        regs.append(r)
        cover[name] = c
    old = list(csv.DictReader(open(REGISTER)))
    fields = list(old[0].keys())
    for r in regs:
        r.update({"approval": APPROVAL, "status": "ACTIVE (Study 6 candidate data; no study registered yet)"})
    with open(REGISTER, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(old + regs)
    (OUT / "download_meta.json").write_text(json.dumps({"datasets": regs, "oecd_coverage": cover}, indent=1) + "\n")
    for r in regs:
        print(r["dataset_id"], r["rows"], r["first"], r["last"], "holdout dropped", r["holdout_rows_dropped"])
    for n, c in cover.items():
        print(n, " ".join("%s:%s" % (a, lo) for a, (lo, hi) in sorted(c.items())))


if __name__ == "__main__":
    main()
