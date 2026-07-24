from __future__ import annotations

from datetime import timedelta

from intel_helpers import FIXED_TS, MODEL_BUNDLE, healthy_state
from keel.intelligence import (
    AuthorityGrant,
    AuthorityLevel,
    Posture,
    baseline_action,
    validate_proposal,
)
from keel.intelligence.contracts import ActionSource, KeelActionProposal
from keel.intelligence.reasons import ReasonCode


def _grant(**over) -> AuthorityGrant:
    base = dict(
        grant_id="g1",
        model_bundle_id=MODEL_BUNDLE,
        deployment_candidate_id="baseline",
        level=AuthorityLevel.SHADOW,
        expires_at=FIXED_TS + timedelta(hours=1),
        permitted_postures=tuple(Posture),
        max_participation_multiplier=1.0,
        max_position_limit_multiplier=1.0,
        strategy_scope=("rsi2", "ensemble"),
        candidate_scope=(),
    )
    base.update(over)
    return AuthorityGrant(**base)


def _proposal(state, **over) -> KeelActionProposal:
    base = dict(
        state_id=state.state_id,
        model_bundle_id=MODEL_BUNDLE,
        deployment_candidate_id="baseline",
        posture=Posture.DEFENSIVE,
        participation_multiplier=0.5,
        position_limit_multiplier=0.5,
        strategy_scope=(),
        candidate_scope=(),
    )
    base.update(over)
    return KeelActionProposal(**base)


def _validate(state, proposal, grant):
    baseline = baseline_action(state)
    return baseline, validate_proposal(proposal, state, baseline, grant, at=FIXED_TS)


def test_valid_reduction_only_proposal_passes():
    st = healthy_state()  # baseline NORMAL
    baseline, v = _validate(st, _proposal(st), _grant())
    assert v.valid is True
    assert v.source == ActionSource.MODEL
    assert v.posture == Posture.DEFENSIVE  # no escalation, it reduced
    assert v.participation_multiplier == 0.5
    assert ReasonCode.SHADOW_MODE_ONLY.value in v.reason_codes


def test_wrong_state_id_fails_closed():
    st = healthy_state()
    _, v = _validate(st, _proposal(st, state_id="not-the-state"), _grant())
    assert v.valid is False
    assert v.source == ActionSource.FALLBACK
    assert ReasonCode.STATE_ID_MISMATCH.value in v.reason_codes


def test_wrong_model_bundle_fails_closed():
    st = healthy_state()
    _, v = _validate(st, _proposal(st, model_bundle_id="other"), _grant())
    assert v.valid is False
    assert ReasonCode.MODEL_NOT_AUTHORISED.value in v.reason_codes


def test_wrong_deployment_fails_closed():
    st = healthy_state()
    _, v = _validate(st, _proposal(st, deployment_candidate_id="other"), _grant())
    assert v.valid is False
    assert ReasonCode.DEPLOYMENT_MISMATCH.value in v.reason_codes


def test_expired_grant_fails_closed():
    st = healthy_state()
    grant = _grant(expires_at=FIXED_TS - timedelta(minutes=1))
    _, v = _validate(st, _proposal(st), grant)
    assert v.valid is False
    assert ReasonCode.AUTHORITY_EXPIRED.value in v.reason_codes


def test_posture_escalation_fails_closed():
    st = healthy_state(edge_row={"beats_luck": False, "pvalue": 1.0})  # baseline DEFENSIVE
    baseline, v = _validate(
        st,
        _proposal(
            st, posture=Posture.NORMAL, participation_multiplier=1.0, position_limit_multiplier=1.0
        ),
        _grant(),
    )
    assert baseline.posture == Posture.DEFENSIVE
    assert v.valid is False
    assert v.posture == baseline.posture  # fell back, no escalation applied
    assert (
        ReasonCode.POSTURE_NOT_AUTHORISED.value in v.reason_codes
        or ReasonCode.PARTICIPATION_ESCALATION.value in v.reason_codes
    )


def test_participation_above_ceiling_fails_closed():
    st = healthy_state()
    grant = _grant(max_participation_multiplier=0.3)
    _, v = _validate(st, _proposal(st, participation_multiplier=0.5), grant)
    assert v.valid is False
    assert ReasonCode.PARTICIPATION_ESCALATION.value in v.reason_codes


def test_position_multiplier_above_ceiling_fails_closed():
    st = healthy_state()
    grant = _grant(max_position_limit_multiplier=0.2)
    _, v = _validate(st, _proposal(st, position_limit_multiplier=0.5), grant)
    assert v.valid is False
    assert ReasonCode.POSITION_LIMIT_ESCALATION.value in v.reason_codes


def test_uncertified_strategy_fails_closed():
    st = healthy_state()
    _, v = _validate(st, _proposal(st, strategy_scope=("not-certified",)), _grant())
    assert v.valid is False
    assert ReasonCode.UNCERTIFIED_STRATEGY.value in v.reason_codes


def test_candidate_out_of_scope_fails_closed():
    st = healthy_state()
    grant = _grant(candidate_scope=("only-this",))
    _, v = _validate(st, _proposal(st, candidate_scope=("something-else",)), grant)
    assert v.valid is False
    assert ReasonCode.CANDIDATE_OUT_OF_SCOPE.value in v.reason_codes


def test_broker_unreconciled_state_blocks_model_action():
    # defence in depth: even a well-formed proposal is refused on unsafe operations
    st = healthy_state(broker_reconciled=False)
    _, v = _validate(
        st,
        _proposal(
            st, posture=Posture.HALT, participation_multiplier=0.0, position_limit_multiplier=0.0
        ),
        _grant(),
    )
    assert v.valid is False
    assert ReasonCode.BROKER_NOT_RECONCILED.value in v.reason_codes
