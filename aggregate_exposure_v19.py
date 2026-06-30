from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path('/mnt/data')
chunks = [ROOT/f'v19_exposure_chunk{i}'/'exposure_by_seed.csv' for i in range(3)]
df = pd.concat([pd.read_csv(p) for p in chunks], ignore_index=True)
out = Path('/mnt/data/infocom_pbft_v19/results_v19'); out.mkdir(exist_ok=True)
df.to_csv(out/'exposure_by_seed.csv', index=False)
agg = (df.groupby(['batches_per_epoch','policy'], as_index=False)
       .agg(failure_epoch_fraction=('any_failure_rate','mean'),
            failure_std=('any_failure_rate','std'),
            brier=('mean_brier','mean'),
            top1_hit=('top1_hit_rate','mean'),
            moved_per_epoch=('mean_moved_nodes','mean'),
            controller_ms=('mean_controller_ms','mean'),
            n=('seed','count')))
agg.to_csv(out/'exposure_aggregate.csv', index=False)
# paired bootstrap of absolute reduction: no_reconfig - risk aware per batch setting.
rng=np.random.default_rng(20260630)
rows=[]
for b in sorted(df.batches_per_epoch.unique()):
    pivot=df[df.batches_per_epoch==b].pivot(index='seed',columns='policy',values='any_failure_rate').dropna()
    delta=(pivot['no_reconfig']-pivot['risk_aware_exchange']).to_numpy()
    boots=np.array([rng.choice(delta,size=len(delta),replace=True).mean() for _ in range(5000)])
    rows.append({'batches_per_epoch':b,'n':len(delta),'absolute_reduction':delta.mean(),'ci_low':np.quantile(boots,.025),'ci_high':np.quantile(boots,.975)})
pd.DataFrame(rows).to_csv(out/'exposure_paired_bootstrap.csv', index=False)
fig,ax=plt.subplots(figsize=(7.2,4.7))
for p,sub in agg.groupby('policy'):
    sub=sub.sort_values('batches_per_epoch')
    ax.plot(sub.batches_per_epoch,sub.failure_epoch_fraction,marker='o',label=p)
ax.set_xscale('log',base=3); ax.set_xticks([24,72,216]); ax.set_xticklabels(['24','72','216'])
ax.set_xlabel('Logical batches observed per epoch');ax.set_ylabel('Failure-epoch fraction');ax.set_title('Observation-exposure robustness')
ax.legend(frameon=False);fig.tight_layout();fig.savefig(out/'fig_exposure.png',dpi=220);plt.close(fig)
print(agg.to_string(index=False))
print(pd.DataFrame(rows).to_string(index=False))
