# Results Status v1.6: Exact Epoch-Reset Posterior

## What changed from v1.5

The v1.5 static particle filter could lose low-probability threshold states after repeated resampling. Its expanded calibration revealed overconfidence in the low-risk bin. Version 1.6 replaces that estimator with an exact, globally constrained posterior for each epoch.

The v1.6 main threat model is deliberately narrower and internally consistent:

- Byzantine identities and their active withholding behavior persist during the evaluation window.
- The controller receives a configuration-time network-wide active-load budget `L`; it never receives validator identities.
- Each epoch is inferred from fresh N/R/S observations. A membership exchange does not carry a stale latent-count posterior into the next epoch.
- Intermittent activation is not claimed; it needs a hidden-state transition model.

## Main controlled-simulation configuration

- 198 validators; 9 committees; 22 validators per committee; `f=7`.
- Global persistent active fraction 0.24, i.e., `L=48`.
- 72 logical batches per shard per epoch; 24 epochs; 24 independent seeds.
- Likelihood attack-regime grid: `(0.55,0.45)`, `(0.70,0.60)`, `(0.90,0.75)` for primary and backup withholding.
- Finite action set: each lower-risk partner and `k in {1,...,6}`.

## Main policy result

| Policy | Mean failure-epoch fraction | Mean moved validators/epoch | Mean controller time/epoch |
|---|---:|---:|---:|
| No reconfiguration | 0.875 | 0.00 | 3.55 ms |
| Periodic global reshuffle | 0.826 | 49.50 | 0.93 ms |
| Random local exchange | 0.868 | 7.08 | 0.91 ms |
| Risk-triggered random partner | 0.429 | 8.04 | 57.09 ms |
| Proposed risk-aware exchange | **0.184** | **5.76** | **56.33 ms** |

The paired bootstrap reduction of the proposed policy relative to no reconfiguration is 0.691 with 95% interval [0.568, 0.792]. These values are controlled-simulator results only.

## Signal checks included in the paper draft

- **Calibration:** 12 no-reconfiguration seeds; ECE 0.003 under the matched simulator.
- **Context negative control:** across 80 trials, benign degraded traces yield essentially zero risk when the visible degraded context is supplied, but risk 1.0 when that context is intentionally omitted. Active withholding under normal context yields mean risk 0.694.

## Not yet a submission claim

- No real BFT membership-handoff measurement.
- No external trace validation.
- Held-out attack-intensity and threat-budget-misspecification results require larger, predeclared replications before they enter the paper.
- The draft is a 5-page technical manuscript, not yet a complete INFOCOM submission.
