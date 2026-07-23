"""Strategy contract and one example strategy.

A strategy sees only history (`Bars.upto(i)`) and the current open position,
and answers one question per bar: enter (with a stop), hold (optionally moving
the stop), or exit. All mechanics — fills, costs, sizing, stop execution —
belong to the engine.

The included SMA-cross strategy exists to exercise the plumbing and the test
suite. It is NOT an edge and is not claimed to be one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from keel.data import Bars


@dataclass(frozen=True)
class Position:
    entry_price: float
    stop: float
    shares: int
    entry_index: int


@dataclass(frozen=True)
class Enter:
    stop: float


@dataclass(frozen=True)
class Hold:
    stop: float | None = None  # optionally raise the stop; engine ignores loosening


@dataclass(frozen=True)
class Exit:
    pass


Decision = Enter | Hold | Exit | None


class Strategy(Protocol):
    warmup: int
    lane: str  # "intraday" (flattened at session close) or "swing" (held overnight)
    session_flat: bool  # True => the engine force-exits at the last bar of a session

    def on_bar(self, history: Bars, position: Position | None) -> Decision: ...


class SmaCross:
    """Long when fast SMA > slow SMA, exit on cross-down, initial stop at the
    recent swing low. Plumbing-test strategy — no edge claimed."""

    lane = "swing"
    session_flat = False

    def __init__(self, fast: int = 20, slow: int = 50, stop_lookback: int = 10):
        if fast >= slow:
            raise ValueError("fast must be < slow")
        self.fast, self.slow, self.stop_lookback = fast, slow, stop_lookback
        self.warmup = slow

    def on_bar(self, history: Bars, position: Position | None) -> Decision:
        close = history.close
        fast = close[-self.fast :].mean()
        slow = close[-self.slow :].mean()
        if position is None:
            if fast > slow:
                stop = float(np.min(history.low[-self.stop_lookback :]))
                if stop < close[-1]:
                    return Enter(stop=stop)
            return None
        if fast < slow:
            return Exit()
        return Hold()
