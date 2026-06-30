from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Literal

import numpy as np
import pandas as pd

from .controller import ExchangeAction, RiskAwareExchangeController
from .exact_inference import ExactConstrainedRiskPosterior
from .metrics import brier_score, top1_hit
from .protocol import Outcome, simulate_batch
from .types import AttackModel, NetworkContext, SimulationConfig

PolicyName = Literal["no_reconfig", "periodic_global_reshuffle", "random_local_exchange", "risk_triggered_random_partner", "risk_aware_exchange", "oracle_risk_aware_exchange"]


@dataclass
class ExperimentOutput:
    events: pd.DataFrame
    epoch_summary: pd.DataFrame
    policy_summary: pd.DataFrame


def _initial_membership(config: SimulationConfig, rng: np.random.Generator) -> np.ndarray:
    """Return validator-to-shard labels with equal shard sizes."""
    labels = np.repeat(np.arange(config.n_shards), config.shard_size)
    rng.shuffle(labels)
    return labels


def _make_malicious_identities(config: SimulationConfig, rng: np.random.Generator) -> np.ndarray:
    n_malicious = int(round(config.n_nodes * config.malicious_fraction))
    arr = np.zeros(config.n_nodes, dtype=bool)
    arr[rng.choice(config.n_nodes, size=n_malicious, replace=False)] = True
    return arr


