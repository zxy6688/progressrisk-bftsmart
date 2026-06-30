from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .inference import PosteriorSnapshot
from .exact_inference import ExactConstrainedRiskPosterior


@dataclass(frozen=True)
class ExchangeAction:
    hot_shard: int
    cold_shard: int
    k: int
    predicted_max_risk_before: float
    predicted_max_risk_after: float
    utility: float


class RiskAwareExchangeController:
    """Finite action controller over a=(hot shard, cold shard, exchange size)."""

    def __init__(
        self,
        committee_size: int,
        f: int,
        n_nodes: int,
        candidate_partners: int,
        max_exchange_k: int,
        migration_penalty: float,
        minimum_predicted_gain: float,
        prediction_samples: int,
        seed: int,
    ) -> None:
        self.committee_size = committee_size
        self.f = f
        self.n_nodes = n_nodes
        self.candidate_partners = candidate_partners
        self.max_exchange_k = max_exchange_k
        self.migration_penalty = migration_penalty
        self.minimum_predicted_gain = minimum_predicted_gain
        self.prediction_samples = prediction_samples
        self.rng = np.random.default_rng(seed)

    def choose_action(
        self, posterior: ExactConstrainedRiskPosterior, snapshot: PosteriorSnapshot
    ) -> ExchangeAction | None:
        risks = snapshot.risk
        h = int(np.argmax(risks))
        before = float(np.max(risks))
        candidates = [s for s in np.argsort(risks) if s != h][: self.candidate_partners]
        if not candidates:
            return None

        best: ExchangeAction | None = None
        samples = posterior.draw_particles(self.prediction_samples)
        for c in candidates:
            for k in range(1, min(self.max_exchange_k, self.committee_size) + 1):
                after = self._predict_max_risk_after_exchange(samples, h, int(c), k)
                cost = (2.0 * k) / self.n_nodes
                utility = -after - self.migration_penalty * cost
                action = ExchangeAction(
                    hot_shard=h,
                    cold_shard=int(c),
                    k=k,
                    predicted_max_risk_before=before,
                    predicted_max_risk_after=after,
                    utility=utility,
                )
                if best is None or action.utility > best.utility:
                    best = action

        if best is None:
            return None
        if before - best.predicted_max_risk_after < self.minimum_predicted_gain:
            return None
        return best

    def choose_oracle_action(self, true_active_loads: np.ndarray) -> ExchangeAction | None:
        """Simulator-only upper bound using true shard loads, never identities.

        This is not a deployable policy. It answers whether random exchange has
        useful headroom even if the controller knew the correct hot/cold shards.
        """
        if true_active_loads.ndim != 1:
            raise ValueError("true_active_loads must be a 1D vector")
        h = int(np.argmax(true_active_loads))
        before = float(np.any(true_active_loads > self.f))
        candidates = [s for s in np.argsort(true_active_loads) if s != h][: self.candidate_partners]
        if not candidates:
            return None
        samples = np.repeat(true_active_loads[np.newaxis, :], self.prediction_samples, axis=0)
        best: ExchangeAction | None = None
        for c in candidates:
            for k in range(1, min(self.max_exchange_k, self.committee_size) + 1):
                after = self._predict_max_risk_after_exchange(samples, h, int(c), k)
                cost = (2.0 * k) / self.n_nodes
                utility = -after - self.migration_penalty * cost
                candidate = ExchangeAction(
                    hot_shard=h,
                    cold_shard=int(c),
                    k=k,
                    predicted_max_risk_before=before,
                    predicted_max_risk_after=after,
                    utility=utility,
                )
                if best is None or candidate.utility > best.utility:
                    best = candidate
        if best is None or before - best.predicted_max_risk_after < self.minimum_predicted_gain:
            return None
        return best

    def _predict_max_risk_after_exchange(
        self, samples: np.ndarray, h: int, c: int, k: int
    ) -> float:
        counts = samples.copy()
        ah = counts[:, h]
        ac = counts[:, c]
        out_h = self.rng.hypergeometric(ah, self.committee_size - ah, k)
        out_c = self.rng.hypergeometric(ac, self.committee_size - ac, k)
        counts[:, h] = ah - out_h + out_c
        counts[:, c] = ac - out_c + out_h
        risk = (counts > self.f).mean(axis=0)
        return float(np.max(risk))
