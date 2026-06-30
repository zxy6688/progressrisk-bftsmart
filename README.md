# ProgressRisk v1.11: audited simulation and final-run BFT-SMaRt handoff harness

This is the single current package for the INFOCOM sharded-BFT project. It supersedes v1.9.

## Frozen main line

`PBFT batch progress -> {Normal, Recovered, Stalled} -> exact constrained Bayesian posterior -> finite random exchange a=(h,c,k)`.

The package does **not** identify validators. It estimates a shard-level persistent active withholding load under a declared context and threat budget, then chooses at most one random `k-for-k` exchange per epoch.

## What is now supported by completed controlled experiments

1. **Development-only budget choice.** On 12 paired development seeds, `k_max=3` is the migration-efficiency knee: failure-epoch fraction 0.184 with 2.49 moved validators/epoch. Larger budgets move materially more validators for small additional reduction.
2. **Held-out main test.** With the preselected `k_max=3`, 24 previously unseen paired seeds give failure-epoch fraction 0.792 for no reconfiguration and 0.203 for ProgressRisk. The paired absolute reduction is 0.589 (bootstrap 95% CI [0.432, 0.731]); the controller moves 2.56 validators/epoch.
3. **Held-out attack-intensity mismatch.** A likelihood mixture over attack regimes reduces failure epochs from 0.833 to 0.299 under a held-out attack generator; a point-likelihood ablation reaches 0.413.
4. **Scale.** With committee size fixed at 22, the controller reduces true over-threshold shard-epoch fraction at 5, 9, and 18 shards.
5. **Raw held-out audit.** The complete 24-seed rows and deterministic paired bootstrap are now packaged. All primary non-timing aggregates exactly reproduce the frozen v1.8 held-out table; risk-aware exchange also beats the risk-triggered random-partner baseline by 0.203 failure-epoch fraction (paired 95% CI [0.123, 0.285]).
6. **Boundary.** At persistent active fraction 0.32, the current `k <= 6` controller has no remaining dilution capacity.

Detailed source paths and assumptions are in `docs/RESULT_REGISTRY_v19.md`.

## What is deliberately NOT claimed

- The controlled PBFT-style event simulator is not a production PBFT deployment.
- The likelihood does not identify all Byzantine validators or cover intermittently active/adaptive adversaries.
- Logical migration count and controller compute time are not state-transfer or membership-handoff latency.
- BFT-SMaRt handoff results are not included. `production/` now contains the v1.11 final-run harness: a mandatory stateful preflight, verified state-install marker, matched no-op controls, unique port blocks, raw-log analysis, runner metadata, validation checks, and a GitHub Actions workflow. The current sandbox cannot resolve GitHub, so it cannot execute the official dependency itself.

## Reproduce tests

```bash
PYTHONPATH=. pytest -q
```

## Reproduce the independent held-out test

The 24-seed test was run in six chunks to avoid runtime truncation:

```bash
for i in 0 1 2 3 4 5; do
  PYTHONPATH=. python run_final_validation_v18.py \
    --suite heldout --seed-start $((120000 + 4*i)) --seeds 4 \
    --out heldout_chunk${i}
done
```

Merge the `heldout_by_seed.csv` files exactly as recorded in `docs/RESULT_REGISTRY_v18.md`.

## Compile the paper

```bash
cd paper
pdflatex main.tex
pdflatex main.tex
```

The paper is a 6-page submission-oriented working manuscript. It is not labelled ready to submit because implementation-level BFT membership-handoff measurement remains outstanding; see `docs/SUBMISSION_GATES_v19.md`.


## v1.11 additions

- Observation-exposure robustness: 12 paired held-out seeds at 24, 72, and 216 logical batches per epoch.
- Automated BFT-SMaRt v2.0 reconfiguration harness with stateful snapshots, no-op controls, raw client probes, and a GitHub Actions workflow.
- Submission gate registry that prevents unexecuted deployment experiments from entering the paper.

- Raw 24-seed held-out policy records, deterministic paired bootstrap, and a standalone aggregation validator.
- Repair of a paper source typesetting typo in the parameter-selection paragraph.


## v1.11 final-run status

The BFT-SMaRt benchmark harness was strengthened after a source-level v2.0 API audit and is ready for external execution. This package still contains **no fabricated handoff values**: the sole remaining submission gate is a successful Actions/local artifact with `validation.json: valid=true`.
