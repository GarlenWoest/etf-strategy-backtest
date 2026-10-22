"""Phase 1 guards: the config encodes the user's rules and the frozen strategy list."""
import csv

from src import PROJECT_ROOT, load_config

cfg = load_config()


def test_holdout_is_locked():
    assert cfg["dates"]["holdout_locked"] is True
    assert cfg["dates"]["holdout_start"] == "2024-01-01"
    assert cfg["dates"]["validation_end"] < cfg["dates"]["holdout_start"]


def test_capital_and_threshold():
    assert cfg["capital"]["starting_usd"] == 100.0
    assert cfg["capital"]["target_usd"] == 1000.0
    assert cfg["capital"]["min_order_usd"] == 1.0


def test_costs():
    c = cfg["costs"]
    assert c["commission_usd"] == 0.0
    assert c["half_spread"] == {"unleveraged": 0.0002, "leveraged": 0.0005}
    assert c["slippage"] == 0.0005
    assert c["sensitivity_multipliers"] == [1, 2, 3]


def test_taxes_follow_user_decisions():
    t = cfg["taxes"]
    assert t["federal_ordinary_rate"] == 0.12
    assert t["ohio_rate"] == 0.0275
    assert t["section_1256_like_60_40"] == ["UGL"]


def test_tqqq_and_tmf_gross_expense_ratios():
    lev = cfg["instruments"]["leveraged"]
    assert lev["TQQQ"]["expense_ratio"] == 0.0094
    assert lev["TMF"]["expense_ratio"] == 0.0101   # confirmed from SEC 497K, gross


def _variant_count(s):
    n = 0
    n += len(s["S2_trend_ma"]["N_days"]) * len(s["S2_trend_ma"]["instruments"]) * 2
    n += len(s["S3_tsmom"]["lookback_months"]) * len(s["S3_tsmom"]["instruments"]) * 2
    n += len(s["S4_rsi2"]["entry_rsi_below"]) * len(s["S4_rsi2"]["instruments"]) * 2
    n += len(s["S5_rotation"]["lookback_months"])
    n += len(s["S6_leveraged_rotation"]["lookback_months"])
    n += len(s["P1_vol_gated_leverage"]["vol_threshold"]) * len(s["P1_vol_gated_leverage"]["pairs"])
    n += len(s["P2_multi_asset_trend"]["sma_months"]) * 2
    n += len(s["P3_rsi2_trend_filter"]["entry_rsi_below"]) * len(s["P3_rsi2_trend_filter"]["instruments"]) * 2
    return n


def test_frozen_list_matches_config_and_research_log():
    s = cfg["strategies"]
    assert s["frozen"] is True
    assert _variant_count(s) == s["total_trials"] == 92
    with open(PROJECT_ROOT / "research_log.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    registered = [r["test_id"] for r in rows if r["result"] == "PRE-REGISTERED"]
    assert registered == ["V%03d" % i for i in range(1, 93)]
    assert sum(r["result"] == "BENCHMARK" for r in rows) == 9
