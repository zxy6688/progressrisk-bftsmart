# Submission gates: ProgressRisk v1.10

## Frozen research line

PBFT batch progress -> `{Normal, Recovered, Stalled}` -> exact constrained
Bayesian posterior -> one random `k`-for-`k` exchange `a=(h,c,k)`.

No new observation variable, no timeout/view-change product likelihood, no
validator identity inference, and no global Markov-state claim may be added
without an explicit project decision.

## Passed

- Protocol-grounded, mutually exclusive batch-level N/R/S observation.
- Exact constrained posterior and finite random exchange controller.
- Development/test separation: `k_max=3` selected on development seeds and
  evaluated on 24 unseen paired seeds.
- Attack-intensity mismatch, scale, action-capacity, context negative-control,
  calibration, and observation-exposure evaluations.
- Raw held-out policy rows and deterministic paired-bootstrap analysis are now
  included in the release.
- `pytest`: 8/8 passed in a clean Python 3.13 environment on 2026-06-30.
- Existing BFT-SMaRt harness passed Bash syntax validation; it has not been
  mistaken for an executed deployment experiment.

## Only blocking empirical gate

### Execute the official BFT-SMaRt v2.0 membership-handoff benchmark

The automated harness must run against official BFT-SMaRt v2.0 and produce,
for each state size, 20 independent matched no-op and reconfiguration trials,
raw logs, a hardware/runner record, `summary.csv`, and a control-adjusted
service-gap analysis. Report `T_add_view`, `T_state_ready`, `T_remove_view`,
`T_cycle`, explicit `currentView` propagation time, and p50/p95 results.

No handoff number may enter the paper before this gate is completed.

## Final paper gate after BFT-SMaRt results exist

1. Insert the implementation handoff table/figure and exact hardware metadata.
2. Replace future-validation wording only with measured scope.
3. Complete paper-quality review: references, notation, figure readability,
   anonymity, and INFOCOM 2027 template compliance.
4. Reproduce tests, raw held-out aggregation, and clean paper build from a
   fresh checkout.
