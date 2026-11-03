# Statistics policy v1.2: DRAFT (not frozen)

_Draft 2026-11-02, from the second outside review. **v1.1 (frozen 2026-11-02, sha256 `67c710df…`) stays in force** until you approve and freeze v1.2. v1.2 applies only to studies registered after its freeze; no past verdict is re-opened. The research pause (research memory, 2026-11-02) also stays in force: no study is registered under any policy until the measured-cost study reports._

## Changes from v1.1

| | v1.1 (frozen) | v1.2 (draft) |
|---|---|---|
| Standard error of the primary t | Not specified. Study 6's protocol chose the plain (i.i.d.) t to decide, with Newey–West lag 3 reported | **HAC required** whenever the test series can be serially dependent or built from overlapping windows: Newey–West (Bartlett kernel), lag = ⌊4·(n/100)^(2/9)⌋ (Newey & West 1994 rule), fixed by this rule, never chosen after results. The plain t is reported alongside. A protocol may use a longer lag only if it states why before results |
| Power at registration | L1 (research review): power ≥ 0.5 at the stated plausible effect | **Two levels** (below) |
| Everything else | t > 3 primary at full cumulative N; Romano–Wolf and DSR reported only; within-family DSR variance; P6; P7 with written amendment | Unchanged |

## 1. HAC standard errors (primary t)

**Rule:** the primary t uses the HAC standard error above whenever any of the following holds:
- returns are overlapping (e.g. multi-day holding periods sampled daily);
- positions persist across observations;
- the series is a per-period statistic built from adjacent windows.

**Why now:** Study 6 (V146) decided on the plain t, as its frozen protocol specified. Recomputed on 2026-11-02 as a diagnostic (same data, pre-2024; **verdict unchanged**: it is the frozen protocol's rule that counts, and every version is below 3 anyway):

| Series | n | Plain t (decided) | NW lag 3 (reported) | HAC, rule lag |
|---|---|---|---|---|
| US primary | 401 | 1.841 | 1.862 | 1.849 (lag 5) |
| US 2009–2023 (secondary i) | 179 | 0.486 | 0.552 | 0.566 (lag 4) |
| Developed ex US (secondary ii) | 401 | 3.045 | 3.225 | 3.328 (lag 5) |

The HAC t is not always smaller. With positive autocorrelation it is smaller; here it is slightly larger. The rule exists so that the choice is never made after seeing which is larger.

## 2. Two power levels

| Level | Registration requirement | Label | What a pass can mean |
|---|---|---|---|
| **SCREENING** | Power ≥ 0.5 under the primary test at the stated plausible effect, with ≥ 30 independent outcomes | Every result labelled "SCREENING" | A candidate for a confirmatory study. **A screening pass is never sufficient for real money**, alone or with other screening passes |
| **CONFIRMATORY** | Power ≥ **0.8** under the primary test at a **pre-specified, economically meaningful effect**: one that would still matter net of measured costs at the intended account size, stated with its reasoning before registration | "CONFIRMATORY" | Eligible for real-money gate 1 (historical pass at full cumulative N under the frozen policy) |

- **Assignment:** the protocol states the level before any data is touched.
- **No upgrades:** a study cannot be upgraded from screening to confirmatory after results.
- **Counting:** both levels count in cumulative N.

## Open questions before freezing

1. Should a CONFIRMATORY study also require a window not used by any screening study of the same family (see `research/PRIOR_EXPOSURE.md`)? Proposed: yes.
2. Should "economically meaningful" have a floor (e.g. net annual Sharpe ≥ 0.3 after measured costs)? Proposed: decide after the measured-cost study reports.
