"""Study 3: monthly simulation timing, costs, signals."""
import numpy as np
import pandas as pd

from src import longhist as LH

IDX = pd.date_range("1990-01-31", periods=6, freq="ME")


def test_weights_earn_next_month_and_costs_charged():
    r = pd.DataFrame({"stocks": [0.0, 0.10, 0.0, 0, 0, 0], "bonds": 0.0, "commodities": 0.0, "gold": np.nan}, index=IDX)
    rf = pd.Series(0.0, index=IDX)
    w = pd.DataFrame(0.0, index=IDX, columns=r.columns)
    w.loc[IDX[0], "stocks"] = 1.0                                   # decided at end of Jan, held in Feb only
    out, turn, cost = LH.simulate(r, rf, w)
    c = LH.one_way_cost("stocks", 1990)
    assert abs(out.iloc[1] - ((1.10) * (1 - c) - 1)) < 1e-12      # Feb return net of the buy cost
    assert abs(turn.iloc[1] - 1.0) < 1e-12                         # sold everything at end of Feb
    assert np.isnan(out.iloc[0])


def test_cost_table_eras():
    assert LH.one_way_cost("stocks", 1950) == 0.0034 and LH.one_way_cost("stocks", 1995) == 0.0011
    assert LH.one_way_cost("bonds", 2010) == 0.0007 and LH.one_way_cost("commodities", 1992) == 0.0058


def test_s3_uses_only_past_months():
    r = pd.DataFrame({"stocks": [0.01, -0.02, 0.03, 0.01, -0.05, 0.02], "bonds": 0.0, "commodities": 0.0, "gold": np.nan}, index=IDX)
    w = LH.s3_weights(r, "stocks", 3)
    r2 = r.copy(); r2.iloc[5, 0] = 0.9                             # change only the last month
    assert w.iloc[:5].equals(LH.s3_weights(r2, "stocks", 3).iloc[:5])
    px = (1 + r["stocks"]).cumprod()
    assert w["stocks"].iloc[3] == float(px.iloc[3] / px.iloc[0] - 1 > 0)


def test_bond_return_at_constant_yield_is_coupon():
    y = pd.Series(5.0, index=IDX)
    assert np.allclose(LH.bond_returns(y, 10.0).to_numpy(), 0.05 / 12, atol=2e-4)
