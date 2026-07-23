"""Per-fill trading cost model: proportional (half-spread + slippage +
percentage commission) plus per-share fees. Defaults are deliberately on the
expensive side — a strategy that only survives at optimistic costs is not a
strategy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    proportional: float = 0.0005  # per side, fraction of notional (spread + slippage)
    per_share: float = 0.0002  # per side, currency per share

    def fill_cost(self, price: float, shares: int) -> float:
        return abs(price * shares) * self.proportional + abs(shares) * self.per_share


FREE = CostModel(proportional=0.0, per_share=0.0)
