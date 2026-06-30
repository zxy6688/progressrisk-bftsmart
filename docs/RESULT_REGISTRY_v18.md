# Result registry v1.8

All paper-facing numbers in v1.8 are listed here. Older particle-filter outputs and unpaired robustness sweeps are excluded.

| Evidence | Source | Seeds | Result used | Status |
|---|---|---:|---|---|
| Development budget selection | `/mnt/data/v17_budget_paired_chunk{0,1,2}/budget_by_seed.csv` | 12 paired | Select `k_max=3` as migration-efficiency knee | Development only; not main claim |
| Held-out policy test | `results_v18/heldout_policy_aggregate.csv` | 24 unseen paired | no reconfig 0.792 vs risk-aware 0.203; abs reduction 0.589, bootstrap CI [0.432, 0.731] | Main paper result |
| Attack-intensity mismatch | `results_v18/attack_mismatch_aggregate.csv` | 12 paired | regime mixture risk-aware 0.299 vs point-likelihood 0.413 vs no reconfig 0.833 | Robustness |
| Scale | `results_v18/scale_aggregate.csv` | 12 per scale | true over-threshold shard-epoch fraction decreases at K=5,9,18 | Robustness |
| Active-fraction capacity | `results_v17/sensitivity_aggregate.csv` | 12 paired per fraction | current k<=6 controller fails at 0.32 | Explicit boundary |
| Conservative threat-budget sensitivity | `results_v18/upper_bound_budget_aggregate.csv` | 12 paired | only L >= true load is valid for the constrained posterior | Limitation |
| Context negative control | `release_results` in original v1.7 source (not copied as paper-facing raw) | 80 trials | supplied degradation context removes false alarms; omitted context produces them | Observation validation |
| Calibration | original v1.6 exact-posterior calibration output | 12 seeds | ECE 0.003 under matched simulator | Internal only |

## Seed discipline

- Development seeds for the budget selection do not overlap the held-out main test seeds.
- Every comparison within a suite uses common random seeds.
- `k_max=3` was locked before the held-out 24-seed experiment.

## Excluded results

- All v1.4/v1.5 static-particle posterior experiments.
- Any early budget/prior output whose compared settings did not share the same seeds.
- Underestimated active-load budgets (`L < L_true`) as a robustness claim: they violate the support of the exact constrained posterior.
