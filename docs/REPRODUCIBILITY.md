# Reproducibility Notes for v1.4

## Nominal configuration

The default `SimulationConfig` is the nominal controlled setting:

- 198 validators / 9 shards / 22 validators per shard / `f=7`;
- global malicious fraction 0.24;
- 72 logical batches per shard per epoch and 24 epochs;
- finite action set includes all 8 partner shards and `k=1,...,6`;
- a hierarchical prior over three persistent attack-intensity regimes.

## Run tests

```bash
python -m pytest -q
```

## Run one reproducible batch

```bash
python run_experiments.py --seeds 12 --seed-start 1000 --out nominal_batch_1
python run_experiments.py --seeds 12 --seed-start 1012 --out nominal_batch_2
```

The internal 24-seed nominal result combines seed IDs 1000--1023. The two-batch layout avoids long single-process wall time in this environment; it does not change the model or seeds.

## Run validation

```bash
python run_validation.py --seeds 12 --context-trials 40 --sensitivity-seeds 8 --out validation
```

## Result discipline

- `nominal_v1_4_24_combined/` is the primary controlled-simulation result.
- The point-likelihood attack mismatch result is an ablation, not the proposed method.
- The held-out attack test and sensitivity runs in this package are preliminary unless their seed counts match a predeclared final table.
- All current results are simulator results; none are real BFT deployment measurements.
