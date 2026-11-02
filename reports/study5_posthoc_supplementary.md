# Study 5: POST-HOC SUPPLEMENTARY (not pre-registered; cannot change the V143/V144 verdicts)

_Computed 2026-11-02 after the frozen Study 5 run (`reports/study5_kill_table.md`), with `tools/study5_posthoc.py`. That script imports the Study 5 runner's functions unchanged. Validation 2015–2023, delay 1, 1× costs. **Spot-only: excludes carry.**_

**Question:** does volatility targeting reduce risk beyond what a lower average exposure does on its own?

**Benchmark:** a constant weight equal to the scaled overlay's average absolute weight w̄, with the same sign, cash, costs and simulator.

| | V143 GBP/USD | | | V144 USD/JPY | | |
|---|---|---|---|---|---|---|
| w̄ (scaled weight range) | 0.948 (0.44–1.00) | | | 0.934 (0.58–1.00) | | |
| | scaled | constant w̄ | unscaled | scaled | constant w̄ | unscaled |
| Realized vol | 9.08% | 9.26% | 9.76% | 8.17% | 8.50% | 9.09% |
| Max drawdown | −19.44% | **−18.81%** | −19.76% | −30.00% | −29.98% | −31.81% |
| Worst month | −5.47% | −5.56% | −5.86% | −8.30% | **−7.70%** | −8.22% |
| Bootstrap 5th / 95th pct, vol(constant) − vol(scaled) | 0.01 / 0.36 pp | | | 0.15 / 0.52 pp | | |
| Bootstrap 5th / 95th pct, vol(unscaled) − vol(constant) | 0.47 / 0.55 pp | | | 0.56 / 0.63 pp | | |
| Share of scaled-vs-unscaled reduction explained by lower exposure: vol / maxDD / worst month | 74% / 292% / 77% | | | 65% / 101% / scaled worse than both | | |

**Reading (post-hoc):**
- **Volatility:** about two-thirds to three-quarters of the reduction comes from simply holding less on average. The remainder (0.18 pp GBP, 0.33 pp JPY) has a bootstrap 5th percentile above 0 in both pairs, but only barely for GBP.
- **Drawdown and worst month:** the constant lower exposure did **as well or better** than volatility targeting. Volatility targeting added no tail-risk reduction beyond the lower average exposure in 2015–2023.
- This does not change the V143/V144 FAIL verdicts.