def _equal_size_global_reshuffle(membership: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    labels = membership.copy()
    rng.shuffle(labels)
    return labels


def _execute_random_exchange(
    membership: np.ndarray, h: int, c: int, k: int, rng: np.random.Generator
) -> None:
    h_nodes = np.flatnonzero(membership == h)
    c_nodes = np.flatnonzero(membership == c)
    chosen_h = rng.choice(h_nodes, size=k, replace=False)
    chosen_c = rng.choice(c_nodes, size=k, replace=False)
    membership[chosen_h] = c
    membership[chosen_c] = h


def _contexts_for_epoch(
    config: SimulationConfig,
    epoch: int,
    context_mode: str,
    rng: np.random.Generator,
) -> list[NetworkContext]:
    base = NetworkContext()
    contexts = [base for _ in range(config.n_shards)]
    if context_mode == "normal":
        return contexts
    if context_mode == "localized_network_degradation":
        # A visible context covariate deliberately worsens one shard without attack.
        stressed = epoch % config.n_shards
        contexts[stressed] = NetworkContext(
            timeout_prob=0.15,
            quorum_outage_prob=0.40,
            max_view_changes=2,
            label="localized_network_degradation",
        )
        return contexts
    if context_mode == "global_network_degradation":
        return [
            NetworkContext(
                timeout_prob=0.10,
                quorum_outage_prob=0.02,
                max_view_changes=2,
                label="global_network_degradation",
            )
            for _ in range(config.n_shards)
        ]
    raise ValueError(f"unknown context_mode={context_mode}")


def _run_epoch_protocol(
    membership: np.ndarray,
    malicious_identity: np.ndarray,
    config: SimulationConfig,
    attack: AttackModel,
    contexts: list[NetworkContext],
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return N/R/S counts, true active loads, and true malicious loads."""
    counts = np.zeros((config.n_shards, 3), dtype=int)
    active_loads = np.zeros(config.n_shards, dtype=int)
    malicious_loads = np.zeros(config.n_shards, dtype=int)
    outcome_index = {Outcome.NORMAL: 0, Outcome.RECOVERED: 1, Outcome.STALLED: 2}

    active_nodes = malicious_identity & (rng.random(config.n_nodes) < attack.activation_prob)
    for s in range(config.n_shards):
        shard_nodes = np.flatnonzero(membership == s)
        active_loads[s] = int(active_nodes[shard_nodes].sum())
        malicious_loads[s] = int(malicious_identity[shard_nodes].sum())
        for _ in range(config.batches_per_epoch):
            trace = simulate_batch(
                active_blockers=active_loads[s],
                committee_size=config.shard_size,
                f=config.f,
                context=contexts[s],
                attack=attack,
                rng=rng,
            )
            counts[s, outcome_index[trace.outcome]] += 1
    return counts, active_loads, malicious_loads


def run_policy_experiment(
    config: SimulationConfig,
    policy: PolicyName,
    seed: int,
    attack: AttackModel | None = None,
    context_mode: str = "normal",
    likelihood_attack: AttackModel | None = None,
    likelihood_attacks: tuple[AttackModel, ...] | None = None,
) -> ExperimentOutput:
    # `attack` generates protocol traces; likelihood models define the offline
    # calibration table. Keeping them separable enables held-out attack-strategy
    # mismatch experiments and a Bayesian mixture over attack intensity.
    attack = attack or AttackModel()
    likelihood_attack = likelihood_attack or attack
    # v1.5 primary model: adversarial identities and their blocking behavior
    # persist across epochs unless membership changes.  The particle filter has
    # no latent activation-state transition, so intermittent activation would
    # require a different hidden Markov model and is intentionally rejected
    # rather than silently mis-modeled.
    if attack.activation_prob != 1.0:
        raise ValueError(
            "The v1.5 persistent-blocker model requires activation_prob=1.0; "
            "intermittent attackers need an explicit state-transition model."
        )
    rng = np.random.default_rng(seed)
    membership = _initial_membership(config, rng)
    malicious_identity = _make_malicious_identities(config, rng)

    # Exact one-epoch posterior under a declared network-wide active-load budget.
    # This is a threat-model parameter, not an identity oracle.
    global_active_budget = int(round(config.n_nodes * config.prior_active_fraction))
    controller = RiskAwareExchangeController(
        committee_size=config.shard_size,
        f=config.f,
        n_nodes=config.n_nodes,
        candidate_partners=config.candidate_partners,
        max_exchange_k=config.max_exchange_k,
        migration_penalty=config.migration_penalty,
        minimum_predicted_gain=config.minimum_predicted_gain,
        prediction_samples=config.prediction_samples,
        seed=int(rng.integers(0, 2**31 - 1)),
    )

    event_rows: list[dict] = []
    epoch_rows: list[dict] = []

    for epoch in range(config.epochs):
        contexts = _contexts_for_epoch(config, epoch, context_mode, rng)
        outcomes, active_loads, malicious_loads = _run_epoch_protocol(
            membership, malicious_identity, config, attack, contexts, rng
        )

        t0 = perf_counter()
        posterior = ExactConstrainedRiskPosterior(
            n_shards=config.n_shards,
            committee_size=config.shard_size,
            f=config.f,
            global_active_budget=global_active_budget,
            attack=likelihood_attack,
            calibration_batches=config.calibration_batches,
            seed=int(rng.integers(0, 2**31 - 1)),
            likelihood_attacks=likelihood_attacks,
        )
        snapshot = posterior.update(outcomes, contexts)
        action: ExchangeAction | None = None
        if policy in {"risk_aware_exchange", "risk_triggered_random_partner"}:
            action = controller.choose_action(posterior, snapshot)
            if policy == "risk_triggered_random_partner" and action is not None:
                # Same posterior trigger and same k budget as the proposed
                # controller, but select the partner shard blindly.
                choices = [s for s in range(config.n_shards) if s != action.hot_shard]
                random_partner = int(rng.choice(choices))
                action = ExchangeAction(
                    hot_shard=action.hot_shard,
                    cold_shard=random_partner,
                    k=action.k,
                    predicted_max_risk_before=action.predicted_max_risk_before,
                    predicted_max_risk_after=float("nan"),
                    utility=float("nan"),
                )
        elif policy == "oracle_risk_aware_exchange":
            action = controller.choose_oracle_action(active_loads)
        controller_ms = (perf_counter() - t0) * 1000.0

        moved_nodes = 0
        if policy in {"risk_aware_exchange", "risk_triggered_random_partner", "oracle_risk_aware_exchange"} and action is not None:
            _execute_random_exchange(membership, action.hot_shard, action.cold_shard, action.k, rng)
            posterior.propagate_random_exchange(action.hot_shard, action.cold_shard, action.k)
            moved_nodes = 2 * action.k
        elif policy == "random_local_exchange":
            h, c = rng.choice(config.n_shards, size=2, replace=False)
            k = int(rng.integers(1, config.max_exchange_k + 1))
            _execute_random_exchange(membership, int(h), int(c), k, rng)
            posterior.propagate_random_exchange(int(h), int(c), k)
            moved_nodes = 2 * k
        elif policy == "periodic_global_reshuffle" and (epoch + 1) % config.periodic_reshuffle_every == 0:
            membership = _equal_size_global_reshuffle(membership, rng)
            posterior.reset_after_global_random_reshuffle()
            moved_nodes = config.n_nodes

        true_failure = active_loads > config.f
        for s in range(config.n_shards):
            event_rows.append(
                {
                    "policy": policy,
                    "seed": seed,
                    "epoch": epoch,
                    "shard": s,
                    "normal": outcomes[s, 0],
                    "recovered": outcomes[s, 1],
                    "stalled": outcomes[s, 2],
                    "posterior_risk": snapshot.risk[s],
                    "posterior_mean_active": snapshot.mean_active_load[s],
                    "true_active_load": active_loads[s],
                    "true_malicious_load": malicious_loads[s],
                    "true_over_threshold": bool(true_failure[s]),
                    "context": contexts[s].label,
                }
            )

        epoch_rows.append(
            {
                "policy": policy,
                "seed": seed,
                "epoch": epoch,
                "any_true_threshold_failure": bool(true_failure.any()),
                "max_true_active_load": int(active_loads.max()),
                "max_posterior_risk": float(snapshot.risk.max()),
                "mean_stall_rate": float(outcomes[:, 2].sum() / outcomes.sum()),
                "mean_recovery_rate": float(outcomes[:, 1].sum() / outcomes.sum()),
                "brier": brier_score(snapshot.risk, true_failure),
                "top1_hit": top1_hit(snapshot.risk, active_loads),
                "moved_nodes": moved_nodes,
                "controller_ms": controller_ms,
                "action_h": None if action is None else action.hot_shard,
                "action_c": None if action is None else action.cold_shard,
                "action_k": None if action is None else action.k,
                "predicted_max_before": None if action is None else action.predicted_max_risk_before,
                "predicted_max_after": None if action is None else action.predicted_max_risk_after,
            }
        )

    events = pd.DataFrame(event_rows)
    epoch_summary = pd.DataFrame(epoch_rows)
    policy_summary = (
        epoch_summary.groupby(["policy", "seed"], as_index=False)
        .agg(
            any_failure_rate=("any_true_threshold_failure", "mean"),
            mean_max_active=("max_true_active_load", "mean"),
            mean_stall_rate=("mean_stall_rate", "mean"),
            mean_recovery_rate=("mean_recovery_rate", "mean"),
            mean_brier=("brier", "mean"),
            top1_hit_rate=("top1_hit", "mean"),
            mean_moved_nodes=("moved_nodes", "mean"),
            mean_controller_ms=("controller_ms", "mean"),
        )
    )
    return ExperimentOutput(events=events, epoch_summary=epoch_summary, policy_summary=policy_summary)


def run_discriminability_experiment(
    committee_size: int,
    f: int,
    context: NetworkContext,
    attack: AttackModel,
    batches_per_state: int,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    index = {Outcome.NORMAL: "normal_rate", Outcome.RECOVERED: "recovered_rate", Outcome.STALLED: "stalled_rate"}
    for a in range(committee_size + 1):
        counts = {value: 0 for value in index.values()}
        for _ in range(batches_per_state):
            trace = simulate_batch(a, committee_size, f, context, attack, rng)
            counts[index[trace.outcome]] += 1
        rows.append(
            {
                "active_blockers": a,
                **{k: v / batches_per_state for k, v in counts.items()},
                "degradation_rate": (counts["recovered_rate"] + counts["stalled_rate"]) / batches_per_state,
            }
        )
    return pd.DataFrame(rows)



def run_context_confounding_experiment(
    committee_size: int,
    f: int,
    prior_active_fraction: float,
    attack: AttackModel,
    batches: int,
    particles: int,
    calibration_batches: int,
    seed: int,
    n_shards: int = 9,
    global_active_budget: int | None = None,
) -> pd.DataFrame:
    """Exact-posterior context negative control with a valid global budget.

    A single target shard is embedded in a full network.  The controller is
    given the same configuration-time global active-load budget in all cases;
    only the target's visible context is toggled.  This avoids the invalid
    one-shard shortcut where a fixed global budget would force the target load.
    """
    if attack.activation_prob != 1.0:
        raise ValueError("context experiment requires persistent blockers")
    rng = np.random.default_rng(seed)
    normal = NetworkContext()
    degraded = NetworkContext(
        timeout_prob=0.15,
        quorum_outage_prob=0.40,
        max_view_changes=2,
        label="localized_network_degradation",
    )
    if global_active_budget is None:
        global_active_budget = int(round(n_shards * committee_size * prior_active_fraction))

    index = {Outcome.NORMAL: 0, Outcome.RECOVERED: 1, Outcome.STALLED: 2}

    def make_counts(target_active: int, target_context: NetworkContext) -> tuple[np.ndarray, list[NetworkContext]]:
        if not 0 <= target_active <= committee_size:
            raise ValueError("invalid target active load")
        counts = np.zeros((n_shards, 3), dtype=int)
        contexts = [target_context] + [normal for _ in range(n_shards - 1)]
        remaining = global_active_budget - target_active
        if remaining < 0 or remaining > (n_shards - 1) * committee_size:
            raise ValueError("infeasible target/global budget")
        other_loads = [remaining // (n_shards - 1)] * (n_shards - 1)
        for i in range(remaining % (n_shards - 1)):
            other_loads[i] += 1
        loads = [target_active] + other_loads
        for s, a in enumerate(loads):
            for _ in range(batches):
                trace = simulate_batch(a, committee_size, f, contexts[s], attack, rng)
                counts[s, index[trace.outcome]] += 1
        return counts, contexts

    def infer(counts: np.ndarray, contexts: list[NetworkContext], local_seed: int) -> tuple[float, float]:
        filt = ExactConstrainedRiskPosterior(
            n_shards=n_shards,
            committee_size=committee_size,
            f=f,
            global_active_budget=global_active_budget,
            attack=attack,
            calibration_batches=calibration_batches,
            seed=local_seed,
        )
        snapshot = filt.update(counts, contexts)
        return float(snapshot.risk[0]), float(snapshot.mean_active_load[0])

    normal_counts, normal_contexts = make_counts(0, normal)
    degraded_counts, degraded_contexts = make_counts(0, degraded)
    ignored_contexts = [normal] + [normal for _ in range(n_shards - 1)]
    attack_counts, attack_contexts = make_counts(f + 1, normal)

    conditions = [
        ("benign_normal", "normal", 0, normal_counts, normal_contexts, seed + 1),
        ("benign_localized_network", "degradation supplied", 0, degraded_counts, degraded_contexts, seed + 2),
        ("benign_localized_network", "degradation ignored (ablation)", 0, degraded_counts, ignored_contexts, seed + 3),
        ("active_withholding", "normal", f + 1, attack_counts, attack_contexts, seed + 4),
    ]
    rows = []
    for condition, model_context, active, counts, contexts, local_seed in conditions:
        risk, mean = infer(counts, contexts, local_seed)
        rows.append({
            "condition": condition,
            "model_context": model_context,
            "true_active_load": active,
            "normal": int(counts[0, 0]),
            "recovered": int(counts[0, 1]),
            "stalled": int(counts[0, 2]),
            "posterior_threshold_risk": risk,
            "posterior_mean_active": mean,
        })
    return pd.DataFrame(rows)

