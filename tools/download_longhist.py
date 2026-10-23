"""Study 3 data: long-history monthly series from free official sources (no logins), validated like Phase 2.

Sources (downloaded to data/raw/longhist/_orig/<source>/ by curl; this script parses them):
  Ken French data library   F-F_Research_Data_Factors_CSV.zip  -> US stock market total return (Mkt-RF + RF), 1-month T-bill (RF)
  AQR datasets              Commodities for the Long Run (index level, monthly) -> equal-weight commodity futures excess return
                            Time Series Momentum factors (monthly) and Century of Factor Premia -> reference only, not traded
  Shiller (Yale)            ie_data.xls -> cross-checks only (bond returns, CPI, S&P); its pre-1953 long rate is linearly
                            interpolated between annual values, which would leak future yields into monthly bond returns
  World Bank Pink Sheet     CMO-Historical-Data-Monthly.xlsx -> gold, $/oz, MONTHLY AVERAGE (user decision 2026-10-23;
                            FRED deleted its LBMA gold series on 2022-01-31)
  FRED (fredgraph.csv)      LTGOVTBD (long-term Treasury yield, 1925-2000), GS10 (10-year, 1953+), TB3MS, CPIAUCNS

Holdout rule: every file is truncated to dates before dates.holdout_start immediately after parsing; only the truncated
series are written (data/raw/longhist/<name>.csv) and the original downloads are then deleted (their SHA-256, size and
download time are kept in data/raw/longhist/download_meta.json). No value on or after 2024-01-01 is printed or stored.

Usage: .venv/bin/python -I tools/download_longhist.py
"""
import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src import PROJECT_ROOT, load_config
from src import data as D

cfg = load_config()
assert cfg["dates"]["holdout_locked"]
CUT = pd.Timestamp(cfg["dates"]["holdout_start"])
RAW = PROJECT_ROOT / "data" / "raw" / "longhist"
ORIG = RAW / "_orig"
FRED_IDS = {"LTGOVTBD": "Long-term US government securities yield (>10y), monthly avg, 1925-2000",
            "GS10": "10-year Treasury constant maturity yield, monthly avg, 1953+",
            "TB3MS": "3-month T-bill secondary market rate, monthly avg, 1934+",
            "CPIAUCNS": "CPI-U, not seasonally adjusted, 1913+"}
SOURCES = {"kf": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip",
           "shiller": "http://www.econ.yale.edu/~shiller/data/ie_data.xls",
           "aqr_cflr": "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Commodities-for-the-Long-Run-Index-Level-Data-Monthly.xlsx",
           "aqr_tsmom": "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Time-Series-Momentum-Factors-Monthly.xlsx",
           "aqr_cfp": "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Century-of-Factor-Premia-Monthly.xlsx",
           "worldbank": "https://thedocs.worldbank.org/en/doc/5d903e848db1d1b83e0ec8f744e55570-0350012021/related/CMO-Historical-Data-Monthly.xlsx"}


def me(idx):
    """Normalize any date-like index to calendar month-end timestamps."""
    return pd.DatetimeIndex(idx).to_period("M").to_timestamp("M")


def cut(s, name, meta):
    n = int((s.index >= CUT).sum())
    meta["holdout_rows_dropped"][name] = n
    return s[s.index < CUT]


# ---------------------------------------------------------------- parsers (return monthly Series, month-end index)

def parse_kf(path):
    z = zipfile.ZipFile(path)
    lines = z.read(z.namelist()[0]).decode("latin1").splitlines()
    i0 = next(i for i, l in enumerate(lines) if l.startswith(",Mkt-RF"))
    rows = []
    for l in lines[i0 + 1:]:
        p = [x.strip() for x in l.split(",")]
        if len(p) < 5 or not p[0].isdigit() or len(p[0]) != 6:
            break                                            # end of the monthly block (annual block follows)
        rows.append((p[0], float(p[1]), float(p[4])))
    df = pd.DataFrame(rows, columns=["ym", "mkt_rf", "rf"])
    df.index = me(pd.to_datetime(df["ym"], format="%Y%m"))
    return (df["mkt_rf"] + df["rf"]) / 100.0, df["rf"] / 100.0


def parse_aqr(path, header_row, col_name):
    d = pd.read_excel(path, sheet_name=0, header=None)
    hdr = list(d.iloc[header_row])
    j = hdr.index(col_name)
    body = d.iloc[header_row + 1:, [0, j]].dropna(subset=[0])
    s = pd.Series(pd.to_numeric(body[j], errors="coerce").to_numpy(), index=me(pd.to_datetime(body[0])))
    return s.dropna()


def parse_worldbank_gold(path):
    d = pd.read_excel(path, sheet_name="Monthly Prices", header=None)
    hdr = list(d.iloc[4])
    j = hdr.index("Gold")
    assert "oz" in str(d.iloc[5, j]).lower(), d.iloc[5, j]
    body = d.iloc[6:, [0, j]].dropna(subset=[0])
    body = body[body[0].astype(str).str.match(r"^\d{4}M\d{2}$")]
    idx = me(pd.to_datetime(body[0].str.replace("M", "-"), format="%Y-%m"))
    return pd.Series(pd.to_numeric(body[j], errors="coerce").to_numpy(), index=idx).dropna()


def parse_shiller(path):
    import xlrd
    s = xlrd.open_workbook(str(path)).sheet_by_name("Data")
    assert s.row_values(7)[17] == "Returns" and "Bond" in s.row_values(6)[17] and s.row_values(7)[4] == "CPI"
    rows = []
    for i in range(8, s.nrows):
        r = s.row_values(i)
        if not isinstance(r[0], float):
            break
        y = int(r[0])
        m = int(round((r[0] - y) * 100))
        rows.append((y, m, r[1], r[2], r[4], r[6], r[17]))
    df = pd.DataFrame(rows, columns=["y", "m", "P", "D", "CPI", "GS10", "bond_gross"])
    df.index = me(pd.to_datetime(dict(year=df.y, month=df.m, day=1)))
    df = df.drop(columns=["y", "m"]).apply(pd.to_numeric, errors="coerce")
    return df


