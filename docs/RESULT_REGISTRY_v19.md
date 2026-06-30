# Result registry v1.9

This registry extends the frozen v1.8 result set. It does **not** replace the v1.8 held-out policy test, and it does not add any unexecuted BFT-SMaRt number to the paper.

| Evidence | Source | Seeds | Result | Role |
|---|---|---:|---|---|
| Held-out policy test | `results_v18/heldout_policy_aggregate.csv` | 24 paired unseen | no reconfiguration 0.792 vs ProgressRisk 0.203; absolute reduction 0.589, bootstrap 95% CI [0.432, 0.731] | Main claim |
| Held-out intensity mismatch | `results_v18/attack_mismatch_aggregate.csv` | 12 paired | hierarchical mixture: 0.833 to 0.299; point-likelihood ablation: 0.413 | Robustness |
| Scale | `results_v18/scale_aggregate.csv` | 12 per scale | reduces true over-threshold shard-epoch rate at 5, 9 and 18 shards | Robustness |
| Active-load capacity | `results_v17/sensitivity_aggregate.csv` | 12 paired | current `k<=6` controller has no benefit at persistent active fraction 0.32 | Boundary |
| Observation exposure | `results_v19/exposure_aggregate.csv` and `exposure_paired_bootstrap.csv` | 12 paired unseen | at 24/72/216 logical batches per epoch: 0.833 to 0.490/0.385/0.333; paired reductions 0.344/0.448/0.500 | Signal robustness |
| BFT-SMaRt handoff | `production/run_bftsmart_handoff_benchmark.sh` | not yet run | automated 4->5->4 harness with no-op controls and state-size sweep | Submission gate, no result yet |

## Exposure experiment discipline

- The controller is frozen at `k_max=3`; no parameter was selected from this suite.
- The simulator uses the held-out primary/backup withholding pair `(0.65, 0.60)` and the previously declared three-regime likelihood mixture.
- Only the number of real logical PBFT batches available per epoch changes.
- This measures evidence exposure, not application throughput.

## Excluded from paper-facing claims

- Any BFT-SMaRt metrics before a completed run with raw logs, state sizes, no-op control, runner metadata, and at least 20 independent trials per state size.
- Results from old static particle posterior implementations.
- Unpaired parameter sweeps.
