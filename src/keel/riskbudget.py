"""Portfolio risk budget — the bank lens.

Promotes the per-trade 1% rule into portfolio-level governance: a cap on total
gross exposure, a cap on how many names, and a drawdown budget that forces a
defensive posture when the equity curve bleeds past a threshold. These are hard,
pre-trade limits — a new order that would breach them is refused, not sized down
after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Limits:
    max_gross_exposure: float = 1.0  # fraction of equity (1.0 = no leverage)
    max_positions: int = 20
    daily_drawdown_budget: float = 0.03  # de-risk if today's drawdown exceeds this


def check_order(
    equity: float,
    gross_exposure: float,
    open_positions: int,
    new_notional: float,
    limits: Limits,
) -> tuple[bool, str]:
    """Allow this new order? Returns (allowed, reason)."""
    if equity <= 0:
        return False, "no equity"
    if open_positions >= limits.max_positions:
        return False, f"position cap reached ({limits.max_positions})"
    projected = (gross_exposure + new_notional) / equity
    if projected > limits.max_gross_exposure:
        return False, f"gross exposure {projected:.0%} > cap {limits.max_gross_exposure:.0%}"
    return True, "ok"


def drawdown_posture(equity_curve: list[float], limits: Limits) -> str:
    """'defensive' once drawdown from the running peak exceeds the budget."""
    if len(equity_curve) < 2:
        return "normal"
    peak = equity_curve[0]
    worst = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        if peak > 0:
            worst = min(worst, v / peak - 1.0)
    return "defensive" if -worst > limits.daily_drawdown_budget else "normal"
