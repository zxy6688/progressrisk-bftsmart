from __future__ import annotations

import numpy as np


def brier_score(risk: np.ndarray, event: np.ndarray) -> float:
    return float(np.mean((risk - event.astype(float)) ** 2))


def top1_hit(risk: np.ndarray, active_counts: np.ndarray) -> float:
    """Whether a posterior top-risk shard is among shards with max true active load."""
    top_pred = np.flatnonzero(risk == risk.max())
    top_true = np.flatnonzero(active_counts == active_counts.max())
    return float(np.intersect1d(top_pred, top_true).size > 0)


def expected_calibration_error(
    risk: np.ndarray, event: np.ndarray, bins: int = 10
) -> float:
    """Equal-width ECE for a binary posterior-risk forecast."""
    risk = np.asarray(risk, dtype=float)
    event = np.asarray(event, dtype=float)
    if risk.size == 0:
        return float("nan")
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (risk >= lo) & ((risk < hi) if hi < 1.0 else (risk <= hi))
        if mask.any():
            ece += mask.mean() * abs(risk[mask].mean() - event[mask].mean())
    return float(ece)
