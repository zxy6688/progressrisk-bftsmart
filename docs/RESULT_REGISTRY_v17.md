# v1.7 Result Registry

## Source of truth

The main 24-seed table is copied only from:

- `/mnt/data/infocom_v16_nominal_24/nominal_policy_aggregate.csv`
- `/mnt/data/infocom_v16_nominal_24/nominal_paired_bootstrap.csv`

The calibration and context controls are copied only from:

- `/mnt/data/infocom_v16_calibration_12/calibration_curve.csv`
- `/mnt/data/infocom_v16_context_80/context_aggregate.csv`

The v1.7 sensitivity result is generated using v1.6 exact inference, 12 paired seeds (`0..11`), and is stored in:

- `results_v17/sensitivity_by_seed.csv`
- `results_v17/sensitivity_aggregate.csv`

## Completed robustness result

| True persistent active fraction | No reconfiguration | Risk-aware exchange | Mean moved validators/epoch |
|---:|---:|---:|---:|
| 0.20 | 0.250 | 0.014 | 3.19 |
| 0.24 | 0.750 | 0.215 | 5.88 |
| 0.28 | 1.000 | 0.549 | 9.12 |
| 0.32 | 1.000 | 1.000 | 4.84 |

Interpretation: within this controlled model and the fixed action budget \(k\leq 6\), the controller improves failure frequency from 0.20 through 0.28. At 0.32, it no longer improves failure frequency; this is reported as an intervention-capacity boundary, not hidden as a negative result.

## Results explicitly excluded from the paper

- The early v1.4/v1.5 release CSVs, which use a different particle estimator.
- Unpaired budget and threat-budget sweeps generated before the v1.7 paired-seed audit.
- Any BFT-SMaRt handoff number until the official BFT-SMaRt implementation is actually downloaded, built, and run.
