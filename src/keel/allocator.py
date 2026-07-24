"""Cross-sectional book — many small, risk-balanced bets, not a few positions.

Given a conviction score per candidate, pick the strongest names above a floor
and give each an *equal share of the risk budget*. Diversification across many
tiny, uncorrelated positions is the only real free lunch — this turns a modest
edge into a smoother curve instead of a lottery on a handful of names.

Pure and testable; returns a per-symbol risk fraction the trader sizes from.
"""

from __future__ import annotations


def allocate(
    convictions: dict[str, float],
    risk_fraction: float = 0.01,
    max_positions: int = 20,
    min_conviction: float = 0.5,
    tilt: bool = True,
) -> dict[str, float]:
    """Top-N names by conviction, each assigned a slice of the total risk budget.
    With `tilt`, higher-conviction names get proportionally more of the budget;
    otherwise the budget is split equally (pure risk parity)."""
    picks = sorted(
        ((c, s) for s, c in convictions.items() if c >= min_conviction),
        reverse=True,
    )[:max_positions]
    if not picks:
        return {}
    budget = risk_fraction  # total portfolio risk to deploy this cycle
    if tilt:
        total = sum(c for c, _ in picks)
        return {s: round(budget * c / total, 6) for c, s in picks}
    per = budget / len(picks)
    return {s: round(per, 6) for _, s in picks}


def gross_exposure(positions: list[dict]) -> float:
    """Sum of |market value| across positions (for the risk-budget check)."""
    return sum(abs(float(p.get("market_value", 0) or 0)) for p in positions)
