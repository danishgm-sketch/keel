"""Policy providers — the pluggable proposers.

A provider observes a ``KeelState`` and the deterministic baseline and returns a
strict ``KeelActionProposal``. It cannot execute anything; it can only propose,
and its output is treated as untrusted input downstream. Free-form LLM text never
crosses this boundary — the legacy adapter translates it into the strict schema
or fails, and failure means the baseline is kept.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from keel.intelligence.contracts import (
    KeelActionProposal,
    KeelState,
    Posture,
    ValidatedKeelAction,
)


class NoProposalError(Exception):
    """Raised when a provider has nothing valid to propose (fails closed)."""


@runtime_checkable
class KeelPolicyProvider(Protocol):
    model_bundle_id: str

    def propose(self, state: KeelState, baseline: ValidatedKeelAction) -> KeelActionProposal: ...


class NoModelPolicy:
    """The always-available provider that proposes nothing. The system runs on the
    deterministic baseline alone."""

    model_bundle_id = "none"

    def propose(self, state: KeelState, baseline: ValidatedKeelAction) -> KeelActionProposal:
        raise NoProposalError("no model deployed")


class LegacyLlmShadowPolicy:
    """Adapter that lets the existing general LLM act as a *shadow challenger*.

    It asks the legacy brain for a coarse risk posture, then translates strictly
    into a reduction-only ``KeelActionProposal`` bound to this exact state. Any
    malformed or unexpected output raises ``NoProposalError`` — it never leaks past the
    boundary, and the caller keeps the baseline.
    """

    model_bundle_id = "legacy-llm-shadow"

    def __init__(self, reason_fn=None):
        # reason_fn(state) -> {"risk_posture": "normal"|"defensive", "rationale": str}
        self._reason_fn = reason_fn

    def _reason(self, state: KeelState) -> dict:
        if self._reason_fn is not None:
            return self._reason_fn(state)
        # Default: consult the legacy AiBrain with a minimal, Keel-only briefing.
        from keel.brain import AiBrain
        from keel.llm import pick_provider

        llm = pick_provider()
        if llm is None:
            raise NoProposalError("no llm available")
        briefing = {
            "has_proven_edge": state.evidence.has_certified_edge,
            "completeness": state.completeness,
            "open_positions": state.portfolio.open_positions,
            "market_open": state.market.is_open,
        }
        return AiBrain(llm).reason(briefing)

    def propose(self, state: KeelState, baseline: ValidatedKeelAction) -> KeelActionProposal:
        rec = self._reason(state)
        posture_str = str(rec.get("risk_posture", "")).lower()
        if posture_str not in ("normal", "defensive"):
            raise NoProposalError(f"malformed posture {posture_str!r}")
        if posture_str == "defensive":
            posture, part, poslim = Posture.DEFENSIVE, 0.5, 0.5
        else:
            posture, part, poslim = Posture.NORMAL, 1.0, 1.0
        return KeelActionProposal(
            state_id=state.state_id,
            model_bundle_id=self.model_bundle_id,
            deployment_candidate_id=state.deployment.candidate_id,
            posture=posture,
            participation_multiplier=part,
            position_limit_multiplier=poslim,
            strategy_scope=(),
            candidate_scope=(),
            rationale=str(rec.get("rationale", ""))[:400],
            source_provenance="legacy-llm-shadow",
        )
