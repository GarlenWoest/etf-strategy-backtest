"""USD/JPY specialist: point-in-time data alignment and the signals of the pre-registered hypotheses.

Calendar: days with a DEXJPUS noon rate (H.10). Everything is aligned to what was knowable on each such day:
  spot   DEXJPUS (yen per USD), observable at noon New York on its date
  US     DGS1, DGS2, DGS10, DTB3 (H.15): usable from the 2nd FX trading day after their date
  Japan  JGB 1Y/2Y/10Y (MoF, posted after the Tokyo close): usable from the next FX trading day
  VIX    VIXCLS close: usable from the next FX trading day
Decisions are weekly, on the last FX trading day of each week, and executed by src.fx_engine at the next FX
trading day's noon rate (lag 1). Rates for financing: US = DTB3, Japan = JGB 1Y (proxy for the short rate; free daily
Japanese money-market data were not available), both in annual decimals.
Single-pair caveat: the strongest carry and momentum evidence is cross-sectional across many currencies
(Burnside, Eichenbaum & Rebelo 2008: diversification raises carry Sharpe by over 50%); single-pair results should be
expected to be weaker.
"""
import numpy as np
import pandas as pd

from src import PROJECT_ROOT

RAW = PROJECT_ROOT / "data" / "raw" / "usdjpy"


def _csv(name):
    return pd.read_csv(RAW / ("%s.csv" % name), index_col=0, parse_dates=True)


def lag_to(series, cal, n):
    """Value usable on each calendar day: the latest observation dated at least n calendar-days-in-`cal` earlier."""
    s = series.dropna()
    pos = cal.searchsorted(s.index, side="left") + n          # first cal day at or after the obs date, plus n days
    ok = pos < len(cal)
    avail = pd.Series(s.to_numpy()[ok], index=cal[pos[ok]])
    avail = avail[~avail.index.duplicated(keep="last")]
    return avail.reindex(cal).ffill()


def load(end="2023-12-29"):
    fx = _csv("fred_DEXJPUS")["DEXJPUS"].dropna().loc[:end]
    cal = fx.index
    us = {k: lag_to(_csv("fred_" + k)[k], cal, 2) / 100.0 for k in ("DGS1", "DGS2", "DGS10", "DTB3")}
    jgb = _csv("mof_jgb_yields")
    jp = {k: lag_to(jgb[k], cal, 1) / 100.0 for k in ("1Y", "2Y", "10Y")}
    vix = lag_to(_csv("fred_VIXCLS")["VIXCLS"], cal, 1)
    return pd.DataFrame({"spot": fx, "us1": us["DGS1"], "us2": us["DGS2"], "us10": us["DGS10"], "tbill": us["DTB3"],
                         "jp1": jp["1Y"], "jp2": jp["2Y"], "jp10": jp["10Y"], "vix": vix}, index=cal)


def weekly_flags(cal):
    wk = cal.to_period("W-SUN")
    return pd.Series(np.r_[wk[1:] != wk[:-1], True], index=cal)


def on_weekly(sig, cal):
    """Keep signal values only on weekly decision days (NaN elsewhere = keep the previous decision)."""
    s = sig.reindex(cal).astype(float)
    s[~weekly_flags(cal).to_numpy()] = np.nan
    return s


# ---------------------------------------------------------------- hypothesis signals (+1 long USD/JPY, -1 short, 0 flat)

def carry_level(d, maturity, threshold_pp=1.0):
    """H1: long when the US-Japan yield differential >= threshold, short when <= -threshold, else flat."""
    diff = (d["us%d" % maturity] - d["jp%d" % maturity]) * 100
    sig = pd.Series(0.0, index=d.index)
    sig[diff >= threshold_pp] = 1.0
    sig[diff <= -threshold_pp] = -1.0
    sig[diff.isna()] = 0.0
    return on_weekly(sig, d.index)


def diff_momentum(d, lookback):
    """H2: sign of the change in the 2-year US-Japan differential over `lookback` FX trading days."""
    diff = d["us2"] - d["jp2"]
    ch = diff - diff.shift(lookback)
    sig = np.sign(ch).fillna(0.0)
    return on_weekly(sig, d.index)


def risk_off(d, kind, window=252, pct=0.80, vol_days=21):
    """True when the risk measure is above its trailing `pct` quantile (window ends on the decision day)."""
    if kind == "vix":
        x = d["vix"]
    elif kind == "vol":
        x = np.log(d["spot"]).diff().rolling(vol_days, min_periods=vol_days).std() * np.sqrt(252)
    else:
        raise ValueError(kind)
    q = x.rolling(window, min_periods=window).quantile(pct)
    return (x > q) & q.notna()


def carry_riskoff(d, kind):
    """H3: H1 (2-year, 1.0 pp) but flat while risk-off."""
    base = carry_level(d, 2).reindex(d.index)
    ro = risk_off(d, kind)
    sig = base.where(~ro, 0.0)
    sig[~weekly_flags(d.index).to_numpy()] = np.nan
    return sig


def relative_slope_change(d, lookback):
    """H4: relative slope RS = (US10-US2) - (JGB10-JGB2). Chen & Tsang (2013): a relatively steeper US curve is
    followed by USD depreciation, so a rise in RS over `lookback` days -> short USD/JPY, a fall -> long."""
    rs = (d["us10"] - d["us2"]) - (d["jp10"] - d["jp2"])
    ch = rs - rs.shift(lookback)
    sig = (-np.sign(ch)).fillna(0.0)
    return on_weekly(sig, d.index)


def always_long(d):
    return on_weekly(pd.Series(1.0, index=d.index), d.index)


# ---------------------------------------------------------------- the frozen trial list (fx1, V135-V142)

def build_trials(d):
    """Registry order = trial IDs. Returns a list of (test_id, hypothesis, params, weekly target Series)."""
    t = [("V135", "UJ-H1 carry level", "maturity=1Y;threshold=1.0pp", carry_level(d, 1)),
         ("V136", "UJ-H1 carry level", "maturity=2Y;threshold=1.0pp", carry_level(d, 2)),
         ("V137", "UJ-H2 differential momentum", "lookback=63d;2Y", diff_momentum(d, 63)),
         ("V138", "UJ-H2 differential momentum", "lookback=126d;2Y", diff_momentum(d, 126)),
         ("V139", "UJ-H3 carry with risk-off filter", "filter=VIX>p80(252d);2Y;1.0pp", carry_riskoff(d, "vix")),
         ("V140", "UJ-H3 carry with risk-off filter", "filter=USDJPY_vol21>p80(252d);2Y;1.0pp", carry_riskoff(d, "vol")),
         ("V141", "UJ-H4 relative curve slope", "lookback=63d;RS=(US10-US2)-(JGB10-JGB2)", relative_slope_change(d, 63)),
         ("V142", "UJ-H4 relative curve slope", "lookback=126d;RS=(US10-US2)-(JGB10-JGB2)", relative_slope_change(d, 126))]
    return t
