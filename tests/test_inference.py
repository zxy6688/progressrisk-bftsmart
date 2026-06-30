import numpy as np

from pbft_progress_sim.inference import ParticleRiskFilter
from pbft_progress_sim.types import AttackModel, NetworkContext


def test_many_stalls_raise_posterior_risk():
    filt = ParticleRiskFilter(
        n_shards=2,
        committee_size=10,
        f=3,
        prior_active_fraction=0.2,
        particles=2500,
        attack=AttackModel(primary_withhold_prob=1.0),
        calibration_batches=1000,
        seed=12,
    )
    before = filt.snapshot().risk.copy()
    outcomes = np.array([[0, 0, 30], [30, 0, 0]])
    after = filt.update(outcomes, [NetworkContext(), NetworkContext()]).risk
    assert after[0] > before[0]
    assert after[0] > after[1]


def test_joint_prior_respects_global_committee_capacity():
    filt = ParticleRiskFilter(
        n_shards=5,
        committee_size=10,
        f=3,
        prior_active_fraction=0.25,
        particles=500,
        attack=AttackModel(),
        calibration_batches=100,
        seed=7,
    )
    assert (filt.particles >= 0).all()
    assert (filt.particles <= 10).all()
    assert (filt.particles.sum(axis=1) <= 50).all()


def test_attack_regime_posterior_normalizes():
    filt = ParticleRiskFilter(
        n_shards=2, committee_size=10, f=3, prior_active_fraction=0.2,
        particles=400, attack=AttackModel(), calibration_batches=100, seed=17,
        likelihood_attacks=(AttackModel(0.6, 0.5), AttackModel(0.9, 0.8)),
    )
    snap = filt.snapshot()
    assert abs(snap.attack_regime_posterior.sum() - 1.0) < 1e-12
    assert len(snap.attack_regime_posterior) == 2
