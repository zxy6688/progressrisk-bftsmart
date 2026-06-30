# A2 proof-bearing state-transfer fix

## Exact root cause found from the failed A2 artifact

The failed run configured `system.totalordermulticast.checkpoint_period = 1`.

After warm-up and the join reconfiguration, every source replica logged:

```
CID requested: 3. Last checkpoint: 3. Last CID: -1
```

In BFT-SMaRt v2.0 `DefaultSingleRecoverable`, a BFT state reply is discarded and
replaced by an empty `DefaultApplicationState` when it cannot provide a
`CertifiedDecision` for the requested CID. A snapshot-only checkpoint at CID 3
has no message batch at CID 3 from which that decision can be reconstructed.
Thus source replicas printed `Sending state...`, but replica 4 received no
installable state and retried until `Negative delay` occurred.

## Fix

All runtime copies now use:

```
system.totalordermulticast.checkpoint_period = 2
```

With the fixed A2 warm-up:

- the non-empty counter=3 snapshot is checkpointed at CID 2;
- the join reconfiguration occupies CID 3 as a retained no-op log entry;
- state transfer at CID 3 contains the CID-2 snapshot plus the proof-bearing
  CID-3 log entry.

The runner now explicitly verifies on every source replica:

```
CID requested: 3. Last checkpoint: 2. Last CID: 3
Constructing ApplicationState up until CID 3
```

before accepting replica 4's `STATE_TRANSFER_INSTALLED` marker.

## Local reproduction performed before delivery

Using the exact failing artifact's BFT-SMaRt v2.0 distribution, 1 MiB snapshot,
and a fresh port range, the corrected configuration completed:

```
0,1,2,3 -> 0,1,2,3,4 -> 1,2,3,4
```

with replica 4 installing `counter=3`, the post-add client receiving `4`, and
the post-remove client receiving `5`.

This patch changes only the A2 workflow and its runner. Do not run A3 until
this GitHub Actions A2 gate succeeds.
