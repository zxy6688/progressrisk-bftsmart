# Experiment Plan and Acceptance Criteria

## E1: Observation discriminability

**Question.** Does the protocol-generated outcome vector change systematically with active blocking load?

**Sweep.** Fix n=3f+1, context, and attack strategy. Sweep active load a from 0 to n.

**Primary plot.** P(N), P(R), P(S) versus a.

**Expected qualitative pattern.**
- As a rises but remains <= f, R should rise because malicious primaries can trigger view recovery.
- Once a > f and blockers withhold required messages, S should sharply increase because fewer than 2f+1 timely participants remain.

**Fail gate.** If N/R/S barely changes across active load, stop: the observation is not informative under the proposed attack semantics.

## E2: Context confounding

**Question.** Does the model avoid calling visible network degradation malicious concentration?

**Conditions.**
1. Normal context + no attack.
2. Normal context + active withholding.
3. Localized degraded context + no attack.

**Metric.** Brier score and posterior risk ranking when context is supplied to the likelihood. Compare to an ablation that ignores context.

**Fail gate.** If condition 3 produces the same posterior as condition 2 even after conditioning on context, do not use the signal for validator exchange.

## E3: Posterior quality

**Question.** Does posterior risk identify shards actually above the active threshold?

**Metrics.** Top-1 hit rate, Brier score, calibration curve, AUROC (extension).

**Ground truth.** Simulator-only active load A[s,t] and indicator A[s,t] > f.

## E4: Reconfiguration benefit

**Policies.**
- No reconfiguration.
- Periodic global random reshuffling.
- Budget-matched random local exchange.
- Risk-aware exchange a=(h,c,k).

**Primary metric.** Fraction of epochs with at least one true over-threshold shard.

**Secondary metrics.** Max true active load, mean stalled rate, migration volume, controller runtime, and risk calibration.

**Claim discipline.** Random exchange may lower the hot shard's expected active load; it does not get an unconditional tail-risk guarantee. The empirical comparison must establish any system-level claim.

## E5: Robustness grid

Vary: malicious fraction, activation probability, primary-withholding probability, benign timeout rate, committee size, number of shards, batch volume, and migration budget.

## Production validation, only after E1-E4 pass

Use a BFT implementation or sharding emulator to measure committee membership handoff, state/checkpoint transfer, and service interruption. This is a validation layer, not a substitute for simulator ground truth.
