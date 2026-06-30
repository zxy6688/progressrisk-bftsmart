# Results Status v1.7

## Paper-facing, fully auditable results

| Evidence | Configuration | Source |
|---|---|---|
| Main policy comparison | Exact epoch-reset posterior, 24 paired seeds | `../infocom_v16_nominal_24/` and copied values in `paper/main.tex` |
| Paired bootstrap | Proposed vs no reconfiguration, 24 common seeds | `../infocom_v16_nominal_24/nominal_paired_bootstrap.csv` |
| Calibration | Matched controlled simulator, 12 no-reconfiguration seeds, ECE 0.00319 | `../infocom_v16_calibration_12/calibration_curve.csv` |
| Context negative control | 80 trials | `../infocom_v16_context_80/context_aggregate.csv` |
| Active-fraction sensitivity | 12 paired seeds for each fraction | `results_v17/sensitivity_*.csv` |

## What v1.7 adds

- A frozen source-of-truth registry for paper numbers.
- Corrected references for SpiralShard and Levee.
- An explicit result that the current controller with `k <= 6` fails at persistent active fraction 0.32.
- A BFT-SMaRt membership-handoff microbenchmark protocol and build skeleton, intentionally marked unexecuted.

## Excluded evidence

- v1.4/v1.5 particle-filter outputs.
- Any early unpaired budget or threat-budget sensitivity output.
- Any production reconfiguration latency number, because BFT-SMaRt has not been downloaded and executed in this environment.

## Next empirical gate

Run the protocol in `production/BFTSMART_HANDOFF_PROTOCOL.md` on the official BFT-SMaRt source. The official project supports reconfiguration but requires `currentView` propagation to replicas and clients; that propagation must be timed as part of the handoff cost.
