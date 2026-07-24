"""Stress testing — 'what does the book do in the worst week?'

Replays the current positions through market shocks and reports the loss. It is
honest about the thing that hurts most: on a hard gap, a stop does NOT save you —
the fill is at the gapped-open, which can be well below the stop. So a shock
larger than a position's stop distance is charged at the full shock, not the
planned loss. That's the difference between a real stress test and a comforting
one.
"""

from __future__ import annotations

DEFAULT_SCENARIOS = {
    "mild pullback -5%": -0.05,
    "correction -10%": -0.10,
    "crash -20%": -0.20,
    "flash gap -30%": -0.30,
}


def _position_loss(pos: dict, shock: float) -> float:
    """Loss for one long position under a downward `shock` (fraction, negative).
    Below the stop the loss is capped at the stop — UNLESS the shock gaps through
    it, in which case the fill is at the gapped price (no protection)."""
    price = float(pos["price"])
    shares = int(pos["shares"])
    stop = float(pos.get("stop", 0) or 0)
    shocked = price * (1 + shock)
    # orderly stop-out if the move stays above the stop; else gapped through it (full damage)
    exit_px = stop if (stop and shocked >= stop) else shocked
    return (exit_px - price) * shares


def stress_book(positions: list[dict], scenarios: dict[str, float] | None = None) -> dict:
    """Report P&L of the whole book under each scenario, as currency and as a
    fraction of the book's notional."""
    scenarios = scenarios or DEFAULT_SCENARIOS
    notional = sum(float(p["price"]) * int(p["shares"]) for p in positions)
    out = {}
    for name, shock in scenarios.items():
        loss = sum(_position_loss(p, shock) for p in positions)
        out[name] = {
            "pnl": round(loss, 2),
            "pct_of_book": round(loss / notional, 4) if notional else 0.0,
        }
    return {"notional": round(notional, 2), "scenarios": out}
