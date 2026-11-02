"""The frozen forward-test pre-registration must not change, and config must carry exactly its parameters."""
import hashlib

import yaml

from src import PROJECT_ROOT

CFG = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text())["live_usdjpy"]


def test_preregistration_file_is_unchanged():
    doc = PROJECT_ROOT / CFG["preregistration"]["document"]
    assert hashlib.sha256(doc.read_bytes()).hexdigest() == CFG["preregistration"]["sha256"]


def test_config_parameters_match_the_preregistration():
    f1, f2 = CFG["rules"]["F001"], CFG["rules"]["F002"]
    assert (f1["trigger_z"], f1["vol_window"], f1["invalidation_mult"], f1["target_mult"], f1["expiry_fx_days"]) == (-2.0, 60, 1.0, 0.5, 2)
    assert (f2["lookback_months"], f2["dead_band_log_return"], f2["stop_monthly_sd_mult"], f2["vol_window"]) == (12, 0.02, 3.0, 60)
    assert CFG["sizing"] == {"start_usd": 10000, "risk_per_trade": 0.005, "per_rule_max_x": 0.5, "max_gross_x": 1.0}
    assert CFG["costs"]["base"] == {"one_way": 0.00015, "financing_admin_fee_annual": 0.01}
    assert CFG["costs"]["stress"] == {"one_way": 0.0003, "financing_admin_fee_annual": 0.015}
    assert CFG["baselines"]["historical_sample_mean"]["sign"] == 1
    assert CFG["evaluation"]["min_resolved_for_claims"] == 30 and CFG["forward_n"] == 2
    doc = (PROJECT_ROOT / CFG["preregistration"]["document"]).read_text()
    for s in ("−2.0 × σ60", "0.5% of equity", "(1 − 1.0 × \\|r_t\\|)", "(1 + 0.5 × \\|r_t\\|)", "> +2%", "3 × σ60 × √21",
              "0.015%", "1.00%/yr", "seed 20261029", "+0.0094%"):
        assert s in doc, s


def test_historical_n_is_unchanged():
    full = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text())
    assert full["usdjpy_study1"]["cumulative_trials_for_dsr"] == 142


def test_v03_amendment_is_unchanged_and_sources_are_read_only():
    a = CFG["amendments"]["v0.3"]
    assert hashlib.sha256((PROJECT_ROOT / a["document"]).read_bytes()).hexdigest() == a["sha256"]
    assert CFG["sources"]["oanda"]["host"] == "https://api-fxpractice.oanda.com"
    assert CFG["sources"]["alpaca"]["host"] == "https://data.alpaca.markets"
    assert CFG["late_detection_minutes"] == 30 and CFG["f002_first_month_end"] == "2026-10-30"


def test_v04_amendment_is_unchanged_and_matches_the_config_thresholds():
    a = CFG["amendments"]["v0.4"]
    assert hashlib.sha256((PROJECT_ROOT / a["document"]).read_bytes()).hexdigest() == a["sha256"]
    sr = CFG["financing"]["series"]
    assert (sr["usd"]["id"], sr["usd"]["valid_max"], sr["usd"]["carry_max"], sr["usd"]["age_unit"]) == ("DTB3", 3, 5, "us_business_days")
    assert (sr["jpy"]["id"], sr["jpy"]["valid_max"], sr["jpy"]["carry_max"], sr["jpy"]["age_unit"]) == ("IRSTCI01JPM156N", 95, 125, "calendar_days")
    assert CFG["financing"]["policy"] == "v1"
    assert CFG["costs"]["base"]["financing_admin_fee_annual"] == 0.01 and CFG["costs"]["stress"]["financing_admin_fee_annual"] == 0.015
