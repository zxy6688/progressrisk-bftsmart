from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Dict, Iterable

import numpy as np

from .inference import PosteriorSnapshot, _GLOBAL_LIKELIHOOD_CACHE, _stable_seed
from .protocol import calibrate_likelihood
from .types import AttackModel, NetworkContext


@dataclass
class ExactPosteriorState:
    """Exact posterior for one epoch under a fixed global active-load budget.

    The deployable v1.6 controller assumes a configuration-time adversarial
    budget L (an upper-bound/threat parameter, not validator identities). Given
    L and equal-size committees, the prior over shard counts is multivariate
    hypergeometric. For one epoch, the N/R/S likelihood factorizes by shard,
    which permits exact dynamic-programming marginals and exact posterior
    sampling without static-particle resampling collapse.
    """

    risk: np.ndarray
    mean_active_load: np.ndarray
    regime_posterior: np.ndarray
    regime_suffix: list[list[np.ndarray]]
    regime_local_weights: list[np.ndarray]
    total_active: int
    n_shards: int
    committee_size: int
    rng: np.random.Generator


class ExactConstrainedRiskPosterior:
    """One-epoch exact Bayesian posterior with a globally conserved active budget.

    Unlike the old static particle filter, this class intentionally does not
    reuse posterior particles across epochs. It is an epoch-reset controller:
    each decision uses the current epoch's N/R/S evidence and a declared global
    active-load budget. This prevents hidden-state persistence assumptions from
    being silently violated after reconfiguration and avoids particle
    impoverishment in low-probability threshold tails.
    """

    def __init__(
        self,
        n_shards: int,
        committee_size: int,
        f: int,
        global_active_budget: int,
        attack: AttackModel,
        calibration_batches: int,
        seed: int,
        likelihood_attacks: tuple[AttackModel, ...] | None = None,
    ) -> None:
        self.n_shards = n_shards
        self.committee_size = committee_size
        self.f = f
        self.global_active_budget = int(global_active_budget)
        self.attack = attack
        self.likelihood_attacks = tuple(likelihood_attacks or (attack,))
        self.calibration_batches = calibration_batches
        self.rng = np.random.default_rng(seed)
        self._likelihood_cache: Dict[tuple[float, float, int, str], np.ndarray] = {}
        if not 0 <= self.global_active_budget <= n_shards * committee_size:
            raise ValueError("global active budget outside network range")
        self.state: ExactPosteriorState | None = None

    def _likelihood_tables(self, context: NetworkContext) -> np.ndarray:
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

    @staticmethod
    def _convolve_truncated(a: np.ndarray, b: np.ndarray, limit: int) -> np.ndarray:
        out = np.convolve(a, b)
        if len(out) < limit + 1:
            out = np.pad(out, (0, limit + 1 - len(out)))
        return out[: limit + 1]

    def _local_weights(
        self, outcome_counts: np.ndarray, contexts: list[NetworkContext], regime: int
    ) -> tuple[np.ndarray, float]:
        L = self.global_active_budget
        n = self.committee_size
        weights = np.zeros((self.n_shards, n + 1), dtype=float)
        log_scale = 0.0
        logcomb = np.array([math.lgamma(n + 1) - math.lgamma(a + 1) - math.lgamma(n - a + 1) for a in range(n + 1)])
        for s, ctx in enumerate(contexts):
            table = self._likelihood_tables(ctx)[regime]
            counts = outcome_counts[s]
            logw = logcomb + (counts * np.log(table + 1e-300)).sum(axis=1)
            m = float(np.max(logw))
            weights[s] = np.exp(logw - m)
            log_scale += m
        return weights, log_scale

    def update(self, outcome_counts: np.ndarray, contexts: Iterable[NetworkContext]) -> PosteriorSnapshot:
        contexts = list(contexts)
        if outcome_counts.shape != (self.n_shards, 3):
            raise ValueError("outcome_counts must have shape (n_shards, 3)")
        if len(contexts) != self.n_shards:
            raise ValueError("one context per shard is required")

        L = self.global_active_budget
        regime_data: list[tuple[np.ndarray, list[np.ndarray], float]] = []
        log_evidence = []
        for g in range(len(self.likelihood_attacks)):
            local, scale = self._local_weights(outcome_counts, contexts, g)
            suffix: list[np.ndarray] = [np.array([]) for _ in range(self.n_shards + 1)]
            suffix[self.n_shards] = np.zeros(L + 1, dtype=float)
            suffix[self.n_shards][0] = 1.0
            for s in range(self.n_shards - 1, -1, -1):
                suffix[s] = self._convolve_truncated(local[s], suffix[s + 1], L)
            z = float(suffix[0][L])
            if z <= 0.0:
                raise RuntimeError("zero posterior normalizer; increase likelihood smoothing")
            regime_data.append((local, suffix, scale))
            log_evidence.append(math.log(z) + scale - (math.lgamma(self.n_shards * self.committee_size + 1) - math.lgamma(L + 1) - math.lgamma(self.n_shards * self.committee_size - L + 1)))

        log_evidence = np.asarray(log_evidence, dtype=float)
        log_evidence -= np.max(log_evidence)
        regime_post = np.exp(log_evidence)
        regime_post /= regime_post.sum()

        risk = np.zeros(self.n_shards, dtype=float)
        mean = np.zeros(self.n_shards, dtype=float)
        state_locals: list[np.ndarray] = []
        state_suffixes: list[list[np.ndarray]] = []
        for g, (local, suffix, _scale) in enumerate(regime_data):
            prefix: list[np.ndarray] = [np.array([]) for _ in range(self.n_shards + 1)]
            prefix[0] = np.zeros(L + 1, dtype=float)
            prefix[0][0] = 1.0
            for s in range(self.n_shards):
                prefix[s + 1] = self._convolve_truncated(prefix[s], local[s], L)
            z = float(suffix[0][L])
            marginals = np.zeros((self.n_shards, self.committee_size + 1), dtype=float)
            for s in range(self.n_shards):
                exclude = self._convolve_truncated(prefix[s], suffix[s + 1], L)
                for a in range(self.committee_size + 1):
                    remain = L - a
                    if 0 <= remain < len(exclude):
                        marginals[s, a] = local[s, a] * exclude[remain] / z
                # Numeric cleanup.
                marginals[s] /= marginals[s].sum()
            values = np.arange(self.committee_size + 1)
            risk += regime_post[g] * marginals[:, self.f + 1 :].sum(axis=1)
            mean += regime_post[g] * (marginals @ values)
            state_locals.append(local)
            state_suffixes.append(suffix)

        self.state = ExactPosteriorState(
            risk=risk,
            mean_active_load=mean,
            regime_posterior=regime_post,
            regime_suffix=state_suffixes,
            regime_local_weights=state_locals,
            total_active=L,
            n_shards=self.n_shards,
            committee_size=self.committee_size,
            rng=self.rng,
        )
        return PosteriorSnapshot(
            risk=risk,
            mean_active_load=mean,
            effective_sample_size=float("inf"),
            attack_regime_posterior=regime_post,
        )

    def snapshot(self) -> PosteriorSnapshot:
        if self.state is None:
            raise RuntimeError("update must be called before snapshot")
        return PosteriorSnapshot(
            risk=self.state.risk.copy(),
            mean_active_load=self.state.mean_active_load.copy(),
            effective_sample_size=float("inf"),
            attack_regime_posterior=self.state.regime_posterior.copy(),
        )

    def draw_particles(self, n_draws: int) -> np.ndarray:
        if self.state is None:
            raise RuntimeError("update must be called before draw_particles")
        st = self.state
        draws = np.zeros((n_draws, self.n_shards), dtype=np.int16)
        regimes = self.rng.choice(len(self.likelihood_attacks), size=n_draws, p=st.regime_posterior)
        L = st.total_active
        for i, g in enumerate(regimes):
            local = st.regime_local_weights[int(g)]
            suffix = st.regime_suffix[int(g)]
            remaining = L
            for s in range(self.n_shards - 1):
                probs = np.zeros(self.committee_size + 1, dtype=float)
                for a in range(self.committee_size + 1):
                    r = remaining - a
                    if 0 <= r < len(suffix[s + 1]):
                        probs[a] = local[s, a] * suffix[s + 1][r]
                total = probs.sum()
                if total <= 0:
                    raise RuntimeError("invalid posterior sample probabilities")
                probs /= total
                a = int(self.rng.choice(self.committee_size + 1, p=probs))
                draws[i, s] = a
                remaining -= a
            draws[i, -1] = remaining
        return draws

    def propagate_random_exchange(self, h: int, c: int, k: int) -> None:
        # Decisions use an epoch-reset posterior.  Membership changes affect the
        # next epoch's observed N/R/S, at which point a fresh exact posterior is
        # constructed.  There is deliberately no stale-posterior propagation.
        return None

    def reset_after_global_random_reshuffle(self) -> None:
        return None
