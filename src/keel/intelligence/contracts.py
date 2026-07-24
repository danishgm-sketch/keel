"""Canonical Keel Intelligence contracts.

Immutable, versioned records that are the ONLY things Keel Intelligence observes
(``KeelState``) and the ONLY things it may emit (``KeelActionProposal``). Every
record is a frozen dataclass; IDs are derived from a canonical serialisation so
identical inputs always produce identical IDs. Timestamps are timezone-aware UTC.

Design rules enforced here:
- The world the model sees is a validated ``KeelState`` — nothing else.
- A proposal can only ever *reduce* activity: multipliers are clamped to [0, 1]
  and validated against a baseline elsewhere. Values above 1.0 are illegal.
- Missing safety information is represented as *unknown/degraded*, never healthy.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from enum import IntEnum, StrEnum

SCHEMA_VERSION = 1


# --------------------------------------------------------------------------- #
# Canonical serialisation + ids
# --------------------------------------------------------------------------- #
def _json_default(o):
    if isinstance(o, datetime):
        return o.astimezone(UTC).isoformat()
    if isinstance(o, StrEnum):
        return o.value
    if isinstance(o, frozenset):
        return sorted(o)
    raise TypeError(f"not canonical-serialisable: {type(o)!r}")


def canonical_json(obj) -> str:
    """Deterministic JSON: sorted keys, no incidental whitespace, UTC times."""
    if hasattr(obj, "__dataclass_fields__"):
        obj = asdict(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=_json_default)


def content_hash(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode()).hexdigest()


def now_utc() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class Posture(IntEnum):
    """Ordered by activity: HALT is the least active, NORMAL the most. The AI may
    never propose a posture *more* active than the deterministic baseline."""

    HALT = 0
    DEFENSIVE = 1
    RESTRICTED = 2
    NORMAL = 3

    @property
    def label(self) -> str:
        return self.name.lower()


class AuthorityLevel(StrEnum):
    NONE = "none"
    SHADOW = "shadow"  # observed + validated, never applied to config (K3)
    ACTIVE = "active"  # future: may bound live limits (not used in Milestone 1)


class ActionSource(StrEnum):
    BASELINE = "baseline"
    MODEL = "model"
    FALLBACK = "fallback"  # a rejected model proposal fell back to baseline


class DataQuality(StrEnum):
    OK = "ok"
    MISSING = "missing"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"


# --------------------------------------------------------------------------- #
# Sub-state records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class DeploymentState:
    deployment_id: str
    candidate_id: str
    model_bundle_id: str
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class EvidenceState:
    has_certified_edge: bool
    last_pvalue: float | None
    oos_sharpe: float | None
    folds: int | None
    champion: str | None
    quality: DataQuality = DataQuality.OK


@dataclass(frozen=True, slots=True)
class MarketState:
    is_open: bool | None  # None = unknown
    feed_healthy: bool
    last_bar_age_seconds: float | None
    quality: DataQuality = DataQuality.OK

    @property
    def is_stale(self) -> bool:
        return self.quality in (DataQuality.STALE, DataQuality.UNAVAILABLE, DataQuality.MISSING)


@dataclass(frozen=True, slots=True)
class PortfolioState:
    equity: float | None
    buying_power: float | None
    open_positions: int
    unprotected_positions: int
    gross_exposure: float | None
    concentration: float | None  # 0..1, largest position / gross
    remaining_risk_capacity: float | None  # 0..1
    quality: DataQuality = DataQuality.OK


@dataclass(frozen=True, slots=True)
class StrategyState:
    active_strategies: tuple[str, ...]
    certified_strategies: tuple[str, ...]
    quality: DataQuality = DataQuality.OK


@dataclass(frozen=True, slots=True)
class ExecutionState:
    broker_reachable: bool
    broker_reconciled: bool
    unknown_broker_state: bool
    pending_orders: int
    quality: DataQuality = DataQuality.OK


@dataclass(frozen=True, slots=True)
class OperationalState:
    process_instance_id: str
    database_healthy: bool
    journal_healthy: bool
    open_incidents: int
    quality: DataQuality = DataQuality.OK


# --------------------------------------------------------------------------- #
# KeelState
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class KeelState:
    deployment: DeploymentState
    evidence: EvidenceState
    market: MarketState
    portfolio: PortfolioState
    strategies: StrategyState
    execution: ExecutionState
    operational: OperationalState
    observation_ts: datetime
    completeness: float  # 0..1
    quality_flags: tuple[str, ...] = ()
    schema_version: int = SCHEMA_VERSION
    created_at: datetime = field(default_factory=now_utc)

    @property
    def state_id(self) -> str:
        """Stable ID from the canonical content (excludes wall-clock created_at)."""
        payload = asdict(self)
        payload.pop("created_at", None)
        return hashlib.sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":"), default=_json_default
            ).encode()
        ).hexdigest()


# --------------------------------------------------------------------------- #
# Actions
# --------------------------------------------------------------------------- #
def _check_multiplier(name: str, value: float) -> None:
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"{name} must be in [0.0, 1.0] (reduction-only); got {value!r}")


@dataclass(frozen=True, slots=True)
class KeelActionProposal:
    """The ONLY thing a model may emit. Multipliers are reduction-only ([0,1]);
    a value outside that range is illegal at construction."""

    state_id: str
    model_bundle_id: str
    deployment_candidate_id: str
    posture: Posture
    participation_multiplier: float
    position_limit_multiplier: float
    strategy_scope: tuple[str, ...]
    candidate_scope: tuple[str, ...]
    rationale: str = ""
    source_provenance: str = "model"
    schema_version: int = SCHEMA_VERSION
    created_at: datetime = field(default_factory=now_utc)

    def __post_init__(self):
        _check_multiplier("participation_multiplier", self.participation_multiplier)
        _check_multiplier("position_limit_multiplier", self.position_limit_multiplier)

    @property
    def proposal_id(self) -> str:
        return content_hash(replace(self, created_at=self.created_at))


@dataclass(frozen=True, slots=True)
class ValidatedKeelAction:
    """The bounded, authority-checked outcome. In shadow mode it is recorded but
    never applied to trading limits."""

    state_id: str
    posture: Posture
    participation_multiplier: float
    position_limit_multiplier: float
    source: ActionSource
    reason_codes: tuple[str, ...]
    valid: bool
    schema_version: int = SCHEMA_VERSION
    created_at: datetime = field(default_factory=now_utc)

    def __post_init__(self):
        _check_multiplier("participation_multiplier", self.participation_multiplier)
        _check_multiplier("position_limit_multiplier", self.position_limit_multiplier)

    @property
    def action_id(self) -> str:
        return content_hash(self)


# --------------------------------------------------------------------------- #
# Authority
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class AuthorityGrant:
    grant_id: str
    model_bundle_id: str
    deployment_candidate_id: str
    level: AuthorityLevel
    expires_at: datetime
    permitted_postures: tuple[Posture, ...]
    max_participation_multiplier: float
    max_position_limit_multiplier: float
    strategy_scope: tuple[str, ...]
    candidate_scope: tuple[str, ...]
    schema_version: int = SCHEMA_VERSION
    created_at: datetime = field(default_factory=now_utc)

    def is_expired(self, at: datetime) -> bool:
        return at.astimezone(UTC) >= self.expires_at.astimezone(UTC)


# --------------------------------------------------------------------------- #
# Outcomes + episodes
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class PredictedOutcome:
    metric: str = "evidence_adjusted_quality"
    value: float | None = None


@dataclass(frozen=True, slots=True)
class ObservedOutcome:
    metric: str = "evidence_adjusted_quality"
    value: float | None = None
    observed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CounterfactualOutcome:
    metric: str = "baseline_minus_model"
    value: float | None = None


@dataclass(frozen=True, slots=True)
class KeelEpisode:
    episode_id: str
    state: KeelState
    legal_actions: tuple[str, ...]
    baseline_action: ValidatedKeelAction
    model_proposal: KeelActionProposal | None
    validated_action: ValidatedKeelAction
    predicted_outcome: PredictedOutcome
    observed_outcome: ObservedOutcome
    counterfactual: CounterfactualOutcome
    attribution_quality: float | None
    data_quality_score: float
    operational_integrity: bool
    schema_version: int = SCHEMA_VERSION
    created_at: datetime = field(default_factory=now_utc)

    @property
    def content_hash(self) -> str:
        payload = asdict(self)
        payload.pop("created_at", None)
        return hashlib.sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":"), default=_json_default
            ).encode()
        ).hexdigest()
