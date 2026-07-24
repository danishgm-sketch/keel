from __future__ import annotations

from intel_helpers import FIXED_TS, healthy_state
from keel.intelligence import Posture, evaluate_shadow
from keel.intelligence.contracts import ActionSource
from keel.intelligence.policy import LegacyLlmShadowPolicy, NoModelPolicy
from keel.intelligence.reasons import ReasonCode


def test_shadow_applied_is_always_baseline():
    st = healthy_state()
    r = evaluate_shadow(st, NoModelPolicy(), at=FIXED_TS)
    assert r.mode == "shadow"
    assert r.applied == r.baseline  # model never applied in shadow


def test_no_model_preserves_baseline():
    st = healthy_state()
    r = evaluate_shadow(st, NoModelPolicy(), at=FIXED_TS)
    assert r.proposal is None
    assert r.validated.source == ActionSource.FALLBACK
    assert ReasonCode.MODEL_UNAVAILABLE.value in r.validated.reason_codes
    assert r.applied.posture == r.baseline.posture


def test_malformed_legacy_llm_fails_closed():
    st = healthy_state()
    policy = LegacyLlmShadowPolicy(reason_fn=lambda s: {"risk_posture": "garbage"})
    r = evaluate_shadow(st, policy, at=FIXED_TS)
    assert r.proposal is None  # adapter refused to emit
    assert r.validated.valid is False
    assert r.applied == r.baseline


def test_provider_exception_fails_closed():
    def boom(_state):
        raise RuntimeError("model crashed")

    st = healthy_state()
    r = evaluate_shadow(st, LegacyLlmShadowPolicy(reason_fn=boom), at=FIXED_TS)
    assert r.proposal is None
    assert r.applied == r.baseline


def test_valid_legacy_shadow_proposal_is_recorded_but_not_applied():
    st = healthy_state()  # baseline NORMAL, bundle matches the shadow policy
    policy = LegacyLlmShadowPolicy(reason_fn=lambda s: {"risk_posture": "defensive"})
    r = evaluate_shadow(st, policy, at=FIXED_TS)
    assert r.proposal is not None
    assert r.proposal.posture == Posture.DEFENSIVE
    assert r.validated.source == ActionSource.MODEL
    assert r.validated.valid is True
    # recorded, but the ACTUAL applied action is still the baseline
    assert r.applied == r.baseline
    # episode captures baseline AND proposal
    assert r.episode.baseline_action == r.baseline
    assert r.episode.model_proposal == r.proposal
