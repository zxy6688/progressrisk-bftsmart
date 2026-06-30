# v1.11 manifest

This is the current execution package for the INFOCOM sharded-BFT project. It supersedes v1.10 for all production-benchmark work.

- `paper/main.pdf` — unchanged 6-page working manuscript. No unexecuted handoff number is inserted.
- `pbft_progress_sim/` — frozen PBFT-style event generator, exact constrained posterior, and finite random-exchange controller.
- `results_v110/` — raw 24-seed held-out policy records and deterministic paired bootstrap.
- `production/` — BFT-SMaRt v2.0 4→5→4 final-run harness with verified state transfer, no-op controls, raw client probes, runner metadata, and result validator.
- `.github/workflows/bftsmart-handoff.yml` — one-click external runner; requires a passing 1 MiB preflight before the 20×3 formal sweep.
- `docs/SUBMISSION_GATES_v111.md` — current hard gate registry.
- `docs/LOCAL_PREFLIGHT_v111.md` — exact local checks passed and the external-network execution boundary.

The only uncompleted empirical item is execution of the official BFT-SMaRt benchmark on a runner with outbound GitHub/Gradle access.
