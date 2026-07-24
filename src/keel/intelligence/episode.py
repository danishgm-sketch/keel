"""Episode factory.

An episode is the durable record of one shadow decision: the exact state, the
legal actions, the baseline, the model proposal (if any), the validated action,
and placeholders for outcomes that will be observed later. The final reward is
deliberately NOT the adjacent equity move — that is a legacy heuristic, not a
valid training signal (see ROADMAP / docs). Outcome fields stay empty here.
"""

from __future__ import annotations

import hashlib

from keel.intelligence.contracts import (
    CounterfactualOutcome,
    KeelActionProposal,
    KeelEpisode,
    KeelState,
    ObservedOutcome,
    Posture,
    PredictedOutcome,
    ValidatedKeelAction,
)


def make_episode(
    state: KeelState,
    baseline: ValidatedKeelAction,
    proposal: KeelActionProposal | None,
    validated: ValidatedKeelAction,
) -> KeelEpisode:
    legal = tuple(p.label for p in Posture if p <= baseline.posture)  # no escalation is legal
    op_integrity = (
        state.operational.database_healthy
        and state.operational.journal_healthy
        and state.execution.broker_reconciled
    )
    seed = f"{state.state_id}:{proposal.proposal_id if proposal else 'none'}:{validated.action_id}"
    episode_id = hashlib.sha256(seed.encode()).hexdigest()
    return KeelEpisode(
        episode_id=episode_id,
        state=state,
        legal_actions=legal,
        baseline_action=baseline,
        model_proposal=proposal,
        validated_action=validated,
        predicted_outcome=PredictedOutcome(),
        observed_outcome=ObservedOutcome(),
        counterfactual=CounterfactualOutcome(),
        attribution_quality=None,
        data_quality_score=state.completeness,
        operational_integrity=op_integrity,
    )
