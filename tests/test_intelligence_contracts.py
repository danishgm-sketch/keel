from __future__ import annotations

import pytest

from intel_helpers import FIXED_TS, healthy_inputs, healthy_state
from keel.intelligence import Posture, build_state
from keel.intelligence.contracts import KeelActionProposal, canonical_json


def test_canonical_serialisation_is_deterministic():
    s = healthy_state()
    assert canonical_json(s) == canonical_json(s)  # function is deterministic
    # content-stability across instances is the state_id's job (excludes wall clock)
    assert healthy_state().state_id == healthy_state().state_id


def test_identical_inputs_produce_identical_state_ids():
    a = build_state(healthy_inputs())
    b = build_state(healthy_inputs())
    assert a.state_id == b.state_id  # created_at is excluded from the id


def test_different_inputs_change_state_id():
    a = healthy_state()
    b = healthy_state(broker_reconciled=False)
    assert a.state_id != b.state_id


def test_timestamps_are_utc_aware():
    s = healthy_state()
    assert s.observation_ts.tzinfo is not None
    assert s.observation_ts == FIXED_TS
    assert s.created_at.tzinfo is not None


def test_invalid_multipliers_are_rejected():
    for bad in (1.5, -0.1):
        with pytest.raises(ValueError, match="reduction-only"):
            KeelActionProposal(
                state_id="s",
                model_bundle_id="m",
                deployment_candidate_id="c",
                posture=Posture.DEFENSIVE,
                participation_multiplier=bad,
                position_limit_multiplier=0.5,
                strategy_scope=(),
                candidate_scope=(),
            )


def test_missing_required_field_fails_construction():
    with pytest.raises(TypeError):
        KeelActionProposal(  # missing required fields
            state_id="s",
            posture=Posture.DEFENSIVE,
        )


def test_completeness_between_zero_and_one():
    assert 0.0 <= build_state(healthy_inputs()).completeness <= 1.0
    assert build_state(healthy_inputs()).completeness == 1.0  # fully healthy
