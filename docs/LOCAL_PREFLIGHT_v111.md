# v1.11 local preflight record

Run date: 2026-06-30.

## Completed inside the packaging environment

- `PYTHONPATH=. pytest -q` → **8 passed**.
- `bash -n production/run_bftsmart_handoff_benchmark.sh` → passed.
- `python3 -m py_compile production/analyze_bftsmart_handoff.py production/validate_bftsmart_handoff.py` → passed.
- `aggregate_heldout_v110.py` regenerated both held-out aggregate and paired-bootstrap CSV files byte-for-byte from `results_v110/heldout_by_seed.csv`.
- The two Java benchmark sources were compiled against minimal API-shape stubs matching the official BFT-SMaRt v2.0 constructor and abstract-method signatures; this validates source syntax and the method-shape assumptions only.

## Not executable in this environment

The official BFT-SMaRt v2.0 checkout and Gradle build could not start because outbound DNS to `github.com` is unavailable in this sandbox (`Could not resolve host: github.com`). Therefore this document is **not** a BFT-SMaRt result and contains no deployment measurement.

The GitHub Actions workflow is the formal execution route. It downloads the pinned official `v2.0` tag, runs a mandatory 1 MiB stateful preflight, and only then launches the 20-trial × 3-state-size sweep.
