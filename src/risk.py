"""Risk modes: AGGRESSIVE below the target, Phase 7B risk layer from the first close at or above it.

AGGRESSIVE: strategy target weights pass through unchanged (no stops, no caps,
no kill switch; 100% in one position allowed).

PHASE_7B (from the first close >= capital.target_usd, permanently, even if equity
later falls back below it):
  - max weight in any one instrument (risk.phase_7b.max_weight_any_instrument)
  - max weight in any single leveraged ETF (max_weight_single_leveraged_etf)
  - drawdown kill switch: once equity falls drawdown_kill_from_post_threshold_peak
    below the highest close reached after the switch, every target goes to cash
    and trading stops for good.
  Excess weight removed by a cap goes to cash (never re-allocated).

Not implemented yet: max loss per trade (2% of account). It needs a stop rule and is
designed in Phase 7B. Until then, apply_7b reports it as not enforced.
"""
AGGRESSIVE = "aggressive"
PHASE_7B = "phase_7b"


class RiskState(object):
    def __init__(self, cfg, leveraged, enabled=True):
        self.enabled = enabled
        self.target = float(cfg["capital"]["target_usd"])
        p = cfg["risk"]["phase_7b"]
        self.max_any = float(p["max_weight_any_instrument"])
        self.max_lev = float(p["max_weight_single_leveraged_etf"])
        self.kill_dd = float(p["drawdown_kill_from_post_threshold_peak"])
        self.leveraged = set(leveraged)
        self.mode = AGGRESSIVE
        self.switch_date = None
        self.switch_count = 0
        self.peak = None
        self.killed = False
        self.kill_date = None

    def on_close(self, date, equity):
        """Update the mode after the close of `date`. Takes effect for orders decided at this close."""
        if not self.enabled:
            return
        if self.mode == AGGRESSIVE and equity >= self.target:
            self.mode = PHASE_7B
            self.switch_date = date
            self.switch_count += 1
            self.peak = equity
        elif self.mode == PHASE_7B and not self.killed:
            self.peak = max(self.peak, equity)
            if equity <= self.peak * (1 - self.kill_dd):
                self.killed = True
                self.kill_date = date

    def apply(self, weights):
        """Transform strategy target weights {ticker: w} according to the current mode."""
        if self.mode == AGGRESSIVE:
            return dict(weights)
        if self.killed:
            return {t: 0.0 for t in weights}
        out = {}
        for t, w in weights.items():
            cap = min(self.max_any, self.max_lev) if t in self.leveraged else self.max_any
            out[t] = min(w, cap)
        return out
