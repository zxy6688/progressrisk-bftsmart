# Results Status v1.4 (Controlled Simulation, Not Yet Submission Results)

## Nominal configuration

- 198 validators, 9 equal committees, 22 validators per committee, `f = 7`.
- Global malicious fraction: 0.24, below the global PBFT one-third bound.
- 72 logical batches per shard per epoch; 24 epochs; 24 independent seeds.
- Hierarchical regime grid for `(primary withholding, backup withholding)`:
  `(0.55, 0.45)`, `(0.70, 0.60)`, `(0.90, 0.75)`.
- Finite action set: every lower-risk partner and `k in {1,...,6}`.

## Nominal policy result

Fraction of epochs containing at least one true over-threshold shard:

| Policy | Mean | Mean moved validators / epoch |
|---|---:|---:|
| No reconfiguration | 0.875 | 0.00 |
| Periodic global reshuffle | 0.854 | 49.50 |
| Random local exchange | 0.856 | 6.98 |
| Risk-triggered random partner | 0.455 | 3.33 |
| Proposed risk-aware exchange | 0.250 | 2.42 |

Paired bootstrap over 24 seeds: compared with no reconfiguration, the proposed controller reduces the failure-epoch fraction by 0.625 (95% bootstrap interval [0.467, 0.766]). Compared with risk-triggered random-partner exchange, the reduction is 0.205 ([0.106, 0.313]).

These are controlled-simulator results only. They must not be advertised as real deployment throughput or universal Byzantine detection results.

## Observation validation

1. **Discriminability.** Under the declared attack model, `P(N)` falls while `P(R)` and `P(S)` rise with active blocking load. Above the PBFT threshold, stall probability increases smoothly rather than by construction jumping to one.
2. **Context negative control.** Across 20 repeated trials, benign localized network degradation produces a mean posterior threshold risk of 0.027 when the visible degraded context is supplied; the same traces yield 1.0 when context is deliberately ignored. Active withholding under normal context yields mean risk 0.875.
3. **Calibration.** Nominal matched-model ECE is 0.019 on 1,258 shard-epoch observations. This is promising but still simulator-calibrated, not external calibration.
4. **Held-out attack intensity.** Under an unseen weaker attack strategy, the hierarchical regime posterior reduces failure epochs from 0.667 (no reconfiguration) to 0.146 in a 6-seed preliminary run; the point-likelihood ablation only reaches 0.507. This needs a larger robustness run before paper inclusion.

## Stress boundary

At global malicious fraction 0.32, local random exchange no longer improves failure epochs in the current budget. This is an expected capacity boundary, not a negative result to conceal: a controller cannot repair an insufficient global honest majority by rearranging too few validators.

## What remains before a submission claim

1. Increase all reportable robustness experiments to predeclared seed counts.
2. Add a workload/RTT trace-based context sweep rather than only synthetic context categories.
3. Implement a BFT-SMaRt membership-handoff microbenchmark for state transfer and interruption cost.
4. Add a sharding emulator experiment for throughput/latency impact, treating it as systems validation rather than ground-truth inference validation.
