from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from pbft_progress_sim import AttackModel, NetworkContext, SimulationConfig
from pbft_progress_sim.simulation import run_context_confounding_experiment, run_discriminability_experiment, run_policy_experiment

# Discrete prior over persistent withholding-intensity regimes. The online
# filter infers the regime jointly with shard active loads rather than assuming
# a single known attacker aggressiveness.
ROBUST_ATTACK_GRID = (
    AttackModel(primary_withhold_prob=0.55, backup_withhold_prob=0.45),
    AttackModel(primary_withhold_prob=0.70, backup_withhold_prob=0.60),
    AttackModel(primary_withhold_prob=0.90, backup_withhold_prob=0.75),
)


def save_discriminability(config: SimulationConfig, out: Path) -> None:
    df = run_discriminability_experiment(
        committee_size=config.shard_size,
        f=config.f,
        context=NetworkContext(),
        attack=AttackModel(),
        batches_per_state=5000,
        seed=11,
    )
    df.to_csv(out / "discriminability.csv", index=False)
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    ax.plot(df["active_blockers"], df["normal_rate"], marker="o", label="Normal")
    ax.plot(df["active_blockers"], df["recovered_rate"], marker="o", label="Recovered")
    ax.plot(df["active_blockers"], df["stalled_rate"], marker="o", label="Stalled")
    ax.axvline(config.f, linestyle="--", label="PBFT f")
    ax.set_xlabel("True active blocking load a")
    ax.set_ylabel("Batch outcome probability")
    ax.set_title("Protocol-generated N/R/S likelihood")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "fig_discriminability.png", dpi=200)
    plt.close(fig)



def save_context_confounding(config: SimulationConfig, out: Path) -> None:
    df = run_context_confounding_experiment(
        committee_size=config.shard_size,
        f=config.f,
        prior_active_fraction=config.prior_active_fraction,
        attack=AttackModel(),
        batches=60,
        particles=config.particles,
        calibration_batches=config.calibration_batches,
        seed=91,
        n_shards=config.n_shards,
        global_active_budget=int(round(config.n_nodes * config.prior_active_fraction)),
    )
    df.to_csv(out / "context_confounding.csv", index=False)
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    ax.bar(df.index.astype(str), df["posterior_threshold_risk"])
    ax.set_xticks(df.index, ["normal\\nbenign", "degraded\\ncontext-aware", "degraded\\ncontext-ignored", "active\\nwithholding"])
    ax.set_ylabel("Posterior P(A > f | N/R/S, context)")
    ax.set_title("Context negative control")
    fig.tight_layout()
    fig.savefig(out / "fig_context_confounding.png", dpi=200)
    plt.close(fig)

def save_policy_benchmark(config: SimulationConfig, out: Path, seeds: int, seed_start: int) -> None:
    policies = [
        "no_reconfig",
        "periodic_global_reshuffle",
        "random_local_exchange",
        "risk_triggered_random_partner",
        "risk_aware_exchange",
    ]
    summaries = []
    epochs = []
    events = []
    for policy in policies:
        for seed in range(seeds):
            result = run_policy_experiment(config, policy=policy, seed=seed_start + seed, likelihood_attacks=ROBUST_ATTACK_GRID)
            summaries.append(result.policy_summary)
            epochs.append(result.epoch_summary)
            events.append(result.events)
    summary = pd.concat(summaries, ignore_index=True)
    epoch_df = pd.concat(epochs, ignore_index=True)
    event_df = pd.concat(events, ignore_index=True)
    summary.to_csv(out / "policy_summary_by_seed.csv", index=False)
    epoch_df.to_csv(out / "epoch_metrics.csv", index=False)
    event_df.to_csv(out / "shard_epoch_events.csv", index=False)

    aggregate = (
        summary.groupby("policy", as_index=False)
        .agg(
            any_failure_rate_mean=("any_failure_rate", "mean"),
            any_failure_rate_std=("any_failure_rate", "std"),
            top1_hit_rate_mean=("top1_hit_rate", "mean"),
            mean_brier_mean=("mean_brier", "mean"),
            mean_stall_rate_mean=("mean_stall_rate", "mean"),
            mean_moved_nodes_mean=("mean_moved_nodes", "mean"),
            mean_controller_ms_mean=("mean_controller_ms", "mean"),
        )
        .sort_values("any_failure_rate_mean")
    )
    aggregate.to_csv(out / "policy_aggregate.csv", index=False)

    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.bar(aggregate["policy"], aggregate["any_failure_rate_mean"], yerr=aggregate["any_failure_rate_std"])
    ax.set_ylabel("Epochs with >=1 true over-threshold shard")
    ax.set_title("Policy comparison: true shard-threshold failure")
    ax.tick_params(axis="x", rotation=18)
    fig.tight_layout()
    fig.savefig(out / "fig_policy_failure_rate.png", dpi=200)
    plt.close(fig)

    risk_aware = epoch_df[epoch_df["policy"] == "risk_aware_exchange"]
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    for seed, sub in risk_aware.groupby("seed"):
        ax.plot(sub["epoch"], sub["max_posterior_risk"], alpha=0.35)
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Max posterior over-threshold risk")
    ax.set_title("Risk-aware controller: posterior risk trajectories")
    fig.tight_layout()
    fig.savefig(out / "fig_risk_trajectories.png", dpi=200)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Small run for fast smoke testing")
    parser.add_argument("--seeds", type=int, default=12)
    parser.add_argument("--seed-start", type=int, default=1000)
    parser.add_argument("--out", type=Path, default=Path("results"))
    args = parser.parse_args()

    config = SimulationConfig()
    if args.quick:
        config = SimulationConfig(
            n_nodes=90,
            n_shards=9,
            malicious_fraction=0.28,
            epochs=10,
            batches_per_epoch=18,
            prior_active_fraction=0.28,
            particles=800,
            calibration_batches=450,
            prediction_samples=350,
            candidate_partners=3,
            max_exchange_k=3,
        )
        args.seeds = min(args.seeds, 3)
    args.out.mkdir(parents=True, exist_ok=True)
    save_discriminability(config, args.out)
    save_context_confounding(config, args.out)
    save_policy_benchmark(config, args.out, args.seeds, args.seed_start)
    print(f"Wrote results to {args.out.resolve()}")


if __name__ == "__main__":
    main()
