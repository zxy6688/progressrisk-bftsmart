FINAL A3 COST PIPELINE — RUN ONLY AFTER A2 #2 PASSED

What this workflow measures:
- Single committee with an application payload of 0 B, 1 MiB, or 16 MiB.
- For each payload size, 20 adjacent matched pairs.
- Each pair alternates order and contains: (a) a four-member stateful no-reconfiguration control, and (b) a real stateful 4 -> 5 -> 4 membership handoff.

Critical fixed protocol setting:
- Both arms use checkpoint period 2. For the handoff, the joining replica restores from the checkpoint at CID 2 and the proof-bearing log entry at CID 3. This is the same geometry that passed standalone A2 #2.

Output metrics (milliseconds):
- T_control_3ops_ms: three ordered requests without reconfiguration.
- T_add_view_ms: from add command start until initial replicas install view 1.
- T_state_ready_ms: from add command start until replica 4 installs non-empty transferred state.
- T_post_add_reply_ms: from add command start until a fresh post-add client reply.
- T_remove_view_ms: from remove command start until survivors install view 2.
- T_cycle_ms: from add command start until final post-remove client reply.

Artifacts:
- a2-preflight-results
- a3-raw-0B / a3-raw-1MiB / a3-raw-16MiB
- bftsmart-final-cost-report

Artifacts retain verdicts, metrics, metadata, and compact protocol evidence. Bulky copied runtimes and raw snapshot files are removed after each successful/failed trial so the final upload remains practical.

Run: Actions -> bftsmart-final-cost -> Run workflow. Do not run old bftsmart-handoff workflows.
