from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a completed BFT-SMaRt handoff benchmark.")
    parser.add_argument("summary", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--expected-trials", type=int, required=True)
    parser.add_argument("--expected-states", required=True, help="comma-separated state sizes in bytes")
    args = parser.parse_args()

    df = pd.read_csv(args.summary)
    expected_states = [int(x) for x in args.expected_states.split(",")]
    errors: list[str] = []
    expected_cols = {
        "mode", "state_bytes", "trial", "t_add_view_ms", "t_state_ready_ms",
        "t_remove_view_ms", "t_cycle_resume_ms", "probe_successes",
        "state_transfer_payload_bytes", "state_transfer_operations",
    }
    missing = expected_cols - set(df.columns)
    if missing:
        errors.append(f"summary missing columns: {sorted(missing)}")

    for state in expected_states:
        sub = df[df["state_bytes"] == state]
        for mode in ("no_op", "reconfig"):
            count = len(sub[sub["mode"] == mode])
            if count != args.expected_trials:
                errors.append(f"state={state}, mode={mode}: expected {args.expected_trials} rows, found {count}")

        rec = sub[sub["mode"] == "reconfig"]
        if not rec.empty:
            required = ["t_add_view_ms", "t_state_ready_ms", "t_remove_view_ms", "t_cycle_resume_ms"]
            if rec[required].isna().any().any():
                errors.append(f"state={state}: a reconfiguration timing metric is missing")
            payload = pd.to_numeric(rec["state_transfer_payload_bytes"], errors="coerce")
            if (payload != state).any():
                errors.append(f"state={state}: state-transfer payload size does not match configured payload")
            ops = pd.to_numeric(rec["state_transfer_operations"], errors="coerce")
            if (ops <= 0).any() or ops.isna().any():
                errors.append(f"state={state}: state-transfer marker lacks post-warmup ordered operations")
            successes = pd.to_numeric(rec["probe_successes"], errors="coerce")
            if (successes <= 0).any() or successes.isna().any():
                errors.append(f"state={state}: a reconfiguration trial has no successful client probes")

    result = {
        "valid": not errors,
        "expected_trials": args.expected_trials,
        "expected_states": expected_states,
        "rows": int(len(df)),
        "errors": errors,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    if errors:
        raise SystemExit("; ".join(errors))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
