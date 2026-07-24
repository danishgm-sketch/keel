"""Stable, machine-readable reason codes.

These are the vocabulary the deterministic policy and the authority validator use
to explain *why* activity was blocked, reduced, or a model proposal rejected.
They are an enum, never scattered strings, so tests and dashboards can rely on
them. New codes are added here; existing values are never renamed.
"""

from __future__ import annotations

from enum import StrEnum


class ReasonCode(StrEnum):
    # --- deterministic safety (operational / execution) ---
    BROKER_NOT_RECONCILED = "BROKER_NOT_RECONCILED"
    POSITION_UNPROTECTED = "POSITION_UNPROTECTED"
    DATABASE_UNHEALTHY = "DATABASE_UNHEALTHY"
    JOURNAL_UNHEALTHY = "JOURNAL_UNHEALTHY"
    MARKET_DATA_STALE = "MARKET_DATA_STALE"
    STATE_INCOMPLETE = "STATE_INCOMPLETE"
    UNKNOWN_BROKER_STATE = "UNKNOWN_BROKER_STATE"

    # --- evidence / portfolio posture ---
    NO_CERTIFIED_EDGE = "NO_CERTIFIED_EDGE"
    PORTFOLIO_CONCENTRATION_HIGH = "PORTFOLIO_CONCENTRATION_HIGH"
    RISK_CAPACITY_LOW = "RISK_CAPACITY_LOW"

    # --- authority validation ---
    AUTHORITY_EXPIRED = "AUTHORITY_EXPIRED"
    MODEL_NOT_AUTHORISED = "MODEL_NOT_AUTHORISED"
    DEPLOYMENT_MISMATCH = "DEPLOYMENT_MISMATCH"
    STATE_ID_MISMATCH = "STATE_ID_MISMATCH"
    POSTURE_NOT_AUTHORISED = "POSTURE_NOT_AUTHORISED"
    PARTICIPATION_ESCALATION = "PARTICIPATION_ESCALATION"
    POSITION_LIMIT_ESCALATION = "POSITION_LIMIT_ESCALATION"
    UNCERTIFIED_STRATEGY = "UNCERTIFIED_STRATEGY"
    CANDIDATE_OUT_OF_SCOPE = "CANDIDATE_OUT_OF_SCOPE"
    INVALID_MODEL_PROPOSAL = "INVALID_MODEL_PROPOSAL"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"

    # --- mode ---
    SHADOW_MODE_ONLY = "SHADOW_MODE_ONLY"
    BASELINE_APPLIED = "BASELINE_APPLIED"
    OK = "OK"
