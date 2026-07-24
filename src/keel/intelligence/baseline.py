"""Deterministic baseline policy.

Pure function of a ``KeelState`` -> a bounded ``ValidatedKeelAction``. No LLM, no
randomness, no I/O. This is the permanent floor the whole system falls back to,
and the reference every model proposal is compared against. The most restrictive
triggered rule wins; every triggered rule contributes a reason code.

Safety ordering (most restrictive first):
  broker not reconciled / unprotected position / db or journal unhealthy /
  market data stale / state too incomplete  -> HALT
  state moderately incomplete / no certified edge                 -> DEFENSIVE
  high concentration / low remaining risk capacity                -> RESTRICTED
  otherwise                                                        -> NORMAL
"""

from __future__ import annotations

from dataclasses import dataclass

from keel.intelligence.contracts import (
    ActionSource,
    KeelState,
    Posture,
    ValidatedKeelAction,
)
from keel.intelligence.reasons import ReasonCode

# posture -> (participation_multiplier, position_limit_multiplier)
_POSTURE_LIMITS = {
    Posture.HALT: (0.0, 0.0),
    Posture.DEFENSIVE: (0.5, 0.5),
    Posture.RESTRICTED: (0.75, 0.75),
    Posture.NORMAL: (1.0, 1.0),
}


@dataclass(frozen=True, slots=True)
class BaselineConfig:
    halt_completeness: float = 0.40
    defensive_completeness: float = 0.70
    high_concentration: float = 0.35
    low_risk_capacity: float = 0.10


def baseline_action(state: KeelState, cfg: BaselineConfig | None = None) -> ValidatedKeelAction:
    cfg = cfg or BaselineConfig()
    reasons: list[ReasonCode] = []
    posture = Posture.NORMAL

    def restrict(to: Posture, code: ReasonCode) -> None:
        nonlocal posture
        posture = Posture(min(posture, to))
        reasons.append(code)

    ex = state.execution
    op = state.operational
    mk = state.market
    pf = state.portfolio
    ev = state.evidence

    # --- HALT-class safety gates ---
    if not ex.broker_reconciled:
        restrict(Posture.HALT, ReasonCode.BROKER_NOT_RECONCILED)
    if ex.unknown_broker_state:
        restrict(Posture.HALT, ReasonCode.UNKNOWN_BROKER_STATE)
    if pf.unprotected_positions > 0:
        restrict(Posture.HALT, ReasonCode.POSITION_UNPROTECTED)
    if not op.database_healthy:
        restrict(Posture.HALT, ReasonCode.DATABASE_UNHEALTHY)
    if not op.journal_healthy:
        restrict(Posture.HALT, ReasonCode.JOURNAL_UNHEALTHY)
    if mk.is_stale or not mk.feed_healthy:
        restrict(Posture.HALT, ReasonCode.MARKET_DATA_STALE)
    if state.completeness < cfg.halt_completeness:
        restrict(Posture.HALT, ReasonCode.STATE_INCOMPLETE)

    # --- DEFENSIVE-class ---
    if state.completeness < cfg.defensive_completeness:
        restrict(Posture.DEFENSIVE, ReasonCode.STATE_INCOMPLETE)
    if not ev.has_certified_edge:
        restrict(Posture.DEFENSIVE, ReasonCode.NO_CERTIFIED_EDGE)

    # --- RESTRICTED-class ---
    if pf.concentration is not None and pf.concentration > cfg.high_concentration:
        restrict(Posture.RESTRICTED, ReasonCode.PORTFOLIO_CONCENTRATION_HIGH)
    if (
        pf.remaining_risk_capacity is not None
        and pf.remaining_risk_capacity < cfg.low_risk_capacity
    ):
        restrict(Posture.RESTRICTED, ReasonCode.RISK_CAPACITY_LOW)

    if not reasons:
        reasons.append(ReasonCode.OK)

    part, poslim = _POSTURE_LIMITS[posture]
    return ValidatedKeelAction(
        state_id=state.state_id,
        posture=posture,
        participation_multiplier=part,
        position_limit_multiplier=poslim,
        source=ActionSource.BASELINE,
        reason_codes=tuple(dict.fromkeys(r.value for r in reasons)),
        valid=True,
    )
