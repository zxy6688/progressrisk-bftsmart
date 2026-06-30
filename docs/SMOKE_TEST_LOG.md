# Internal Smoke-Test Log (Not Paper Results)

## Commands run

```bash
python -m pytest -q
python run_experiments.py --quick --seeds 3 --out results
python run_experiments.py --seeds 4 --out full_smoke
```

## Outcome

- Unit tests: 3 passed.
- The protocol likelihood has the expected qualitative shape: as active blockers rise while `a <= f`, recovery becomes more frequent; when `a > f`, all-withholding executions stall by construction.
- The finite action controller executes and writes per-shard outcomes, posterior risk, simulator-only active load, migration volume, and controller runtime.
- Context is supplied explicitly to the likelihood. A negative-control run shows that severe benign degradation can still shift the posterior mean for sub-threshold active load; however, it did not create a posterior over-threshold decision in the tested setting. This is a limitation to test rather than a success claim.

## Why these numbers are not publishable

The likelihood currently uses the same declared event generator as the simulator. This is a correctness check, not evidence of real-world calibration. The paper must add held-out attack parameters, network mismatch, workload variation, and an implementation-level validation layer before reporting performance claims.
