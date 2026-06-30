from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AttackModel:
    """Declared active-withholding threat model.

    An active Byzantine validator can attack in either role. If selected as a
    primary, it may withhold PRE-PREPARE. If it participates in a prepare/commit
    quorum, it may withhold its timely consensus vote. These are probabilities
    of the attack strategy, not inferred facts about individual validators.
    """

    primary_withhold_prob: float = 0.90
    backup_withhold_prob: float = 0.75
    activation_prob: float = 1.00


@dataclass(frozen=True)
class NetworkContext:
    """Observable benign context supplied to the controller.

    timeout_prob is the probability that a view misses its proposal deadline for
    benign reasons. quorum_outage_prob is the per-honest-replica probability of
    missing the prepare/commit deadline in that view. Both are explicit
    likelihood inputs; neither is silently treated as Byzantine evidence.
    """

    timeout_prob: float = 0.015
    quorum_outage_prob: float = 0.003
    max_view_changes: int = 2
    label: str = "normal"

    def cache_key(self) -> tuple[float, float, int, str]:
        return (
            round(self.timeout_prob, 6),
            round(self.quorum_outage_prob, 6),
            self.max_view_changes,
            self.label,
        )


@dataclass(frozen=True)
class SimulationConfig:
    n_nodes: int = 198
    n_shards: int = 9
    # Nominal regime: below the global 1/3 BFT bound but close enough for
    # local concentration to be nontrivial. Stress values are swept separately.
    malicious_fraction: float = 0.24
    epochs: int = 24
    batches_per_epoch: int = 72
    prior_active_fraction: float = 0.24
    particles: int = 3500
    calibration_batches: int = 1800
    prediction_samples: int = 400
    candidate_partners: int = 8
    max_exchange_k: int = 6
    migration_penalty: float = 0.03
    minimum_predicted_gain: float = 0.005
    periodic_reshuffle_every: int = 4

    @property
    def shard_size(self) -> int:
        if self.n_nodes % self.n_shards:
            raise ValueError("n_nodes must be divisible by n_shards")
        return self.n_nodes // self.n_shards

    @property
    def f(self) -> int:
        n = self.shard_size
        if (n - 1) % 3:
            raise ValueError(
                "This simulator uses n = 3f + 1 committees; choose a shard size such as 4, 7, 10, 13, 16, 19, 22."
            )
        return (n - 1) // 3
