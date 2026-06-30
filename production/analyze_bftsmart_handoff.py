from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

if len(sys.argv) != 3:
    raise SystemExit('Usage: analyze_bftsmart_handoff.py summary.csv output_dir')
summary, out = map(Path, sys.argv[1:])
out.mkdir(parents=True, exist_ok=True)
df = pd.read_csv(summary)
metrics = ['t_add_view_ms','t_state_ready_ms','t_remove_view_ms','t_cycle_resume_ms','t_view_propagation_ms','longest_reply_gap_ms','probe_successes','probe_failures']
rows=[]
for (mode, state), sub in df.groupby(['mode','state_bytes']):
    r={'mode':mode,'state_bytes':state,'n':len(sub)}
    for m in metrics:
        x=pd.to_numeric(sub[m],errors='coerce').dropna()
        r[f'{m}_median']=x.median() if len(x) else float('nan')
        r[f'{m}_p95']=x.quantile(.95) if len(x) else float('nan')
    rows.append(r)
res=pd.DataFrame(rows).sort_values(['state_bytes','mode'])
res.to_csv(out/'handoff_summary_by_state.csv',index=False)
# Control-adjusted service gap uses paired trial ids.
pivot=df.pivot_table(index=['state_bytes','trial'],columns='mode',values='longest_reply_gap_ms',aggfunc='first').reset_index()
if {'no_op','reconfig'}.issubset(pivot.columns):
    pivot['excess_reply_gap_ms']=pivot['reconfig']-pivot['no_op']
    pivot.to_csv(out/'handoff_control_adjusted_gaps.csv',index=False)
print(res.to_string(index=False))
