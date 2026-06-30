#!/usr/bin/env python3
"""Aggregate all A3 matrix artifacts without silently dropping failures."""
from __future__ import annotations

import csv
import math
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
out = Path(sys.argv[2] if len(sys.argv) > 2 else 'bftsmart_final_report')
out.mkdir(parents=True, exist_ok=True)
raw_files = sorted(root.rglob('a3_raw_trials.tsv'))
if not raw_files:
    print('No A3 raw trial files found.', file=sys.stderr)
    sys.exit(2)

rows: list[dict[str, str]] = []
seen = set()
for path in raw_files:
    with path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            key = (row.get('state_label'), row.get('pair'), row.get('treatment'))
            # Artifacts are expected to be unique; duplicate rows are a workflow error, not averaged away.
            if key in seen:
                print(f'Duplicate A3 row: {key}', file=sys.stderr)
                sys.exit(2)
            seen.add(key)
            rows.append(row)

fieldnames = [
    'state_label', 'snapshot_payload_bytes', 'pair', 'treatment', 'order', 'status', 'port_base',
    'T_control_3ops_ms', 'T_add_view_ms', 'T_state_ready_ms', 'T_post_add_reply_ms',
    'T_remove_view_ms', 'T_cycle_ms', 'result_dir'
]
with (out / 'a3_all_trials.tsv').open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
    writer.writeheader()
    writer.writerows(sorted(rows, key=lambda r: (int(r['snapshot_payload_bytes']), int(r['pair']), r['treatment'])))

expected_pairs = int(os.environ.get('EXPECTED_PAIRS', '20'))
expected_labels = {'0B', '1MiB', '16MiB'}
expected_rows = expected_pairs * len(expected_labels) * 2
failure_rows = [r for r in rows if r['status'] != 'PASS']
missing_labels = sorted(expected_labels - {r['state_label'] for r in rows})

metrics = ['T_control_3ops_ms', 'T_add_view_ms', 'T_state_ready_ms', 'T_post_add_reply_ms', 'T_remove_view_ms', 'T_cycle_ms']
def percentile95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]

summary_rows = []
groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
for r in rows:
    groups[(r['state_label'], r['treatment'])].append(r)
for (label, treatment), group in sorted(groups.items(), key=lambda x: (int(x[1][0]['snapshot_payload_bytes']), x[0][1])):
    passed = [r for r in group if r['status'] == 'PASS']
    for metric in metrics:
        values = []
        for r in passed:
            value = r.get(metric, 'NA')
            if value not in ('', 'NA', None):
                values.append(float(value))
        summary_rows.append({
            'state_label': label,
            'snapshot_payload_bytes': group[0]['snapshot_payload_bytes'],
            'treatment': treatment,
            'metric': metric,
            'n_total': len(group),
            'n_pass': len(passed),
            'pass_rate': f'{len(passed) / len(group):.3f}' if group else '0.000',
            'n_metric': len(values),
            'median_ms': f'{statistics.median(values):.1f}' if values else 'NA',
            'p95_ms': f'{percentile95(values):.1f}' if values else 'NA',
            'min_ms': f'{min(values):.1f}' if values else 'NA',
            'max_ms': f'{max(values):.1f}' if values else 'NA',
        })

sum_fields = ['state_label', 'snapshot_payload_bytes', 'treatment', 'metric', 'n_total', 'n_pass', 'pass_rate', 'n_metric', 'median_ms', 'p95_ms', 'min_ms', 'max_ms']
with (out / 'a3_summary.csv').open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=sum_fields)
    writer.writeheader()
    writer.writerows(summary_rows)

lines = [
    '# BFT-SMaRt membership-handoff cost study', '',
    f'- Expected raw rows: {expected_rows}',
    f'- Observed raw rows: {len(rows)}',
    f'- Failed raw rows: {len(failure_rows)}',
    f'- Missing state labels: {", ".join(missing_labels) if missing_labels else "none"}', '',
    '## Summary (milliseconds)', '',
    '| State payload | Treatment | Metric | n pass / total | Median | p95 | Min–Max |',
    '|---|---|---:|---:|---:|---:|---:|',
]
for r in summary_rows:
    if r['n_metric'] == '0':
        continue
    lines.append(f"| {r['state_label']} | {r['treatment']} | {r['metric']} | {r['n_pass']}/{r['n_total']} | {r['median_ms']} | {r['p95_ms']} | {r['min_ms']}–{r['max_ms']} |")
if failure_rows:
    lines.extend(['', '## Failed trial rows', ''])
    for r in failure_rows:
        lines.append(f"- {r['state_label']} pair {r['pair']} {r['treatment']}: see `{r['result_dir']}/verdict.txt` in its raw artifact.")
(out / 'a3_summary.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('\n'.join(lines))

if len(rows) != expected_rows or failure_rows or missing_labels:
    sys.exit(1)
