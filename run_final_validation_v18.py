from __future__ import annotations

"""Frozen v1.8 validation suite.

This suite does not alter the ProgressRisk observation, posterior, or action
semantics.  It only validates a preselected controller configuration on seeds
that were not used in the budget-development sweep.

Development decision (frozen before running this file): max_exchange_k=3.
Reason: on paired development seeds it is the migration-efficiency knee:
roughly the same failure reduction as larger k but far fewer moved validators.
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from pbft_progress_sim import AttackModel, SimulationConfig
from pbft_progress_sim.simulation import run_policy_experiment

ATTACK_GRID = (
    AttackModel(primary_withhold_prob=0.55, backup_withhold_prob=0.45),
    AttackModel(primary_withhold_prob=0.70, backup_withhold_prob=0.60),
    AttackModel(primary_withhold_prob=0.90, backup_withhold_prob=0.75),
)
POLICIES = (
    "no_reconfig",
    "periodic_global_reshuffle",
    "random_local_exchange",
    "risk_triggered_random_partner",
    "risk_aware_exchange",
)


def cfg_for(shards: int = 9) -> SimulationConfig:
    # Committee size remains 22 = 3*7+1 in every scale setting.
    return SimulationConfig(
        n_nodes=22 * shards,
        n_shards=shards,
        malicious_fraction=0.24,
        epochs=24,
        batches_per_epoch=72,
        prior_active_fraction=0.24,
        particles=3500,
        calibration_batches=1800,
        prediction_samples=400,
        candidate_partners=min(8, shards - 1),
        max_exchange_k=3,
        migration_penalty=0.03,
        minimum_predicted_gain=0.005,
        periodic_reshuffle_every=4,
    )


def summarize(rows: list[dict], keys: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    return (
        df.groupby(keys, as_index=False)
        .agg(
            any_failure_rate_mean=("any_failure_rate", "mean"),
            any_failure_rate_std=("any_failure_rate", "std"),
            overthreshold_shard_epoch_mean=("overthreshold_shard_epoch", "mean"),
            overthreshold_shard_epoch_std=("overthreshold_shard_epoch", "std"),
            top1_hit_rate_mean=("top1_hit_rate", "mean"),
            mean_brier_mean=("mean_brier", "mean"),
            mean_moved_nodes_mean=("mean_moved_nodes", "mean"),
            mean_controller_ms_mean=("mean_controller_ms", "mean"),
            n=("seed", "count"),
        )
        .sort_values(keys)
    )


def row_from(out, *, seed: int, **meta: object) -> dict:
    row = out.policy_summary.iloc[0].to_dict()
    ev = out.events
    row["overthreshold_shard_epoch"] = float((ev["true_active_load"] > 7).mean())
    row["seed"] = seed
    row.update(meta)
    return row


def plot_policy(agg: pd.DataFrame, path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    ax.bar(agg["policy"], agg["any_failure_rate_mean"], yerr=agg["any_failure_rate_std"])
    ax.set_title(title)
    ax.set_ylabel("Epochs with ≥1 true over-threshold shard")
    ax.tick_params(axis="x", rotation=18)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def plot_scale(agg: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.7))
    for policy, sub in agg.groupby("policy"):
        sub = sub.sort_values("n_shards")
        ax.plot(sub["n_shards"], sub["overthreshold_shard_epoch_mean"], marker="o", label=policy)
    ax.set_xlabel("Number of shards (committee size fixed at 22)")
    ax.set_ylabel("True over-threshold shard-epoch fraction")
    ax.set_title("Scale validation")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def run_heldout(seed_start: int, seeds: int, out: Path) -> None:
    cfg = cfg_for(9)
    rows: list[dict] = []
    for policy in POLICIES:
        for off in range(seeds):
            seed = seed_start + off
            result = run_policy_experiment(cfg, policy, seed=seed, likelihood_attacks=ATTACK_GRID)
            rows.append(row_from(result, seed=seed, policy=policy, suite="heldout"))
    raw = pd.DataFrame(rows)
    raw.to_csv(out / "heldout_by_seed.csv", index=False)
    agg = summarize(rows, ["policy"])
    agg.to_csv(out / "heldout_aggregate.csv", index=False)
    plot_policy(agg, out / "fig_heldout_policy.png", "Held-out policy validation (k ≤ 3)")


def run_scale(seed_start: int, seeds: int, out: Path) -> None:
    rows: list[dict] = []
    # 5, 9, and 18 shards: same 22-node PBFT committee and same risk semantics.
    for shards in (5, 9, 18):
        cfg = cfg_for(shards)
        for policy in ("no_reconfig", "risk_aware_exchange"):
            for off in range(seeds):
                seed = seed_start + 10_000 * shards + off
                result = run_policy_experiment(cfg, policy, seed=seed, likelihood_attacks=ATTACK_GRID)
                rows.append(row_from(result, seed=seed, n_shards=shards, n_nodes=cfg.n_nodes, policy=policy, suite="scale"))
    raw = pd.DataFrame(rows)
    raw.to_csv(out / "scale_by_seed.csv", index=False)
    agg = summarize(rows, ["n_shards", "n_nodes", "policy"])
    agg.to_csv(out / "scale_aggregate.csv", index=False)
    plot_scale(agg, out / "fig_scale.png")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--suite", choices=("heldout", "scale"), required=True)
    p.add_argument("--seed-start", type=int, required=True)
    p.add_argument("--seeds", type=int, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.suite == "heldout":
        run_heldout(a.seed_start, a.seeds, a.out)
    else:
        run_scale(a.seed_start, a.seeds, a.out)
    print(a.out.resolve())


if __name__ == "__main__":
    main()
