# Production membership-handoff benchmark — v1.11 final-run harness

This is the implementation-level validation layer for ProgressRisk. It measures **one actual BFT-SMaRt v2.0 committee handoff**:

```text
4-replica committee → add waiting spare → state transfer → distribute currentView → remove spare → distribute currentView → first resumed client reply
```

It is deliberately a **single-committee handoff microbenchmark**, not a full two-shard `k-for-k` implementation. It validates the operational unit that the controlled simulator cannot measure: how much real BFT membership management, state installation, and client interruption cost for one moved validator.

## What is newly enforced

- Uses official BFT-SMaRt **v2.0**.
- Performs an automatic **1 MiB stateful preflight pair** before any formal sweep.
- Refuses to accept a join as “state transfer succeeded” unless the spare logs `installSnapshot` with the configured payload size **and at least one pre-join ordered operation**.
- Uses distinct TCP-port blocks for every state/trial/mode, avoiding stale-process port reuse.
- Saves runner/JDK/BFT-SMaRt revision metadata and uploads artifacts even if preflight fails.
- Validates that every requested state size has the intended number of matched no-op and reconfiguration trials before reporting a summary.

## Formal design

- Initial committee: replicas `0–3`, `n=4`, `f=1`.
- Spare replica: `4`, started before the add command and blocked until BFT-SMaRt sends the join result.
- Transition: `4 → 5 → 4`, with `f=1` unchanged.
- Default payload sizes: `0`, `1 MiB`, `16 MiB`.
- Formal run: 20 matched no-op and reconfiguration trials per state size.
- Workload: one continuous ordered-counter client; the client has a 5-second ordered invocation timeout so outages appear in raw probe logs.

## Recorded measurements

- add-command → all incumbent replicas install new view;
- add-command → spare installs state with verified payload size and nonzero ordered-operation count;
- remove-command → incumbents install final view;
- add-command → first post-removal successful client reply;
- explicit `currentView` distribution time;
- longest gap between successful client replies;
- matched no-op-adjusted reply gap;
- raw BFT-SMaRt logs, raw client probes, runner metadata, and validation report.

## Run locally

```bash
export BFTSMART_HOME=/absolute/path/to/bft-smart/library
export RESULTS_DIR=$PWD/bftsmart_handoff_results
export TRIALS=20
export STATE_SIZES=0,1048576,16777216
./production/run_bftsmart_handoff_benchmark.sh
```

## Run in GitHub Actions

Push this repository unchanged, open **Actions → bftsmart-handoff → Run workflow**, and leave the default parameters. The workflow first executes one stateful preflight pair. Only if that passes does it run the formal sweep. The uploaded artifact contains all raw logs even when a stage fails.

## Claim discipline

No handoff number is paper evidence until the formal sweep succeeds, the generated `validation.json` says `valid: true`, and the paper reports runner metadata, state sizes, trial counts, medians, p95 values, no-op controls, and raw artifact availability.
