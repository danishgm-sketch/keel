"""Order-intent domain record + deterministic idempotency key.

Establishes the record for idempotent order submission (a later milestone wires it
into execution). The idempotency key is a pure function of the intent's identity,
so the same signal can never be turned into two orders by a retry or a crash.
This module does not submit orders.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(StrEnum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


def _now() -> datetime:
    return datetime.now(UTC)


def idempotency_key(
    deployment_id: str,
    candidate_id: str,
    strategy_id: str,
    symbol: str,
    signal_ts: str,
    side: str,
    quantity: int,
    intended_stop: float | None,
) -> str:
    """Stable key for one intended order. Identical identity -> identical key."""
    stop = "none" if intended_stop is None else f"{float(intended_stop):.4f}"
    seed = "|".join(
        [
            deployment_id,
            candidate_id,
            strategy_id,
            symbol.upper(),
            signal_ts,
            str(side).lower(),
            str(int(quantity)),
            stop,
        ]
    )
    return hashlib.sha256(seed.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class OrderIntent:
    intent_id: str
    idempotency_key: str
    deployment_id: str
    candidate_id: str
    strategy_id: str
    symbol: str
    signal_ts: str
    side: OrderSide
    quantity: int
    intended_stop: float | None
    intended_order_class: str
    status: OrderStatus = OrderStatus.PENDING
    broker_order_id: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)


def make_intent(
    deployment_id: str,
    candidate_id: str,
    strategy_id: str,
    symbol: str,
    signal_ts: str,
    side: str,
    quantity: int,
    intended_stop: float | None,
    intended_order_class: str = "oto",
) -> OrderIntent:
    key = idempotency_key(
        deployment_id, candidate_id, strategy_id, symbol, signal_ts, side, quantity, intended_stop
    )
    return OrderIntent(
        intent_id=key[:32],
        idempotency_key=key,
        deployment_id=deployment_id,
        candidate_id=candidate_id,
        strategy_id=strategy_id,
        symbol=symbol.upper(),
        signal_ts=signal_ts,
        side=OrderSide(str(side).lower()),
        quantity=int(quantity),
        intended_stop=intended_stop,
        intended_order_class=intended_order_class,
    )
