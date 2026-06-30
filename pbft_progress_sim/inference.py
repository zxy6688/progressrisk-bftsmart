from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Iterable

import numpy as np

from .protocol import calibrate_likelihood
from .types import AttackModel, NetworkContext


@dataclass
class PosteriorSnapshot:
    risk: np.ndarray
    mean_active_load: np.ndarray
    effective_sample_size: float
    attack_regime_posterior: np.ndarray


# Offline likelihood calibration is a model artifact, not random per-seed noise.
_GLOBAL_LIKELIHOOD_CACHE: Dict[tuple, np.ndarray] = {}


def _stable_seed(key: tuple) -> int:
    digest = hashlib.blake2b(repr(key).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="little") % (2**31 - 1)


class ParticleRiskFilter:
    """Joint particle posterior over active loads and a global attack regime.

    A particle carries (A_1, ..., A_K, gamma), where gamma indexes one declared
    withholding-intensity regime. The posterior therefore performs Bayesian
    model averaging *after* observing an epoch, rather than averaging likelihood
    tables independently for every batch. This distinguishes "many weak
    blockers" from "fewer aggressive blockers" more faithfully.
    """

    def __init__(
        self,
        n_shards: int,
        committee_size: int,
        f: int,
        prior_active_fraction: float,
        particles: int,
        attack: AttackModel,
        calibration_batches: int,
        seed: int,
        likelihood_attacks: tuple[AttackModel, ...] | None = None,
    ) -> None:
        self.n_shards = n_shards
        self.committee_size = committee_size
        self.f = f
        self.prior_active_fraction = prior_active_fraction
        self.n_particles = particles
        self.attack = attack
        self.likelihood_attacks = tuple(likelihood_attacks or (attack,))
        self.calibration_batches = calibration_batches
        self.rng = np.random.default_rng(seed)
        self.particles = self._sample_joint_prior(particles)
        self.attack_regimes = self.rng.integers(
            0, len(self.likelihood_attacks), size=particles, dtype=np.int16
        )
        self.weights = np.full(particles, 1.0 / particles, dtype=float)
        self._likelihood_cache: Dict[tuple[float, float, int, str], np.ndarray] = {}

    def _sample_joint_prior(self, n_particles: int) -> np.ndarray:
        """Sample shard loads jointly, preserving a global active-load total."""
        total_nodes = self.n_shards * self.committee_size
        out = np.zeros((n_particles, self.n_shards), dtype=np.int16)
        totals = self.rng.binomial(total_nodes, self.prior_active_fraction, size=n_particles)
        for i, total in enumerate(totals):
            remain_active = int(total)
            remain_nodes = total_nodes
            for s in range(self.n_shards - 1):
                draw = int(
                    self.rng.hypergeometric(
                        remain_active,
                        remain_nodes - remain_active,
                        self.committee_size,
                    )
                )
                out[i, s] = draw
                remain_active -= draw
                remain_nodes -= self.committee_size
            out[i, -1] = remain_active
        return out

    def _likelihood_tables(self, context: NetworkContext) -> np.ndarray:
        """Return a table with shape (n_attack_regimes, n+1, 3)."""
        local_key = context.cache_key()
        if local_key not in self._likelihood_cache:
            tables = []
            for attack_model in self.likelihood_attacks:
                table_key = (
                    self.committee_size,
                    self.f,
                    local_key,
                    attack_model.primary_withhold_prob,
                    attack_model.backup_withhold_prob,
                    self.calibration_batches,
                )
                if table_key not in _GLOBAL_LIKELIHOOD_CACHE:
                    _GLOBAL_LIKELIHOOD_CACHE[table_key] = calibrate_likelihood(
                        committee_size=self.committee_size,
                        f=self.f,
                        context=context,
                        attack=attack_model,
                        batches_per_state=self.calibration_batches,
                        seed=_stable_seed(table_key),
                    )
                tables.append(_GLOBAL_LIKELIHOOD_CACHE[table_key])
            self._likelihood_cache[local_key] = np.stack(tables, axis=0)
        return self._likelihood_cache[local_key]

    def update(
        self,
        outcome_counts: np.ndarray,
        contexts: Iterable[NetworkContext],
    ) -> PosteriorSnapshot:
        """Bayesian update from one epoch of shard-wise N/R/S counts."""
        contexts = list(contexts)
        if outcome_counts.shape != (self.n_shards, 3):
            raise ValueError("outcome_counts must have shape (n_shards, 3)")
        if len(contexts) != self.n_shards:
            raise ValueError("one context per shard is required")

        log_weights = np.log(self.weights + 1e-300)
        for s, context in enumerate(contexts):
            tables = self._likelihood_tables(context)
            state_likelihood = tables[self.attack_regimes, self.particles[:, s]]
            log_weights += (outcome_counts[s] * np.log(state_likelihood + 1e-300)).sum(axis=1)

        log_weights -= np.max(log_weights)
        self.weights = np.exp(log_weights)
        self.weights /= self.weights.sum()

        ess = 1.0 / np.sum(self.weights**2)
        if ess < self.n_particles * 0.55:
            self._resample()
            ess = float(self.n_particles)

        return self.snapshot(ess)

    def _resample(self) -> None:
        indices = self.rng.choice(
            self.n_particles, size=self.n_particles, replace=True, p=self.weights
        )
        self.particles = self.particles[indices].copy()
        self.attack_regimes = self.attack_regimes[indices].copy()
        self.weights.fill(1.0 / self.n_particles)

    def snapshot(self, effective_sample_size: float | None = None) -> PosteriorSnapshot:
        risk = (self.particles > self.f).astype(float).T @ self.weights
        mean_active = self.particles.T @ self.weights
        regime_post = np.bincount(
            self.attack_regimes,
            weights=self.weights,
            minlength=len(self.likelihood_attacks),
        )
        if effective_sample_size is None:
            effective_sample_size = float(1.0 / np.sum(self.weights**2))
        return PosteriorSnapshot(
            risk=risk,
            mean_active_load=mean_active,
            effective_sample_size=effective_sample_size,
            attack_regime_posterior=regime_post,
        )

    def draw_particles(self, n: int) -> np.ndarray:
        idx = self.rng.choice(self.n_particles, size=n, replace=True, p=self.weights)
        return self.particles[idx].copy()

    def propagate_random_exchange(self, h: int, c: int, k: int) -> None:
        """Propagate the posterior through an unobserved random k-for-k exchange."""
        if h == c:
            raise ValueError("exchange requires two different shards")
        if not 1 <= k <= self.committee_size:
            raise ValueError("invalid exchange size")

        ah = self.particles[:, h].astype(int)
        ac = self.particles[:, c].astype(int)
        out_h = self.rng.hypergeometric(ah, self.committee_size - ah, k)
        out_c = self.rng.hypergeometric(ac, self.committee_size - ac, k)
        self.particles[:, h] = ah - out_h + out_c
        self.particles[:, c] = ac - out_c + out_h

    def reset_after_global_random_reshuffle(self) -> None:
        self.particles = self._sample_joint_prior(self.n_particles)
        self.weights.fill(1.0 / self.n_particles)
