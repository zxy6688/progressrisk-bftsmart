from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pbft_progress_sim import AttackModel, NetworkContext, SimulationConfig
from pbft_progress_sim.inference import ParticleRiskFilter
from pbft_progress_sim.metrics import expected_calibration_error
from pbft_progress_sim.protocol import Outcome, simulate_batch
from pbft_progress_sim.simulation import run_policy_experiment

ROBUST_ATTACK_GRID = (
    AttackModel(primary_withhold_prob=0.55, backup_withhold_prob=0.45),
    AttackModel(primary_withhold_prob=0.70, backup_withhold_prob=0.60),
    AttackModel(primary_withhold_prob=0.90, backup_withhold_prob=0.75),
)


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    return (
        summary.groupby("policy", as_index=False)
        .agg(
            any_failure_rate_mean=("any_failure_rate", "mean"),
            any_failure_rate_std=("any_failure_rate", "std"),
            top1_hit_rate_mean=("top1_hit_rate", "mean"),
            mean_brier_mean=("mean_brier", "mean"),
            mean_moved_nodes_mean=("mean_moved_nodes", "mean"),
            mean_controller_ms_mean=("mean_controller_ms", "mean"),
        )
        .sort_values("any_failure_rate_mean")
    )


def run_attack_mismatch(config: SimulationConfig, seeds: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Held-out attack test with point-model ablation and proposed regime model."""
    point_attack = AttackModel(primary_withhold_prob=0.90, backup_withhold_prob=0.75)
    # Deliberately not one of the grid points.
    heldout_attack = AttackModel(primary_withhold_prob=0.65, backup_withhold_prob=0.60)
    policies = ["no_reconfig", "risk_triggered_random_partner", "risk_aware_exchange"]
    rows = []
    for model_name, grid in [("point_likelihood_ablation", None), ("hierarchical_regime_model", ROBUST_ATTACK_GRID)]:
        for policy in policies:
            for seed in range(seeds):
                result = run_policy_experiment(
                    config,
                    policy=policy,  # type: ignore[arg-type]
                    seed=20_000 + seed,
                    attack=heldout_attack,
                    likelihood_attack=point_attack,
                    likelihood_attacks=grid,
                )
                row = result.policy_summary.copy()
                row["inference_model"] = model_name
                rows.append(row)
    per_seed = pd.concat(rows, ignore_index=True)
    aggregate = (
        per_seed.groupby(["inference_model", "policy"], as_index=False)
        .agg(
            any_failure_rate_mean=("any_failure_rate", "mean"),
            any_failure_rate_std=("any_failure_rate", "std"),
            top1_hit_rate_mean=("top1_hit_rate", "mean"),
            mean_brier_mean=("mean_brier", "mean"),
            mean_moved_nodes_mean=("mean_moved_nodes", "mean"),
            mean_controller_ms_mean=("mean_controller_ms", "mean"),
        )
        .sort_values(["inference_model", "any_failure_rate_mean"])
    )
    return per_seed, aggregate


def _generate_counts(
    a: int,
    committee_size: int,
    f: int,
    batches: int,
    context: NetworkContext,
    attack: AttackModel,
    rng: np.random.Generator,
) -> np.ndarray:
    counts = np.zeros((1, 3), dtype=int)
    index = {Outcome.NORMAL: 0, Outcome.RECOVERED: 1, Outcome.STALLED: 2}
    for _ in range(batches):
        out = simulate_batch(a, committee_size, f, context, attack, rng).outcome
        counts[0, index[out]] += 1
    return counts


def _infer_risk(
    counts: np.ndarray,
    config: SimulationConfig,
    context: NetworkContext,
    attack: AttackModel,
    seed: int,
    likelihood_attacks: tuple[AttackModel, ...] | None = None,
) -> float:
    filt = ParticleRiskFilter(
        n_shards=1,
        committee_size=config.shard_size,
        f=config.f,
        prior_active_fraction=config.prior_active_fraction,
        particles=config.particles,
        attack=attack,
        calibration_batches=config.calibration_batches,
        seed=seed,
        likelihood_attacks=likelihood_attacks,
    )
    return float(filt.update(counts, [context]).risk[0])


def run_context_replication(config: SimulationConfig, trials: int) -> pd.DataFrame:
    """Replicate the negative control instead of reporting one lucky trace."""
    attack = AttackModel()
    normal = NetworkContext()
    degraded = NetworkContext(
        timeout_prob=0.15,
        quorum_outage_prob=0.40,
        max_view_changes=2,
        label="localized_network_degradation",
    )
    rows: list[dict] = []
    for i in range(trials):
        rng = np.random.default_rng(30_000 + i)
        benign_counts = _generate_counts(
            0, config.shard_size, config.f, 60, degraded, attack, rng
        )
        heldout_counts = _generate_counts(
            config.f + 1, config.shard_size, config.f, 60, normal, attack, rng
        )
        rows.extend(
            [
                {
                    "condition": "benign_degraded_context_supplied",
                    "trial": i,
                    "posterior_risk": _infer_risk(
                        benign_counts, config, degraded, attack, 40_000 + i, ROBUST_ATTACK_GRID
                    ),
                },
                {
                    "condition": "benign_degraded_context_ignored",
                    "trial": i,
                    "posterior_risk": _infer_risk(
                        benign_counts, config, normal, attack, 50_000 + i, ROBUST_ATTACK_GRID
                    ),
                },
                {
                    "condition": "active_withholding_normal_context",
                    "trial": i,
                    "posterior_risk": _infer_risk(
                        heldout_counts, config, normal, attack, 60_000 + i, ROBUST_ATTACK_GRID
                    ),
                },
            ]
        )
    return pd.DataFrame(rows)


def calibration_table(events: pd.DataFrame, bins: int = 6) -> tuple[pd.DataFrame, float]:
    x = events[["posterior_risk", "true_over_threshold"]].copy()
    x["bin"] = pd.cut(
        x["posterior_risk"],
        bins=np.linspace(0.0, 1.0, bins + 1),
        include_lowest=True,
    )
    table = (
        x.groupby("bin", observed=False)
        .agg(
            n=("posterior_risk", "size"),
            mean_predicted_risk=("posterior_risk", "mean"),
            observed_frequency=("true_over_threshold", "mean"),
        )
        .reset_index()
    )
    ece = expected_calibration_error(
        x["posterior_risk"].to_numpy(), x["true_over_threshold"].to_numpy(), bins=bins
    )
    return table, ece


def run_sensitivity(base: SimulationConfig, seeds: int) -> pd.DataFrame:
    rows = []
    for frac in [0.20, 0.24, 0.28, 0.32]:
        config = SimulationConfig(
            n_nodes=base.n_nodes,
            n_shards=base.n_shards,
            malicious_fraction=frac,
            prior_active_fraction=frac,
            epochs=base.epochs,
            batches_per_epoch=base.batches_per_epoch,
            particles=base.particles,
            calibration_batches=base.calibration_batches,
            prediction_samples=base.prediction_samples,
            candidate_partners=base.candidate_partners,
            max_exchange_k=base.max_exchange_k,
            migration_penalty=base.migration_penalty,
            minimum_predicted_gain=base.minimum_predicted_gain,
            periodic_reshuffle_every=base.periodic_reshuffle_every,
        )
        for policy in ["no_reconfig", "risk_aware_exchange"]:
            for seed in range(seeds):
                result = run_policy_experiment(
                    config, policy=policy, seed=70_000 + int(frac * 1000) + seed,  # type: ignore[arg-type]
                    likelihood_attacks=ROBUST_ATTACK_GRID,
                )
                row = result.policy_summary.copy()
                row["malicious_fraction"] = frac
                rows.append(row)
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=12)
    parser.add_argument("--context-trials", type=int, default=40)
    parser.add_argument("--sensitivity-seeds", type=int, default=6)
    parser.add_argument("--out", type=Path, default=Path("validation"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    config = SimulationConfig()

    mismatch_per_seed, mismatch_aggregate = run_attack_mismatch(config, args.seeds)
    mismatch_per_seed.to_csv(args.out / "attack_mismatch_by_seed.csv", index=False)
    mismatch_aggregate.to_csv(args.out / "attack_mismatch_aggregate.csv", index=False)

    # Calibration is evaluated with no intervention so outcomes are not altered
    # by a prior controller decision.
    calibration_events = []
    for seed in range(args.seeds):
        calibration_events.append(
            run_policy_experiment(config, "no_reconfig", 80_000 + seed, likelihood_attacks=ROBUST_ATTACK_GRID).events
        )
    events = pd.concat(calibration_events, ignore_index=True)
    cal_table, ece = calibration_table(events)
    cal_table["ece"] = ece
    cal_table.to_csv(args.out / "calibration_curve.csv", index=False)

    fig, ax = plt.subplots(figsize=(5.8, 5.2))
    valid = cal_table[cal_table["n"] > 0]
    ax.plot([0, 1], [0, 1], linestyle="--", label="ideal")
    ax.plot(
        valid["mean_predicted_risk"],
        valid["observed_frequency"],
        marker="o",
        label=f"posterior (ECE={ece:.3f})",
    )
    ax.set_xlabel("Mean posterior threshold risk")
    ax.set_ylabel("Observed over-threshold frequency")
    ax.set_title("Calibration under matched attack model")
    ax.legend()
    fig.tight_layout()
    fig.savefig(args.out / "fig_calibration.png", dpi=200)
    plt.close(fig)

    context = run_context_replication(config, args.context_trials)
    context.to_csv(args.out / "context_replications.csv", index=False)
    context_aggregate = (
        context.groupby("condition", as_index=False)
        .agg(
            posterior_risk_mean=("posterior_risk", "mean"),
            posterior_risk_std=("posterior_risk", "std"),
            false_alarm_rate_50=("posterior_risk", lambda x: float((x >= 0.5).mean())),
        )
    )
    context_aggregate.to_csv(args.out / "context_replication_aggregate.csv", index=False)

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.bar(
        context_aggregate["condition"],
        context_aggregate["posterior_risk_mean"],
        yerr=context_aggregate["posterior_risk_std"],
    )
    ax.set_ylabel("Posterior P(A > f | N/R/S, context)")
    ax.set_title("Replicated context negative control")
    ax.tick_params(axis="x", rotation=18)
    fig.tight_layout()
    fig.savefig(args.out / "fig_context_replication.png", dpi=200)
    plt.close(fig)

    sensitivity = run_sensitivity(config, args.sensitivity_seeds)
    sensitivity.to_csv(args.out / "sensitivity_by_seed.csv", index=False)
    sensitivity_agg = (
        sensitivity.groupby(["malicious_fraction", "policy"], as_index=False)
        .agg(
            any_failure_rate_mean=("any_failure_rate", "mean"),
            any_failure_rate_std=("any_failure_rate", "std"),
            mean_moved_nodes_mean=("mean_moved_nodes", "mean"),
        )
    )
    sensitivity_agg.to_csv(args.out / "sensitivity_aggregate.csv", index=False)

    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    for policy, sub in sensitivity_agg.groupby("policy"):
        ax.plot(
            sub["malicious_fraction"],
            sub["any_failure_rate_mean"],
            marker="o",
            label=policy,
        )
    ax.set_xlabel("Global malicious fraction")
    ax.set_ylabel("Epochs with >=1 true over-threshold shard")
    ax.set_title("Sensitivity to global adversarial fraction")
    ax.legend()
    fig.tight_layout()
    fig.savefig(args.out / "fig_sensitivity.png", dpi=200)
    plt.close(fig)

    print(f"Wrote validation results to {args.out.resolve()}")


if __name__ == "__main__":
    main()
