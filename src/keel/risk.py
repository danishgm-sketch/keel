"""Fixed-fractional position sizing from stop distance.

The risk fraction is an explicit parameter with a conservative default, not a
grep-enforced literal; the invariants (risk never exceeds the fraction, no
silent leverage) are enforced by tests, which is where invariants belong.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

DEFAULT_RISK_FRACTION = 0.01


@dataclass(frozen=True)
class Sizing:
    shares: int
    cash_risk: float  # planned loss at the stop; a gap through the stop can exceed it


def size_from_stop(
    equity: float,
    entry: float,
    stop: float,
    risk_fraction: float = DEFAULT_RISK_FRACTION,
) -> Sizing:
    """Shares such that (entry - stop) * shares <= equity * risk_fraction,
    with notional capped at equity so a tight stop cannot create leverage."""
    if not 0 < risk_fraction <= 0.05:
        raise ValueError("risk_fraction must be in (0, 0.05]")
    dist = abs(entry - stop)
    if equity <= 0 or entry <= 0 or dist <= 0:
        return Sizing(0, 0.0)
    shares = math.floor(equity * risk_fraction / dist)
    shares = min(shares, math.floor(equity / entry))
    return Sizing(shares, shares * dist)
