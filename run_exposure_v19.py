from __future__ import annotations

"""Observation-exposure robustness for frozen ProgressRisk v1.8 semantics.

This suite does not tune controller parameters.  It uses the held-out attack
intensity from v1.8 and the already frozen hierarchical likelihood grid, then
varies only the number of real logical batches observed per epoch.  It tests
whether N/R/S remains useful with sparse evidence, not whether a larger
workload improves throughput.
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from pbft_progress_sim import AttackModel, SimulationConfig
from pbft_progress_sim.simulation import run_policy_experiment

LIKELIHOOD_GRID = (
    AttackModel(primary_withhold_prob=0.55, backup_withhold_prob=0.45),
    AttackModel(primary_withhold_prob=0.70, backup_withhold_prob=0.60),
    AttackModel(primary_withhold_prob=0.90, backup_withhold_prob=0.75),
)
HELDOUT_ATTACK = AttackModel(primary_withhold_prob=0.65, backup_withhold_prob=0.60)


def cfg(batches: int) -> SimulationConfig:
    return SimulationConfig(
        n_nodes=198,
        n_shards=9,
        malicious_fraction=0.24,
        epochs=24,
        batches_per_epoch=batches,
        prior_active_fraction=0.24,
        calibration_batches=1800,
        prediction_samples=400,
        candidate_partners=8,
        max_exchange_k=3,
        migration_penalty=0.03,
        minimum_predicted_gain=0.005,
        periodic_reshuffle_every=4,
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--seed-start', type=int, required=True)
    p.add_argument('--seeds', type=int, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    rows = []
    for batches in (24, 72, 216):
        for policy in ('no_reconfig', 'risk_aware_exchange'):
            for off in range(a.seeds):
                seed = a.seed_start + off
                out = run_policy_experiment(
                    cfg(batches), policy, seed=seed,
                    attack=HELDOUT_ATTACK,
                    likelihood_attacks=LIKELIHOOD_GRID,
                )
                r = out.policy_summary.iloc[0].to_dict()
                r.update({'seed': seed, 'batches_per_epoch': batches, 'policy': policy})
                rows.append(r)

    raw = pd.DataFrame(rows)
    raw.to_csv(a.out / 'exposure_by_seed.csv', index=False)
    agg = (raw.groupby(['batches_per_epoch','policy'], as_index=False)
           .agg(failure_epoch_fraction=('any_failure_rate','mean'),
                failure_std=('any_failure_rate','std'),
                brier=('mean_brier','mean'),
                top1_hit=('top1_hit_rate','mean'),
                moved_per_epoch=('mean_moved_nodes','mean'),
                controller_ms=('mean_controller_ms','mean'),
                n=('seed','count')))
    agg.to_csv(a.out / 'exposure_aggregate.csv', index=False)
    fig, ax = plt.subplots(figsize=(7.2,4.7))
    for policy, sub in agg.groupby('policy'):
        sub = sub.sort_values('batches_per_epoch')
        ax.plot(sub['batches_per_epoch'], sub['failure_epoch_fraction'], marker='o', label=policy)
    ax.set_xscale('log', base=3)
    ax.set_xticks([24,72,216])
    ax.set_xticklabels(['24','72','216'])
    ax.set_xlabel('Logical batches observed per epoch')
    ax.set_ylabel('Failure-epoch fraction')
    ax.set_title('Observation-exposure robustness (held-out attack intensity)')
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(a.out / 'fig_exposure.png', dpi=220)
    print(a.out.resolve())

if __name__ == '__main__':
    main()
