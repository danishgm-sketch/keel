"""Authority validator — pure, fail-closed.

Every model proposal passes through this before it is ever recorded as a model
action. It checks the proposal against the exact state, model bundle, deployment
candidate, and an explicit, expiring ``AuthorityGrant``. If *any* check fails, it
returns the deterministic baseline action (source = FALLBACK) with machine-
readable reason codes — never a partially-applied proposal. On success it returns
a model action that is bounded to be no more active than the baseline and within
the grant's ceilings (reduction-only).

This function has no I/O and no dependence on an LLM. It is the single choke point
through which model influence is permitted, and it can only ever *reduce* activity.
"""

from __future__ import annotations

from datetime import datetime

from keel.intelligence.contracts import (
    ActionSource,
    AuthorityGrant,
    KeelActionProposal,
    KeelState,
    Posture,
    ValidatedKeelAction,
    now_utc,
)
from keel.intelligence.reasons import ReasonCode


def _fallback(baseline: ValidatedKeelAction, reasons: list[ReasonCode]) -> ValidatedKeelAction:
    codes = tuple(dict.fromkeys([*(r.value for r in reasons), ReasonCode.BASELINE_APPLIED.value]))
    return ValidatedKeelAction(
        state_id=baseline.state_id,
        posture=baseline.posture,
        participation_multiplier=baseline.participation_multiplier,
        position_limit_multiplier=baseline.position_limit_multiplier,
        source=ActionSource.FALLBACK,
        reason_codes=codes,
        valid=False,
    )


def validate_proposal(
    proposal: KeelActionProposal,
    state: KeelState,
    baseline: ValidatedKeelAction,
    grant: AuthorityGrant,
    at: datetime | None = None,
) -> ValidatedKeelAction:
    at = at or now_utc()
    reasons: list[ReasonCode] = []

    # --- identity binding: proposal must match exactly this state/bundle/candidate ---
    if proposal.state_id != state.state_id:
        reasons.append(ReasonCode.STATE_ID_MISMATCH)
    if not (proposal.model_bundle_id == grant.model_bundle_id == state.deployment.model_bundle_id):
        reasons.append(ReasonCode.MODEL_NOT_AUTHORISED)
    if not (
        proposal.deployment_candidate_id
        == grant.deployment_candidate_id
        == state.deployment.candidate_id
    ):
        reasons.append(ReasonCode.DEPLOYMENT_MISMATCH)

    # --- authority grant validity ---
    if grant.is_expired(at):
        reasons.append(ReasonCode.AUTHORITY_EXPIRED)
    if grant.level.value == "none":
        reasons.append(ReasonCode.MODEL_NOT_AUTHORISED)

    # --- operational fail-closed (defence in depth; baseline already halts here) ---
    if not state.execution.broker_reconciled:
        reasons.append(ReasonCode.BROKER_NOT_RECONCILED)
    if state.portfolio.unprotected_positions > 0:
        reasons.append(ReasonCode.POSITION_UNPROTECTED)
    if not state.operational.database_healthy:
        reasons.append(ReasonCode.DATABASE_UNHEALTHY)
    if not state.operational.journal_healthy:
        reasons.append(ReasonCode.JOURNAL_UNHEALTHY)
    if state.market.is_stale or not state.market.feed_healthy:
        reasons.append(ReasonCode.MARKET_DATA_STALE)

    # --- posture authority + no escalation above baseline ---
    if proposal.posture not in grant.permitted_postures:
        reasons.append(ReasonCode.POSTURE_NOT_AUTHORISED)
    if int(proposal.posture) > int(baseline.posture):
        reasons.append(ReasonCode.POSTURE_NOT_AUTHORISED)

    # --- multipliers: reduction-only vs BOTH grant ceiling and baseline ---
    if (
        proposal.participation_multiplier > grant.max_participation_multiplier
        or proposal.participation_multiplier > baseline.participation_multiplier
    ):
        reasons.append(ReasonCode.PARTICIPATION_ESCALATION)
    if (
        proposal.position_limit_multiplier > grant.max_position_limit_multiplier
        or proposal.position_limit_multiplier > baseline.position_limit_multiplier
    ):
        reasons.append(ReasonCode.POSITION_LIMIT_ESCALATION)

    # --- scope: strategies must be certified AND inside the grant ---
    certified = set(state.strategies.certified_strategies)
    grant_strats = set(grant.strategy_scope)
    for s in proposal.strategy_scope:
        if s not in certified:
            reasons.append(ReasonCode.UNCERTIFIED_STRATEGY)
        if grant_strats and s not in grant_strats:
            reasons.append(ReasonCode.MODEL_NOT_AUTHORISED)
    grant_cands = set(grant.candidate_scope)
    if grant_cands:
        for c in proposal.candidate_scope:
            if c not in grant_cands:
                reasons.append(ReasonCode.CANDIDATE_OUT_OF_SCOPE)

    if reasons:
        return _fallback(baseline, reasons)

    # --- success: bounded model action (never more active than baseline) ---
    posture = Posture(min(int(proposal.posture), int(baseline.posture)))
    part = min(proposal.participation_multiplier, baseline.participation_multiplier)
    poslim = min(proposal.position_limit_multiplier, baseline.position_limit_multiplier)
    codes = [ReasonCode.OK]
    if grant.level.value == "shadow":
        codes.append(ReasonCode.SHADOW_MODE_ONLY)
    return ValidatedKeelAction(
        state_id=state.state_id,
        posture=posture,
        participation_multiplier=part,
        position_limit_multiplier=poslim,
        source=ActionSource.MODEL,
        reason_codes=tuple(c.value for c in codes),
        valid=True,
    )
