# Submission gates: ProgressRisk v1.11

## Frozen research line

PBFT batch progress → `{Normal, Recovered, Stalled}` → exact constrained Bayesian posterior → one random `k`-for-`k` exchange `a=(h,c,k)`.

The observation model, inference target, action semantics, held-out seed set, and main simulator results are frozen. No validator identity inference, timeout/view-change multiplication, or global Markov-stationarity claim is permitted.

## Passed and locally revalidated on 2026-06-30

- 8/8 Python unit tests pass.
- Held-out raw 24-seed table regenerates the frozen 0.792 → 0.203 main result.
- Paired bootstrap regenerates absolute reduction 0.5885 and 95% interval [0.4323, 0.7309].
- BFT-SMaRt harness passes Bash syntax and Python compilation checks.
- Source-level API audit confirms BFT-SMaRt v2.0 supports `DefaultVMServices` add/remove with four add arguments, `DefaultSingleRecoverable` snapshot hooks, and explicit `currentView` propagation.

## Only blocking empirical gate

Run `.github/workflows/bftsmart-handoff.yml` successfully on a GitHub-hosted or comparable external runner.

The formal output must contain, for each payload size 0 / 1 MiB / 16 MiB:

- 20 no-op rows and 20 reconfiguration rows;
- nonempty add-view, state-ready, remove-view, and cycle-to-resume times for every reconfiguration trial;
- state-transfer markers that match payload bytes and show post-warmup ordered operations;
- raw probe logs and runner metadata;
- `validation.json` with `valid: true`.

Until then, the manuscript remains a controlled-simulation paper with an unexecuted implementation benchmark. No real handoff result may be claimed.

## Final paper gate after a valid artifact

1. Summarize p50/p95 cost and matched control-adjusted reply gaps.
2. State explicitly that this is a one-committee handoff microbenchmark, not an end-to-end two-shard exchange.
3. Add the runner/JDK/BFT-SMaRt revision to the experiment section.
4. Rebuild all simulator tables, paper PDF, and artifact hashes from a clean checkout.
