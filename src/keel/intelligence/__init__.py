"""Keel Intelligence — a closed-domain, evidence-gated decision layer.

Its only world is Keel: the only input is a validated ``KeelState``, the only
output is a bounded ``KeelActionProposal``, and its only authority is an explicit,
expiring ``AuthorityGrant``. In Milestone 1 it runs in SHADOW mode — observed,
validated, and recorded, but never applied to trading limits or orders.

Import boundaries (enforced by review + tests): this package must not import
broker clients. Policy providers may propose but cannot execute.
"""

from keel.intelligence.authority import validate_proposal
from keel.intelligence.baseline import BaselineConfig, baseline_action
from keel.intelligence.contracts import (
    AuthorityGrant,
    AuthorityLevel,
    KeelActionProposal,
    KeelEpisode,
    KeelState,
    Posture,
    ValidatedKeelAction,
)
from keel.intelligence.reasons import ReasonCode
from keel.intelligence.runtime import KeelRuntime, ShadowResult, evaluate_shadow, shadow_grant
from keel.intelligence.state_builder import RuntimeInputs, build_state

__all__ = [
    "AuthorityGrant",
    "AuthorityLevel",
    "BaselineConfig",
    "KeelActionProposal",
    "KeelEpisode",
    "KeelRuntime",
    "KeelState",
    "Posture",
    "ReasonCode",
    "RuntimeInputs",
    "ShadowResult",
    "ValidatedKeelAction",
    "baseline_action",
    "build_state",
    "evaluate_shadow",
    "shadow_grant",
    "validate_proposal",
]
