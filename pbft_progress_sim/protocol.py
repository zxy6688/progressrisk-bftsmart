from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict

import numpy as np

from .types import AttackModel, NetworkContext


class Outcome(str, Enum):
    NORMAL = "N"
    RECOVERED = "R"
    STALLED = "S"


@dataclass(frozen=True)
class BatchTrace:
    outcome: Outcome
    view_changes: int
    primary_block_events: int
    benign_timeout_events: int
    quorum_outage_events: int
    timely_committers_last_view: int


def simulate_batch(
    active_blockers: int,
    committee_size: int,
    f: int,
    context: NetworkContext,
    attack: AttackModel,
    rng: np.random.Generator,
) -> BatchTrace:
    """Simulate one logical PBFT batch through normal and recovery views.

    A batch may complete in the original view (N), complete after one or more
    installed NEW-VIEW recoveries (R), or remain unfinished at the configured
    deadline (S). Active Byzantine validators withhold PRE-PREPARE and/or
    timely PREPARE/COMMIT messages probabilistically. Thus a >f active load
    raises stall probability but does *not* make every batch deterministically
    stall: Byzantine validators may selectively cooperate in a particular view.
    """
    if not 0 <= active_blockers <= committee_size:
        raise ValueError("active_blockers outside committee range")
    if committee_size != 3 * f + 1:
        raise ValueError("committee_size must equal 3f+1")
    if not (0.0 <= attack.primary_withhold_prob <= 1.0):
        raise ValueError("primary_withhold_prob must be in [0,1]")
    if not (0.0 <= attack.backup_withhold_prob <= 1.0):
        raise ValueError("backup_withhold_prob must be in [0,1]")
    if not (0.0 <= context.timeout_prob <= 1.0):
        raise ValueError("timeout_prob must be in [0,1]")
    if not (0.0 <= context.quorum_outage_prob <= 1.0):
        raise ValueError("quorum_outage_prob must be in [0,1]")

    view_changes = 0
    primary_blocks = 0
    benign_timeouts = 0
    quorum_outages = 0
    last_timed_committers = 0

    for _view in range(context.max_view_changes + 1):
        # In a shuffled committee, the primary for a particular view is active
        # with probability a/n. A faulty primary may withhold its proposal.
        primary_is_active = rng.random() < (active_blockers / committee_size)
        primary_withholds = primary_is_active and (
            rng.random() < attack.primary_withhold_prob
        )
        benign_timeout = rng.random() < context.timeout_prob

        if primary_withholds or benign_timeout:
            primary_blocks += int(primary_withholds)
            benign_timeouts += int(benign_timeout)
            view_changes += 1
            continue

        # A proposal is available. Honest replicas can still miss the
        # prepare/commit deadline under visible network stress. Active replicas
        # selectively withhold their votes according to the attack policy.
        honest_replicas = committee_size - active_blockers
        timely_honest = int(
            rng.binomial(honest_replicas, 1.0 - context.quorum_outage_prob)
        )
        timely_active = int(
            rng.binomial(active_blockers, 1.0 - attack.backup_withhold_prob)
        )
        timely_committers = timely_honest + timely_active
        last_timed_committers = timely_committers

        if timely_committers >= 2 * f + 1:
            outcome = Outcome.RECOVERED if view_changes else Outcome.NORMAL
            return BatchTrace(
                outcome=outcome,
                view_changes=view_changes,
                primary_block_events=primary_blocks,
                benign_timeout_events=benign_timeouts,
                quorum_outage_events=quorum_outages,
                timely_committers_last_view=last_timed_committers,
            )

        # This view cannot obtain a timely commit quorum; timeout ->
        # VIEW-CHANGE -> NEW-VIEW follows. Count it as one benign quorum
        # impairment only when an honest quorum loss contributed.
        if timely_honest < honest_replicas:
            quorum_outages += 1
        view_changes += 1

    return BatchTrace(
        outcome=Outcome.STALLED,
        view_changes=view_changes,
        primary_block_events=primary_blocks,
        benign_timeout_events=benign_timeouts,
        quorum_outage_events=quorum_outages,
        timely_committers_last_view=last_timed_committers,
    )


def calibrate_likelihood(
    committee_size: int,
    f: int,
    context: NetworkContext,
    attack: AttackModel,
    batches_per_state: int,
    seed: int,
    smoothing: float = 1.0,
) -> np.ndarray:
    """Estimate P(N/R/S | active_blockers=a, context, attack) offline."""
    rng = np.random.default_rng(seed)
    table = np.zeros((committee_size + 1, 3), dtype=float)
    order = [Outcome.NORMAL, Outcome.RECOVERED, Outcome.STALLED]
    idx: Dict[Outcome, int] = {o: i for i, o in enumerate(order)}

    for a in range(committee_size + 1):
        counts = np.full(3, smoothing, dtype=float)
        for _ in range(batches_per_state):
            trace = simulate_batch(a, committee_size, f, context, attack, rng)
            counts[idx[trace.outcome]] += 1.0
        table[a] = counts / counts.sum()
    return table
