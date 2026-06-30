# Method Specification v1.4: PBFT Progress Outcomes -> Hierarchical Bayesian Risk

## Paper-level claim

We do **not** claim that protocol logs identify all Byzantine identities or the exact number of latent Byzantine validators. We make the narrower, testable claim:

> Under an explicit active-withholding model and observable network/workload context, PBFT progress outcomes provide evidence about a shard's active quorum-blocking load. A budgeted controller uses the posterior to choose one random exchange at an epoch boundary and can reduce subsequent local threshold-risk in controlled simulation.

## Hidden state

For shard `s` and epoch `t`:

    A[s] = number of persistent active quorum-blocking Byzantine validators

`A` differs from the total latent Byzantine count. In v1.5, the main threat model fixes the active blocking set over consecutive epochs; only a reconfiguration changes which shard contains these blockers. Intermittent attacker activation requires a separate hidden-state transition and is not claimed here.

The model also contains one system-level nuisance state:

    gamma = persistent attack-intensity regime

`gamma` indexes a small prior grid of primary/backup withholding probabilities. The particle state is therefore `(A_1, ..., A_K, gamma)`. This avoids pretending that the attacker aggressiveness is known exactly.

## Protocol observation

Each logical batch `b` has exactly one final outcome:

    N: normal completion in the original view
    R: completion after at least one installed NEW-VIEW
    S: operational stall by the epoch deadline

Epoch observation for shard `s`:

    Y[s,t] = (N_N[s,t], N_R[s,t], N_S[s,t])

The three counts are mutually exclusive and sum to the number of real pending batches. Timeout / VIEW-CHANGE / NEW-VIEW are preserved as diagnostic trace data but are not multiplied as independent evidence.

## Event-level likelihood

For an active load `a`, observable context `xi`, and attack regime `gamma`:

    phi_o(a, xi, gamma) = P(O_b = o | A[s,t] = a, xi, gamma)

for `o` in `{N, R, S}`.

The simulator generates this likelihood by executing a PBFT-style view chain:

1. an active primary may withhold PRE-PREPARE;
2. otherwise each active replica may withhold a timely PREPARE/COMMIT vote;
3. honest replicas can miss the deadline according to the visible context;
4. a view with fewer than `2f+1` timely committers triggers timeout -> VIEW-CHANGE -> NEW-VIEW;
5. a batch is `S` only after the recovery budget is exhausted.

Thus `A > f` raises the probability of `S`, but does not force every batch to stall: attackers may selectively cooperate in individual views.

## Exact constrained Bayesian update

Let L be a configuration-time upper bound on the network-wide persistent active blocking load. Conditional on L, the prior over equal-size shard counts is multivariate hypergeometric. Within one epoch, the N/R/S likelihood factorizes across shards, so we compute exact posterior marginals using dynamic programming and average over the finite attack-regime grid:

    P(A, gamma | Y, xi, L) proportional to P(Y | A, xi, gamma) P(A | L) P(gamma).

The controller uses an epoch-reset posterior: it does not silently carry stale latent counts through a membership change. The controller reports:

    R[s,t] = P(A[s,t] > f | Y, xi)

where every committee satisfies `n = 3f + 1`.

## Control action

The deployable action is:

    a = (h, c, k)

where `h` is the posterior-hot shard, `c` is a lower-risk partner, and `k` validators are uniformly sampled from each committee and exchanged. The controller evaluates a finite action set and performs at most one exchange per epoch.

A simulator-only oracle policy is retained solely as an upper bound. It sees true shard counts but still uses random membership exchange; it is never a deployable baseline.

## Explicit scope and limitations

- No node identity inference.
- A declared global active-load budget L is required by the exact posterior; robustness to budget misspecification is evaluated separately.
- No unconditional log-to-Byzantine-count mapping.
- No claim that view recovery is permanent consensus failure.
- No strict stationary-distribution guarantee: the engineering controller uses a finite action set.
- A BFT implementation-level handoff experiment remains required before claiming production reconfiguration cost.
