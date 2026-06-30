# ProgressRisk v1.13 runner audit repair

## Do not apply v1.12

A post-release audit found one remaining fatal control-flow defect in v1.12:
replica 4 is intentionally outside the initial `0,1,2,3` view. In BFT-SMaRt
v2.0, `ServiceReplica` blocks in its constructor while such a replica waits for
the TTP join reply. Therefore its post-constructor `STATEFUL_COUNTER_READY`
marker cannot appear before `DefaultVMServices addServer` is issued.

## v1.13 fixes

1. Retains v1.12's full per-runtime `hosts.config` rewrite, unique ports, and
   direct-JVM cleanup.
2. Waits for BFT-SMaRt's own `Waiting for the TTP` log before issuing the add
   command. This log is emitted only after the joining replica has built and
   bound its replica-to-replica communication listener.
3. Waits for `STATEFUL_COUNTER_READY` only after the add command and view
   installation, then verifies `STATE_TRANSFER_INSTALLED` with a nonzero
   operation count and exact configured payload size.
4. Adds `STATEFUL_COUNTER_FIRST_ORDERED` and waits for it before reconfiguration,
   so state transfer cannot be falsely counted before the initial committee has
   actually executed a request.
5. Streams probe CSV rows to disk, so a failed trial retains partial probe
   evidence in the uploaded artifact.
6. Makes the workflow smoke-only by default. The formal 20×3 sweep requires an
   explicit `run_formal_sweep=true` selection after a successful preflight.

This patch is a runner correction only. It changes no scientific result and no
paper claim.