def fred(sid):
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s&coed=%s" % (sid, (CUT - pd.Timedelta(days=1)).date())
    df = pd.read_csv(url)
    if df.shape[1] != 2:
        raise RuntimeError("FRED format changed for %s: %s" % (sid, list(df.columns)))
    s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").to_numpy(), index=me(pd.to_datetime(df.iloc[:, 0])))
    if s.notna().sum() == 0:
        raise RuntimeError("FRED download empty: %s" % sid)
    return s.dropna()


# ---------------------------------------------------------------- bond total return from yields

def bond_price(coupon, yld, years):
    """Price per $1 face of a semiannual-coupon bond with `years` to maturity (fractional periods allowed)."""
    n = 2.0 * years
    h = yld / 2.0
    return coupon / 2.0 * (1 - (1 + h) ** (-n)) / h + (1 + h) ** (-n)


def bond_returns(yield_pct, maturity):
    """Monthly total return of buying a par bond at last month's yield and repricing it one month later at this
    month's yield, with one month of coupon accrued. Yields in percent (monthly averages)."""
    y = yield_pct / 100.0
    y0 = y.shift(1)
    r = bond_price(y0, y, maturity - 1.0 / 12) - 1 + y0 / 12
    return r.dropna()


# ---------------------------------------------------------------- validation (monthly analogue of validate_prices)

def validate_monthly(s, name, kind, move_flag):
    """kind: 'return' (s = monthly returns) or 'level' (s = prices/yields). Never modifies data."""
    out = []

    def add(check, dates, detail=""):
        if len(dates):
            out.append({"series": name, "check": check, "count": int(len(dates)),
                        "dates": [str(d.date()) for d in dates][:40], "detail": detail})

    add("duplicate_month", s.index[s.index.duplicated()])
    full = pd.date_range(s.index.min(), s.index.max(), freq="ME")
    add("missing_month", full.difference(s.index))
    add("nan", s.index[s.isna()])
    if kind == "level":
        add("non_positive", s.index[s <= 0])
        mv = s.pct_change()
    else:
        add("return_below_-100%", s.index[s <= -1])
        mv = s
    add("big_move", mv.index[mv.abs() > move_flag], "flag only, kept (>%.0f%% in a month)" % (100 * move_flag))
    same = s.diff().eq(0)
    run = same.groupby((~same).cumsum()).cumsum()
    add("stale_run", s.index[run >= 2], "value unchanged 3+ months")
    return out


def main():
    meta = {"parsed_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "downloaded_at_utc": (ORIG / "downloaded_at.txt").read_text().strip(), "sources": SOURCES,
            "originals": {}, "holdout_rows_dropped": {}, "series": {}}
    for p in sorted(ORIG.rglob("*")):
        if p.is_file() and p.name != "downloaded_at.txt":
            meta["originals"][str(p.relative_to(ORIG))] = {"bytes": p.stat().st_size, "sha256": D.sha256(p)}
    kf_mkt, kf_rf = parse_kf(ORIG / "kf" / "F-F_Research_Data_Factors_CSV.zip")
    cflr = parse_aqr(ORIG / "aqr_cflr" / "cflr.xlsx", 10, "Excess return of equal-weight commodities portfolio")
    tsmom = parse_aqr(ORIG / "aqr_tsmom" / "tsmom.xlsx", 17, "TSMOM")
    tsmom_cm = parse_aqr(ORIG / "aqr_tsmom" / "tsmom.xlsx", 17, "TSMOM^CM")
    gold = parse_worldbank_gold(ORIG / "worldbank" / "cmo_monthly.xlsx")
    sh = parse_shiller(ORIG / "shiller" / "ie_data.xls")
    series = {"stocks_kf_total_return": kf_mkt, "tbill_kf_rf": kf_rf, "commodities_aqr_excess_return": cflr,
              "aqr_tsmom_factor_reference": tsmom, "aqr_tsmom_cm_factor_reference": tsmom_cm,
              "gold_worldbank_usd_oz_monthly_avg": gold, "shiller_bond_gross_return": sh["bond_gross"].dropna(),
              "shiller_cpi": sh["CPI"].dropna(), "shiller_sp_price": sh["P"].dropna(), "shiller_sp_dividend": sh["D"].dropna()}
    for sid in FRED_IDS:
        series["fred_" + sid] = fred(sid)
    meta["fred_downloaded_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for name, s in series.items():
        s = cut(s.sort_index(), name, meta)
        s.rename(name).to_csv(RAW / ("%s.csv" % name), index_label="month_end")
        series[name] = s
        meta["series"][name] = {"first": str(s.index[0].date()), "last": str(s.index[-1].date()), "rows": int(len(s)),
                                "sha256": D.sha256(RAW / ("%s.csv" % name))}
    # the AQR Century of Factor Premia file is reference material only; nothing from it is used
    for p in sorted(ORIG.rglob("*")):                       # originals contain post-2023 rows: delete after truncation
        if p.is_file():
            p.unlink()
    for p in sorted(ORIG.rglob("*"), reverse=True):
        p.rmdir()
    ORIG.rmdir()
    with open(RAW / "download_meta.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    return meta


if __name__ == "__main__":
    m = main()
    for k, v in m["series"].items():
        print("%-40s %s .. %s  %5d rows" % (k, v["first"], v["last"], v["rows"]))
    print("holdout rows dropped:", m["holdout_rows_dropped"])
