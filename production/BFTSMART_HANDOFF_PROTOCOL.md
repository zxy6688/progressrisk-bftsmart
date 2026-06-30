# BFT-SMaRt membership-handoff microbenchmark protocol

## Objective

This benchmark supplies the deployment-level evidence that the simulator cannot provide: the operational cost of one membership handoff. It does **not** validate the Bayesian signal, which is evaluated separately with controlled simulator ground truth.

Each reconfiguration trial executes:

```text
4-replica baseline -> add waiting spare replica -> state transfer -> explicit currentView propagation -> remove spare -> explicit currentView propagation -> resumed client replies
```

A matched no-op trial uses the same state size, runtime layout, warm-up, and client probe, but does not send `DefaultVMServices` commands.

## Automated implementation

Run:

```bash
export BFTSMART_HOME=/absolute/path/to/bft-smart/library
export RESULTS_DIR=$PWD/bftsmart_handoff_results
export TRIALS=20
export STATE_SIZES=0,1048576,16777216
./production/run_bftsmart_handoff_benchmark.sh
```

The script requires the official BFT-SMaRt v2.0 source. It builds the distribution, creates isolated runtime directories, compiles a stateful counter service and closed-loop probe client, and writes raw logs and a `summary.csv` file. It then produces `handoff_summary_by_state.csv` and `handoff_control_adjusted_gaps.csv`.

## Fixed design

- Initial committee: replicas 0–3, $f=1$.
- Spare replica: 4, started before join and waiting for the trusted reconfiguration message.
- Transition: `4 -> 5 -> 4` with `f=1` throughout.
- State sizes: zero/minimal, 1 MiB, 16 MiB by default.
- Workload: continuous ordered counter updates from a timestamped client.
- Replications: 20 no-op + 20 reconfiguration trials per state size by default.

## Recorded metrics

| Metric | Meaning |
|---|---|
| `t_add_view_ms` | add command to all original replicas logging the first installed new view |
| `t_state_ready_ms` | add command to spare replica completing state installation |
| `t_remove_view_ms` | remove command to all remaining replicas logging final view |
| `t_cycle_resume_ms` | add command to first successful client reply after final removal |
| `t_view_propagation_ms` | explicit `currentView` file-copy time |
| `longest_reply_gap_ms` | largest interval between successive client successes |
| `excess_reply_gap_ms` | reconfiguration reply gap minus matched no-op reply gap |

## Reporting rule

Report hardware/runner metadata, all state sizes, trial counts, median and 95th-percentile values, no-op values, and raw-data availability. Do not collapse `currentView` propagation or state transfer into an unreported implementation detail.
