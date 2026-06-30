from __future__ import annotations

"""Predeclared robustness suite for ProgressRisk v1.7.

All comparisons use paired seeds and the v1.6 exact epoch-reset posterior.
The script intentionally separates result chunks so long replications can be
merged without mixing configs or silently changing random seeds.
"""

import argparse
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import pandas as pd

from pbft_progress_sim import AttackModel, SimulationConfig
from pbft_progress_sim.simulation import run_policy_experiment

ROBUST_ATTACK_GRID = (
    AttackModel(primary_withhold_prob=0.55, backup_withhold_prob=0.45),
    AttackModel(primary_withhold_prob=0.70, backup_withhold_prob=0.60),
    AttackModel(primary_withhold_prob=0.90, backup_withhold_prob=0.75),
)


def config_like(base: SimulationConfig, **kw: object) -> SimulationConfig:
    d = {
        "n_nodes": base.n_nodes,
        "n_shards": base.n_shards,
        "malicious_fraction": base.malicious_fraction,
        "epochs": base.epochs,
        "batches_per_epoch": base.batches_per_epoch,
        "prior_active_fraction": base.prior_active_fraction,
        "particles": base.particles,
        "calibration_batches": base.calibration_batches,
        "prediction_samples": base.prediction_samples,
        "candidate_partners": base.candidate_partners,
        "max_exchange_k": base.max_exchange_k,
        "migration_penalty": base.migration_penalty,
        "minimum_predicted_gain": base.minimum_predicted_gain,
        "periodic_reshuffle_every": base.periodic_reshuffle_every,
    }
    d.update(kw)
    return SimulationConfig(**d)


def result_row(result, **meta: object) -> dict:
    row = result.policy_summary.iloc[0].to_dict()
    row.update(meta)
    return row


def aggregate(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    return (
        df.groupby(keys, as_index=False)
        .agg(
            any_failure_rate_mean=("any_failure_rate", "mean"),
            any_failure_rate_std=("any_failure_rate", "std"),
            top1_hit_rate_mean=("top1_hit_rate", "mean"),
            mean_brier_mean=("mean_brier", "mean"),
            mean_moved_nodes_mean=("mean_moved_nodes", "mean"),
            mean_controller_ms_mean=("mean_controller_ms", "mean"),
            n=("seed", "count"),
        )
        .sort_values(keys)
    )


def run_sensitivity(base: SimulationConfig, seeds: Iterable[int]) -> pd.DataFrame:
    rows = []
    for frac in (0.20, 0.24, 0.28, 0.32):
        cfg = config_like(base, malicious_fraction=frac, prior_active_fraction=frac)
        for policy in ("no_reconfig", "risk_aware_exchange"):
            for seed in seeds:
                out = run_policy_experiment(
                    cfg, policy, seed=70_000 + int(frac * 1_000) + seed,
                    likelihood_attacks=ROBUST_ATTACK_GRID,
                )
                rows.append(result_row(out, malicious_fraction=frac))
    return pd.DataFrame(rows)


def run_budget(base: SimulationConfig, seeds: Iterable[int]) -> pd.DataFrame:
    rows = []
    for kmax in (1, 3, 6, 9):
        cfg = config_like(base, max_exchange_k=kmax)
        for seed in seeds:
            out = run_policy_experiment(
                cfg, "risk_aware_exchange", seed=91_000 + seed,
                likelihood_attacks=ROBUST_ATTACK_GRID,
            )
            rows.append(result_row(out, max_exchange_k=kmax))
    return pd.DataFrame(rows)


def run_budget_misspec(base: SimulationConfig, seeds: Iterable[int]) -> pd.DataFrame:
    rows = []
    # True persistent active fraction stays 0.24; only controller budget changes.
    for assumed in (0.16, 0.20, 0.24, 0.28, 0.32):
        cfg = config_like(base, prior_active_fraction=assumed)
        for seed in seeds:
            out = run_policy_experiment(
                cfg, "risk_aware_exchange", seed=96_000 + seed,
                likelihood_attacks=ROBUST_ATTACK_GRID,
            )
            rows.append(result_row(out, assumed_active_fraction=assumed))
    return pd.DataFrame(rows)


def run_attack_mismatch(base: SimulationConfig, seeds: Iterable[int]) -> pd.DataFrame:
    rows = []
    heldout = AttackModel(primary_withhold_prob=0.65, backup_withhold_prob=0.60)
    point = AttackModel(primary_withhold_prob=0.90, backup_withhold_prob=0.75)
    for model_name, grid in (
        ("point_likelihood_ablation", None),
        ("hierarchical_regime_model", ROBUST_ATTACK_GRID),
    ):
        for policy in ("no_reconfig", "risk_triggered_random_partner", "risk_aware_exchange"):
            for seed in seeds:
                out = run_policy_experiment(
                    base, policy, seed=20_000 + seed, attack=heldout,
                    likelihood_attack=point, likelihood_attacks=grid,
                )
                rows.append(result_row(out, inference_model=model_name))
    return pd.DataFrame(rows)


def plot_lines(df: pd.DataFrame, x: str, hue: str | None, path: Path, title: str, xlabel: str) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.7))
    if hue is None:
        sub = df.sort_values(x)
        ax.plot(sub[x], sub["any_failure_rate_mean"], marker="o")
    else:
        for label, sub in df.groupby(hue):
            sub = sub.sort_values(x)
            ax.plot(sub[x], sub["any_failure_rate_mean"], marker="o", label=str(label))
        ax.legend(frameon=False)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Failure-epoch fraction")
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--suite", choices=("sensitivity", "budget", "prior", "attack"), required=True)
    p.add_argument("--seed-start", type=int, default=0)
    p.add_argument("--seeds", type=int, default=4)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    base = SimulationConfig()

    if args.suite == "sensitivity":
        raw = run_sensitivity(base, seeds)
        group = ["malicious_fraction", "policy"]
        plot_x, hue, title, xlabel = "malicious_fraction", "policy", "Sensitivity to persistent active fraction", "True persistent active fraction"
    elif args.suite == "budget":
        raw = run_budget(base, seeds)
        group = ["max_exchange_k"]
        plot_x, hue, title, xlabel = "max_exchange_k", None, "Migration-budget sensitivity", "Maximum exchanged validators per shard (k)"
    elif args.suite == "prior":
        raw = run_budget_misspec(base, seeds)
        group = ["assumed_active_fraction"]
        plot_x, hue, title, xlabel = "assumed_active_fraction", None, "Threat-budget misspecification", "Controller-assumed active fraction"
    else:
        raw = run_attack_mismatch(base, seeds)
        group = ["inference_model", "policy"]
        plot_x, hue, title, xlabel = "inference_model", "policy", "Held-out attack-intensity mismatch", "Inference model"

    raw.to_csv(args.out / f"{args.suite}_by_seed.csv", index=False)
    agg = aggregate(raw, group)
    agg.to_csv(args.out / f"{args.suite}_aggregate.csv", index=False)
    plot_lines(agg, plot_x, hue, args.out / f"fig_{args.suite}.png", title, xlabel)
    print(args.out.resolve())


if __name__ == "__main__":
    main()
