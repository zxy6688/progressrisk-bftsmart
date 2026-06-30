# Result registry v1.10

The scientific main line remains frozen:

`PBFT logical batch progress -> {Normal, Recovered, Stalled} -> exact constrained Bayesian posterior -> one budgeted random exchange a=(h,c,k)`.

v1.10 does not introduce a new model, new observation variable, controller
parameter, simulator condition, or paper-facing deployment number. It repairs
one reproducibility artifact and confirms the frozen held-out result.

| Evidence | Source | Seeds | Result | Role |
|---|---|---:|---|---|
| Development-only budget selection | `results_v18/development_budget_aggregate.csv` | 12 paired | Lock `k_max=3` as migration-efficiency knee | Parameter selection only |
| Held-out policy result | `results_v110/heldout_by_seed.csv`, `heldout_aggregate.csv` | 24 paired, seed 120000--120023 | no reconfiguration 0.792 vs risk-aware 0.203; absolute reduction 0.589, paired 95% CI [0.432, 0.731] | Main claim, raw rows retained |
| Partner-selection separation | `results_v110/heldout_paired_bootstrap.csv` | same 24 paired seeds | risk-aware vs risk-triggered random partner: absolute reduction 0.203, 95% CI [0.123, 0.285] | Confirms partner selection effect |
| Held-out attack-intensity mismatch | `results_v18/attack_mismatch_aggregate.csv` | 12 paired | mixture 0.833 to 0.299; point likelihood 0.413 | Robustness |
| Scale | `results_v18/scale_aggregate.csv` | 12 per scale | reduces true over-threshold shard-epoch rate at 5, 9 and 18 shards | Robustness |
| Active-load capacity | `results_v17/sensitivity_aggregate.csv` | 12 paired | no benefit at active fraction 0.32 for `k<=6` | Explicit boundary |
| Observation exposure | `results_v19/exposure_aggregate.csv`, `exposure_paired_bootstrap.csv` | 12 paired | retained effect at 24, 72, and 216 batches/epoch | Signal robustness |
| BFT-SMaRt handoff | `production/run_bftsmart_handoff_benchmark.sh` | not run | automated 4->5->4 harness with no-op controls | Sole remaining empirical gate |

## Reproduction audit

On 2026-06-30, the complete 24-seed held-out suite was re-executed from the
frozen code. All primary policy means, standard deviations, risk metrics,
migration counts, and sample counts match `results_v18/heldout_policy_aggregate.csv`.
Only controller timing varies across hardware/runtime environments.
