import numpy as np
from pbft_progress_sim.exact_inference import ExactConstrainedRiskPosterior
from pbft_progress_sim.types import AttackModel, NetworkContext


def test_exact_posterior_conserves_active_budget_and_normalizes():
    filt = ExactConstrainedRiskPosterior(
        n_shards=3,
        committee_size=4,
        f=1,
        global_active_budget=3,
        attack=AttackModel(),
        calibration_batches=200,
        seed=4,
    )
    counts = np.array([[10, 0, 0], [8, 2, 0], [1, 4, 5]])
    snap = filt.update(counts, [NetworkContext(), NetworkContext(), NetworkContext()])
    assert np.all((snap.risk >= 0) & (snap.risk <= 1))
    samples = filt.draw_particles(800)
    assert np.all(samples.sum(axis=1) == 3)
    assert np.all((samples >= 0) & (samples <= 4))


def test_exact_posterior_increases_risk_for_degraded_shard():
    filt = ExactConstrainedRiskPosterior(
        n_shards=2,
        committee_size=4,
        f=1,
        global_active_budget=2,
        attack=AttackModel(),
        calibration_batches=400,
        seed=5,
    )
    snap = filt.update(
        np.array([[1, 4, 7], [12, 0, 0]]),
        [NetworkContext(), NetworkContext()],
    )
    assert snap.risk[0] > snap.risk[1]
