"""v0.5 candidate check (owner request 2026-11-02): US Treasury daily bill rates vs the Board H.15 3-month T-bill
(series RIFSGFSM03_N.B, the series FRED mirrors as DTB3). Data quality only: no returns, no rule evaluation.
Downloads 2015-2023 only (pre-2024) from home.treasury.gov into data/raw/treasury_bills/ (git-ignored), registers each
file (SHA-256) in research/DATA_REGISTER.csv, and prints the comparison on shared dates."""
import csv
import hashlib
import io
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path(__import__("subprocess").run(["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                         capture_output=True, text=True).stdout.strip()).parent
URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/%d/all"
       "?type=daily_treasury_bill_rates&field_tdr_date_value=%d&page&_format=csv")
UA = {"User-Agent": "Mozilla/5.0 (trading-research data check; read-only research use)"}
YEARS = range(2015, 2024)


def main():
    out_dir = MAIN / "data" / "raw" / "treasury_bills"
    out_dir.mkdir(parents=True, exist_ok=True)
    frames, reg_rows = [], []
    for y in YEARS:
        p = out_dir / ("daily_treasury_bill_rates_%d.csv" % y)
        if not p.exists():
            raw = urllib.request.urlopen(urllib.request.Request(URL % (y, y), headers=UA), timeout=90).read()
            p.write_bytes(raw)
            reg_rows.append({"dataset_id": "treasury_bill_rates_%d" % y, "approval": "owner 2026-11-02 (v0.5 candidate check)",
                             "source": "U.S. Department of the Treasury, Daily Treasury Bill Rates", "url": URL % (y, y),
                             "licence": "U.S. government work (Treasury website) [U: terms page not read]", "licence_evidence": "",
                             "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                             "stored_file": str(p.relative_to(MAIN)), "stored_sha256": hashlib.sha256(raw).hexdigest(),
                             "original_sha256": hashlib.sha256(raw).hexdigest(), "original_bytes": len(raw), "rows": "", "first": "", "last": "",
                             "holdout_rows_dropped": 0, "notes": "requested by calendar year 2015-2023 only (no 2024+ transfer)", "status": "ACTIVE (comparison only)"})
        d = pd.read_csv(p)
        d["Date"] = pd.to_datetime(d["Date"], format="%m/%d/%Y")
        assert (d["Date"] < "2024-01-01").all()
        frames.append(d)
        if reg_rows and reg_rows[-1]["stored_file"].endswith("%d.csv" % y):
            reg_rows[-1].update(rows=len(d), first=str(d["Date"].min().date()), last=str(d["Date"].max().date()))
    if reg_rows:
        R = MAIN / "research" / "DATA_REGISTER.csv"
        old = list(csv.DictReader(open(R)))
        with open(R, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(old[0].keys()))
            w.writeheader(); w.writerows(old + reg_rows)
    t = pd.concat(frames).set_index("Date").sort_index()
    b = pd.read_csv(MAIN / "data" / "raw" / "board_h15" / "board_h15_tbill_3m_secondary.csv", parse_dates=["date"]).set_index("date")["value"].dropna()
    b = b.loc["2015-01-01":"2023-12-31"]
    res = {}
    for col in ("13 WEEKS BANK DISCOUNT", "13 WEEKS COUPON EQUIVALENT"):
        s = pd.to_numeric(t[col], errors="coerce").dropna()
        c = s.index.intersection(b.index)
        dd = (s.loc[c] - b.loc[c])
        res[col] = {"shared_dates": int(len(c)), "identical_to_0.005pp": int((dd.abs() < 0.005).sum()),
                    "mean_diff_pp": round(float(dd.mean()), 4), "mean_abs_diff_pp": round(float(dd.abs().mean()), 4),
                    "p95_abs_diff_pp": round(float(dd.abs().quantile(0.95)), 4), "max_abs_diff_pp": round(float(dd.abs().max()), 4),
                    "treasury_only_dates": int(len(s.index.difference(b.index))), "board_only_dates": int(len(b.index.difference(s.index)))}
    print(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    main()
