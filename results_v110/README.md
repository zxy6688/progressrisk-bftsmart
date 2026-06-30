# Held-out raw-record repair and paired analysis (v1.10)

This directory fixes a reproducibility packaging gap in v1.9: the 24 common
held-out seeds were documented only through an aggregate table. The policy
means were therefore auditable but the paired bootstrap could not be rerun
from the release alone.

`heldout_by_seed.csv` is a deterministic re-execution of the frozen
`run_final_validation_v18.py --suite heldout` experiment on the declared
seed range `120000..120023`, with no changes to the observation model,
posterior, controller, parameters, policies, or seed set.

- All non-timing primary aggregate quantities exactly match
  `results_v18/heldout_policy_aggregate.csv` to numerical precision.
- Controller milliseconds are environment-dependent and are kept only as
  a local reproducibility observation; the paper retains its original run
  measurement until a hardware metadata table is finalized.
- `heldout_paired_bootstrap.csv` uses 10,000 paired resamples with
  `numpy.random.default_rng(20260630)`. Its first row reproduces the
  paper's reported 0.589 reduction and 95% interval [0.432, 0.731], up to
  rounding.
- `aggregate_heldout_v110.py` regenerates both derived CSV files from raw
  rows and validates 24 common seeds per policy.
