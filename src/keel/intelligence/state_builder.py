"""State builder — turn the live runtime into a canonical ``KeelState``.

Consumes *explicit* inputs (never globals) and is deterministic for identical
inputs. The cardinal rule: missing or unconfirmed safety information is recorded
as unknown/degraded — never as healthy. If we cannot confirm a position is
protected, it counts as unprotected; if we cannot confirm broker reconciliation,
it is *not* reconciled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from keel.intelligence.contracts import (
    DataQuality,
    DeploymentState,
    EvidenceState,
    ExecutionState,
    KeelState,
    MarketState,
    OperationalState,
    PortfolioState,
    StrategyState,
    now_utc,
)

# Critical fields that make a state "complete enough" to consider acting on.
_CRITICAL = (
    "evidence",
    "market_feed",
    "portfolio",
    "broker_reconciled",
    "position_protection",
    "database",
    "journal",
)


@dataclass
class RuntimeInputs:
    """Explicit snapshot the service fills each cycle. Plain (mutable) container;
    the builder converts it into an immutable KeelState."""

    deployment_id: str = "dev-local"
    candidate_id: str = "baseline"
    model_bundle_id: str = "none"
    process_instance_id: str = "unknown"

    # evidence
    edge_row: dict | None = None  # last edge_ledger row
    champion: str | None = None
    certified_strategies: tuple[str, ...] = ()
    active_strategies: tuple[str, ...] = ()

    # market
    clock: dict | None = None  # broker clock (is_open, next_close, ...)
    market_feed_healthy: bool = False
    last_bar_age_seconds: float | None = None

    # portfolio
    account: dict | None = None  # equity, buying_power
    positions: list[dict] = field(default_factory=list)
    protected_symbols: frozenset[str] = frozenset()  # symbols with a confirmed stop
    risk_fraction: float = 0.01

    # execution
    broker_reachable: bool = False
    broker_reconciled: bool = False
    pending_orders: int = 0

    # operational
    database_healthy: bool = False
    journal_healthy: bool = False
    open_incidents: int = 0

    observation_ts: datetime | None = None


def _f(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def build_state(inp: RuntimeInputs) -> KeelState:
    obs = (inp.observation_ts or now_utc()).astimezone(UTC)
    flags: list[str] = []

    # --- deployment ---
    deployment = DeploymentState(inp.deployment_id, inp.candidate_id, inp.model_bundle_id)

    # --- evidence ---
    row = inp.edge_row or {}
    evidence_known = bool(inp.edge_row)
    evidence = EvidenceState(
        has_certified_edge=bool(row.get("beats_luck")),
        last_pvalue=_f(row.get("pvalue")),
        oos_sharpe=_f(row.get("oos_sharpe")),
        folds=row.get("n_folds"),
        champion=inp.champion,
        quality=DataQuality.OK if evidence_known else DataQuality.MISSING,
    )
    if not evidence_known:
        flags.append("evidence_missing")

    # --- market ---
    clock = inp.clock or {}
    market_known = bool(inp.clock) and inp.market_feed_healthy
    market = MarketState(
        is_open=clock.get("is_open"),
        feed_healthy=bool(inp.market_feed_healthy),
        last_bar_age_seconds=inp.last_bar_age_seconds,
        quality=DataQuality.OK if market_known else DataQuality.STALE,
    )
    if not market_known:
        flags.append("market_feed_degraded")

    # --- portfolio ---
    acct = inp.account or {}
    equity = _f(acct.get("equity"))
    positions = inp.positions or []
    values = [abs(_f(p.get("market_value")) or 0.0) for p in positions]
    gross = sum(values) if values else 0.0
    concentration = (max(values) / gross) if gross > 0 else 0.0
    remaining_capacity = None
    if equity and equity > 0:
        remaining_capacity = max(0.0, 1.0 - gross / equity)
    # A position is unprotected unless we can *confirm* its stop.
    unprotected = sum(1 for p in positions if p.get("symbol") not in inp.protected_symbols)
    portfolio_known = bool(inp.account)
    portfolio = PortfolioState(
        equity=equity,
        buying_power=_f(acct.get("buying_power")),
        open_positions=len(positions),
        unprotected_positions=unprotected,
        gross_exposure=gross,
        concentration=concentration,
        remaining_risk_capacity=remaining_capacity,
        quality=DataQuality.OK if portfolio_known else DataQuality.UNAVAILABLE,
    )
    if not portfolio_known:
        flags.append("portfolio_unavailable")
    if unprotected:
        flags.append("unprotected_positions")

    # --- strategies ---
    strategies = StrategyState(
        active_strategies=tuple(inp.active_strategies),
        certified_strategies=tuple(inp.certified_strategies),
    )

    # --- execution (defaults are the SAFE/degraded values) ---
    execution = ExecutionState(
        broker_reachable=bool(inp.broker_reachable),
        broker_reconciled=bool(inp.broker_reconciled),
        unknown_broker_state=not inp.broker_reachable,
        pending_orders=int(inp.pending_orders),
        quality=DataQuality.OK if inp.broker_reconciled else DataQuality.DEGRADED,
    )
    if not inp.broker_reconciled:
        flags.append("broker_not_reconciled")

    # --- operational ---
    operational = OperationalState(
        process_instance_id=inp.process_instance_id,
        database_healthy=bool(inp.database_healthy),
        journal_healthy=bool(inp.journal_healthy),
        open_incidents=int(inp.open_incidents),
        quality=DataQuality.OK
        if (inp.database_healthy and inp.journal_healthy)
        else DataQuality.DEGRADED,
    )
    if not inp.database_healthy:
        flags.append("database_degraded")
    if not inp.journal_healthy:
        flags.append("journal_degraded")

    # --- completeness score over critical fields ---
    present = {
        "evidence": evidence_known,
        "market_feed": market_known,
        "portfolio": portfolio_known,
        "broker_reconciled": inp.broker_reconciled,
        "position_protection": unprotected == 0 and portfolio_known,
        "database": inp.database_healthy,
        "journal": inp.journal_healthy,
    }
    completeness = sum(1 for k in _CRITICAL if present.get(k)) / len(_CRITICAL)

    return KeelState(
        deployment=deployment,
        evidence=evidence,
        market=market,
        portfolio=portfolio,
        strategies=strategies,
        execution=execution,
        operational=operational,
        observation_ts=obs,
        completeness=round(completeness, 4),
        quality_flags=tuple(flags),
    )
