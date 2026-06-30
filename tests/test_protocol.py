import numpy as np

from pbft_progress_sim.protocol import Outcome, simulate_batch
from pbft_progress_sim.types import AttackModel, NetworkContext


def test_no_active_blockers_normal_without_network_noise():
    trace = simulate_batch(
        active_blockers=0,
        committee_size=10,
        f=3,
        context=NetworkContext(timeout_prob=0.0, quorum_outage_prob=0.0),
        attack=AttackModel(primary_withhold_prob=1.0, backup_withhold_prob=1.0),
        rng=np.random.default_rng(2),
    )
    assert trace.outcome == Outcome.NORMAL


def test_all_active_blockers_stall_if_everyone_withholds():
    trace = simulate_batch(
        active_blockers=4,
        committee_size=10,
        f=3,
        context=NetworkContext(timeout_prob=0.0, quorum_outage_prob=0.0, max_view_changes=1),
        attack=AttackModel(primary_withhold_prob=0.0, backup_withhold_prob=1.0),
        rng=np.random.default_rng(4),
    )
    assert trace.outcome == Outcome.STALLED


def test_above_threshold_is_not_deterministically_stalled_when_attackers_sometimes_cooperate():
    outcomes = []
    rng = np.random.default_rng(2026)
    for _ in range(250):
        outcomes.append(
            simulate_batch(
                active_blockers=4,
                committee_size=10,
                f=3,
                context=NetworkContext(timeout_prob=0.0, quorum_outage_prob=0.0),
                attack=AttackModel(primary_withhold_prob=0.0, backup_withhold_prob=0.80),
                rng=rng,
            ).outcome
        )
    assert Outcome.NORMAL in outcomes
    assert Outcome.STALLED in outcomes
