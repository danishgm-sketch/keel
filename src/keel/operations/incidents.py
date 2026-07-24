"""Structured incidents — operational safety events with a lifecycle.

Incidents are persisted, surfaced in status, and (via the deterministic policy's
state flags) can block activity. They do not themselves place or cancel orders.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class IncidentSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class IncidentCategory(StrEnum):
    BROKER_RECONCILIATION_FAILURE = "BROKER_RECONCILIATION_FAILURE"
    POSITION_PROTECTION_FAILURE = "POSITION_PROTECTION_FAILURE"
    STALE_MARKET_DATA = "STALE_MARKET_DATA"
    DATABASE_FAILURE = "DATABASE_FAILURE"
    JOURNAL_FAILURE = "JOURNAL_FAILURE"
    INVALID_MODEL_PROPOSAL = "INVALID_MODEL_PROPOSAL"
    EXPIRED_AUTHORITY = "EXPIRED_AUTHORITY"
    STATE_INCOMPLETENESS = "STATE_INCOMPLETENESS"
    DUPLICATE_ORDER_INTENT = "DUPLICATE_ORDER_INTENT"
    UNKNOWN_BROKER_STATE = "UNKNOWN_BROKER_STATE"


class IncidentStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Incident:
    incident_id: str
    category: IncidentCategory
    severity: IncidentSeverity
    status: IncidentStatus
    message: str
    correlation_id: str | None = None
    deployment_id: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)


def new_incident(
    category: IncidentCategory,
    severity: IncidentSeverity,
    message: str,
    correlation_id: str | None = None,
    deployment_id: str | None = None,
) -> Incident:
    ts = _now()
    seed = f"{category.value}:{severity.value}:{message}:{ts.isoformat()}"
    incident_id = hashlib.sha256(seed.encode()).hexdigest()[:32]
    return Incident(
        incident_id=incident_id,
        category=category,
        severity=severity,
        status=IncidentStatus.OPEN,
        message=message,
        correlation_id=correlation_id,
        deployment_id=deployment_id,
        created_at=ts,
        updated_at=ts,
    )
