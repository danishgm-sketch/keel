"""Shadow runtime — orchestrate one intelligence evaluation, without touching orders.

The flow, per cycle:
  1. build the canonical ``KeelState``;
  2. compute the deterministic baseline action;
  3. obtain a model proposal from the pluggable provider (or none);
  4. validate the proposal through the pure authority validator (fail-closed);
  5. record baseline, proposal, validated result, and the ACTUAL applied action;
  6. return a ``ShadowResult``.

In shadow mode (K3) the applied action is ALWAYS the baseline. The runtime never
mutates trading limits, never places orders, and never changes authority. It is a
pure observer that produces a durable, auditable record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from keel.intelligence.authority import validate_proposal
from keel.intelligence.baseline import BaselineConfig, baseline_action
from keel.intelligence.contracts import (
    ActionSource,
    AuthorityGrant,
    AuthorityLevel,
    KeelActionProposal,
    KeelEpisode,
    KeelState,
    Posture,
    ValidatedKeelAction,
    now_utc,
)
from keel.intelligence.episode import make_episode
from keel.intelligence.policy import KeelPolicyProvider, NoModelPolicy, NoProposalError
from keel.intelligence.reasons import ReasonCode


@dataclass(frozen=True, slots=True)
class ShadowResult:
    state: KeelState
    baseline: ValidatedKeelAction
    proposal: KeelActionProposal | None
    validated: ValidatedKeelAction
    applied: ValidatedKeelAction  # in shadow mode, always the baseline
    episode: KeelEpisode
    mode: str = "shadow"


def shadow_grant(
    model_bundle_id: str,
    candidate_id: str,
    certified_strategies: tuple[str, ...] = (),
    ttl_minutes: int = 30,
    at: datetime | None = None,
) -> AuthorityGrant:
    """A shadow-level grant: permits all postures for recording, reduction-only
    ceilings, scoped to certified strategies. Shadow grants never apply to config."""
    at = at or now_utc()
    return AuthorityGrant(
        grant_id=f"shadow:{model_bundle_id}:{candidate_id}",
        model_bundle_id=model_bundle_id,
        deployment_candidate_id=candidate_id,
        level=AuthorityLevel.SHADOW,
        expires_at=at.astimezone(UTC) + timedelta(minutes=ttl_minutes),
        permitted_postures=tuple(Posture),
        max_participation_multiplier=1.0,
        max_position_limit_multiplier=1.0,
        strategy_scope=certified_strategies,
        candidate_scope=(),
    )


def _unavailable(baseline: ValidatedKeelAction) -> ValidatedKeelAction:
    return ValidatedKeelAction(
        state_id=baseline.state_id,
        posture=baseline.posture,
        participation_multiplier=baseline.participation_multiplier,
        position_limit_multiplier=baseline.position_limit_multiplier,
        source=ActionSource.FALLBACK,
        reason_codes=(ReasonCode.MODEL_UNAVAILABLE.value, ReasonCode.BASELINE_APPLIED.value),
        valid=False,
    )


def evaluate_shadow(
    state: KeelState,
    policy: KeelPolicyProvider | None = None,
    grant: AuthorityGrant | None = None,
    baseline_cfg: BaselineConfig | None = None,
    at: datetime | None = None,
) -> ShadowResult:
    """Pure orchestration: no I/O, no config mutation, no orders."""
    policy = policy or NoModelPolicy()
    baseline = baseline_action(state, baseline_cfg)
    grant = grant or shadow_grant(
        policy.model_bundle_id,
        state.deployment.candidate_id,
        state.strategies.certified_strategies,
        at=at,
    )

    proposal: KeelActionProposal | None = None
    try:
        proposal = policy.propose(state, baseline)
    except NoProposalError:
        proposal = None
    except Exception:
        # An unexpected provider failure must fail closed, never crash the cycle.
        proposal = None

    if proposal is None:
        validated = _unavailable(baseline)
    else:
        validated = validate_proposal(proposal, state, baseline, grant, at=at)

    episode = make_episode(state, baseline, proposal, validated)
    # Shadow mode: the ACTUAL applied action is always the baseline.
    return ShadowResult(
        state=state,
        baseline=baseline,
        proposal=proposal,
        validated=validated,
        applied=baseline,
        episode=episode,
    )


@dataclass
class KeelRuntime:
    """Holds the active policy/deployment and evaluates shadow decisions. This is
    the object the service owns. It records but never applies."""

    policy: KeelPolicyProvider = field(default_factory=NoModelPolicy)

    def evaluate(self, state: KeelState, at: datetime | None = None) -> ShadowResult:
        return evaluate_shadow(state, self.policy, at=at)

    @staticmethod
    def summarise(result: ShadowResult) -> dict:
        """A compact, JSON-safe record for status surfaces and persistence."""
        p = result.proposal
        return {
            "mode": result.mode,
            "state_id": result.state.state_id,
            "model_bundle": (p.model_bundle_id if p else result.applied.source.value),
            "completeness": result.state.completeness,
            "baseline_posture": result.baseline.posture.label,
            "proposal_posture": (p.posture.label if p else None),
            "validated_posture": result.validated.posture.label,
            "validated_source": result.validated.source.value,
            "validated_valid": result.validated.valid,
            "reason_codes": list(result.validated.reason_codes),
            "applied_posture": result.applied.posture.label,
            "quality_flags": list(result.state.quality_flags),
            "episode_id": result.episode.episode_id,
        }
