# Submission gates: ProgressRisk v1.9

## Frozen main line

PBFT logical batch progress -> `{Normal, Recovered, Stalled}` -> exact constrained Bayesian posterior -> one budgeted random exchange `a=(h,c,k)`.

No new observation variable, no return to the old timeout/view-change product likelihood, and no reintroduction of the large Markov state search are permitted without a new project decision.

## Gates already passed

- Protocol-grounded batch-level N/R/S observation is implemented and tested.
- Exact constrained posterior replaces the invalid static-particle posterior.
- Development/test separation is observed: `k<=3` was selected on development seeds and evaluated on 24 unseen paired seeds.
- Attack-intensity mismatch, scale, active-load capacity, and observation-exposure robustness are recorded.
- Clean Python environment: `pytest` passes 8/8 in the v1.9 package.

## Remaining blocking gate

### BFT implementation handoff measurement

The paper may not make implementation-level claims until `production/run_bftsmart_handoff_benchmark.sh` has been executed against official BFT-SMaRt v2.0 and produces:

- 20 independent no-op and reconfiguration trials for each state size;
- raw client probe logs and replica/TTP logs;
- `summary.csv`, per-state median and p95 values;
- hardware/runner metadata;
- reported `T_add_view`, `T_state_ready`, `T_remove_view`, `T_cycle`, explicit `currentView` propagation time, and control-adjusted service gap.

The harness is fully automated and includes a GitHub Actions workflow, but cannot be run in the current environment because it has no outbound DNS access to retrieve the official BFT-SMaRt source and its Gradle dependencies.

## Paper-finalization gate after the handoff run

- Insert the real handoff table and state-size plot.
- Replace all ``future validation'' wording with the measured scope.
- Conduct one final citation/metadata pass against the target INFOCOM call for papers and template.
- Run the reproducibility workflow from a clean checkout.
