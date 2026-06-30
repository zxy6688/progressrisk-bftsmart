# First-Author Paper Outline (Working v1)

## Provisional title

**Sensing PBFT Progress Without Identifying Validators: Risk-Aware Random Reconfiguration for Sharded BFT Systems**

Do not finalize the title until E1-E4 pass.

## Abstract structure

1. Random sharding protects in expectation but local committee risk can concentrate.
2. Existing approaches often assume node identification, rely on post-failure recovery, or randomize without using current shard conditions.
3. We introduce PBFT progress outcomes N/R/S as protocol-grounded shard observations.
4. Under a declared active-withholding attack model and context-calibrated likelihood, we infer active quorum-blocking risk without identifying validators.
5. A finite risk-aware random exchange controller chooses a=(h,c,k) under a migration budget.
6. Controlled simulation evaluates signal calibration, local threshold-failure reduction, overhead, and robustness.

## 1 Introduction

- Randomized committee assignment remains an important baseline.
- Average/global adversarial fraction does not eliminate local tail risk.
- Gap: how to sense operationally risky shards without pretending to identify each Byzantine node.
- Contributions stated only after experiments validate them.

## 2 Background and Related Work

- PBFT progress and view recovery.
- Randomized sharding / corrupted-shard tolerance.
- BFT performance degradation and malicious-primary handling.
- Reconfiguration / membership change systems.

## 3 Problem and Threat Model

- Epoch, equal-size shard committees, n=3f+1.
- Fixed hidden Byzantine identities in simulator; epoch-level active blocking behavior.
- Observable network/load context.
- Goal: reduce probability/frequency of local active-quorum threshold failure under a migration budget.

## 4 PBFT Progress Observation Model

- Batch tracking and N/R/S definitions.
- Why event-chain aggregation avoids duplicate evidence.
- Simulator-calibrated likelihood.
- Particle Bayesian posterior and risk output.

## 5 Budgeted Risk-Aware Random Exchange

- Finite action a=(h,c,k).
- Posterior propagation through hypergeometric exchange.
- One action per epoch; no action if expected gain fails threshold.
- Complexity and runtime bound.

## 6 Evaluation

- E1-E5 from EXPERIMENT_PLAN.md.
- Baselines, metrics, ablations, negative controls.

## 7 Discussion and Limitations

- Active blocking vs all latent Byzantine nodes.
- Context misspecification.
- Attack adaptation.
- Real membership handoff costs.

## 8 Conclusion
