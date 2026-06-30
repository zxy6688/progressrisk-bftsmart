# ProgressRisk v1.14 — withdrawn v1.13 repair

Do not run v1.13. A source-level audit of the pushed v1.13 script found that it still appended to the stock `hosts.config`, leaving replicas 0–3 on the stock ports across the no-op and reconfiguration subtrials. It also started replica 4 in the no-op control and did not use an `exec` launch wrapper that guarantees the recorded PID is the JVM process.

## v1.14 changes

1. Replaces—not appends—the full `hosts.config` on every isolated local runtime, assigning all five replicas unique per-trial ports.
2. Uses `exec java` in the launched subshell so cleanup kills the actual JVM.
3. Starts only replicas 0–3 for the no-op control.
4. In the reconfiguration arm, waits for the official BFT-SMaRt `Waiting for the TTP` message from replica 4 before calling `DefaultVMServices addServer`.
5. Emits and waits for the first successfully ordered application request before joining replica 4, so a zero-operation state transfer cannot be accepted.
6. Streams probe outcomes to CSV and keeps the workflow smoke-only (`trials=1`, `state_sizes=1048576`) by default.

This patch changes only the measurement harness. It changes no simulator result and no paper claim.
