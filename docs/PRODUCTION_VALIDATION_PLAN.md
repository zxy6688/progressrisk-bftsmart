# Production Validation Plan (After Controller Results Stabilize)

## Why this is a second layer

The event-level simulator is necessary because it provides hidden active-load ground truth. It cannot measure membership handoff cost in a full BFT stack. The prototype layer therefore validates *cost and service interruption*, not the simulator's hidden-state inference claim.

## Microbenchmark: BFT-SMaRt

Use BFT-SMaRt for a small committee handoff experiment:

1. Run a deterministic key-value service with `n = 4` and then `n = 7` replicas.
2. Issue a steady stream of update requests.
3. Trigger one add/remove membership operation at an epoch boundary.
4. Measure request latency, temporary service interruption, state/checkpoint transfer size, and time to resume stable throughput.
5. Compare one-at-a-time membership change with batched `k-for-k` exchange emulated as ordered remove/add operations.

BFT-SMaRt is appropriate because its official library implements on-the-fly add/remove replica reconfiguration, while its README also makes clear that the current view configuration must be distributed consistently. This makes the configuration-transfer burden an explicit measured limitation rather than an ignored detail.

## Sharded systems validation: BlockEmulator

Use BlockEmulator / BlockEmulator-X only for system-level sharding metrics:

- throughput;
- confirmation latency;
- workload balance;
- migration interruption proxy.

Do not claim that its public account/state migration mechanism directly implements validator committee reconfiguration unless the code path is inspected and adapted. The controller should first be integrated as an epoch-level membership policy in a minimal branch, with all modifications documented.

## Acceptance criteria

The prototype layer is successful only if the controller's decision time plus reconfiguration time fits within the configured epoch maintenance window and does not erase the safety benefit through unacceptable service interruption.
