"""Study 5 POST-HOC SUPPLEMENTARY (not pre-registered; cannot change the V143/V144 verdicts).

Owner request 2026-11-02 (research reset section 2), computed after the frozen Study 5 run, from its own functions
(tools/run_study5.py, imported unchanged): does volatility targeting reduce risk beyond what a lower average exposure
does on its own?

For T1 (GBP/USD) and T2 (USD/JPY), validation window, delay 1, 1x costs:
- w_bar = mean |weight| of the scaled overlay over the validation days on which a weight is applied.
- Constant benchmark = base sign x w_bar on every day (simulate() holds a weight as a fraction of equity; costs are
  charged only on weight changes, the same convention as the scaled overlay between its month-end decisions).
- Realized vol, max drawdown and worst calendar month for scaled, constant-w_bar and unscaled; R-1-style stationary
  bootstrap (5-day blocks, 10,000 resamples, seed 20261102) of vol(constant) - vol(scaled) and vol(unscaled) - vol(constant).
Spot-only: excludes carry. Writes results/study5_posthoc.json.
"""
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_study5", ROOT / "tools" / "run_study5.py")
S5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S5)


def one(px, tb, label):
    lr = np.log(px / px.shift(1)).loc[S5.IS0:S5.IS1].dropna()
    sign = 1.0 if lr.mean() > 0 else -1.0
    ws = S5.vol_target_weights(px, sign, S5.VA0, S5.VA1)
    wu = S5.vol_target_weights(px, sign, S5.VA0, S5.VA1, unscaled=True)
    st = max(ws.first_valid_index(), wu.first_valid_index())
    ws, wu = ws.loc[st:], wu.loc[st:]
    wbar = float(ws.iloc[:-1].abs().mean())                     # weights applied to returns (last day has no return)
    wc = pd.Series(sign * wbar, index=ws.index)
    p = px.loc[st:S5.VA1]
    out = {"label": label, "base_sign": sign, "w_bar": wbar, "w_scaled_min_max": [float(ws.abs().min()), float(ws.abs().max())]}
    series = {}
    for name, w in (("scaled", ws), ("constant_wbar", wc), ("unscaled", wu)):
        r, e, _ = S5.simulate(p, tb, w, 1.0)
        series[name] = r
        out[name] = {"vol": S5.ann_vol(r), "max_drawdown": S5.max_drawdown(e), "worst_month": S5.worst_month(r)}
    lo, hi = S5.boot_vol_diff(series["constant_wbar"], series["scaled"])
    out["boot_vol_constant_minus_scaled_p5_p95"] = [lo, hi]
    lo, hi = S5.boot_vol_diff(series["unscaled"], series["constant_wbar"])
    out["boot_vol_unscaled_minus_constant_p5_p95"] = [lo, hi]
    s, c, u = out["scaled"], out["constant_wbar"], out["unscaled"]
    out["share_of_reduction_from_lower_exposure"] = {
        k: (abs(u[k]) - abs(c[k])) / (abs(u[k]) - abs(s[k])) if abs(u[k]) != abs(s[k]) else None
        for k in ("vol", "max_drawdown", "worst_month")}
    return out


def main():
    gbp, jpy, tb, _ = S5.load()
    tbs = tb.dropna(subset=["value"]).set_index("date")["value"]
    res = {"label": "POST-HOC SUPPLEMENTARY (not pre-registered; cannot change the V143/V144 verdicts); excludes carry"}
    for df, lab in ((gbp, "V143 GBP/USD"), (jpy, "V144 USD/JPY")):
        px = df.dropna(subset=["value"]).set_index("date")["value"]
        res[lab] = one(px, tbs, lab)
    p = ROOT / "results" / "study5_posthoc.json"
    p.write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
