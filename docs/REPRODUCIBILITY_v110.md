# Reproducibility record v1.10

## Verification completed in the release build

1. `PYTHONPATH=. pytest -q` -> 8 passed.
2. Frozen held-out suite rerun on the declared seed blocks
   `120000..120023`, four seeds per block.
3. The complete raw policy-by-seed file is included under `results_v110/`.
4. Re-aggregation exactly matches all original non-timing fields in
   `results_v18/heldout_policy_aggregate.csv`.
5. A 10,000-draw paired bootstrap with RNG seed `20260630` regenerates the
   paper's rounded 95% interval `[0.432, 0.731]` for no-reconfiguration
   minus risk-aware exchange.
6. `bash -n production/run_bftsmart_handoff_benchmark.sh` passes. This is
   a syntax check only; it is not a BFT-SMaRt run.

## Commands

```bash
PYTHONPATH=. pytest -q
PYTHONPATH=. python run_final_validation_v18.py --suite heldout \
  --seed-start 120000 --seeds 24 --out /tmp/heldout
python aggregate_heldout_v110.py --raw /tmp/heldout/heldout_by_seed.csv \
  --out /tmp/heldout_aggregated
cd paper && pdflatex main.tex && pdflatex main.tex
```

The held-out run can be split into six four-seed chunks when wall-clock
limits are tight, then concatenate the six `heldout_by_seed.csv` files before
calling the aggregator.
