"""Ensemble — combine weak signals into one conviction, judged by the gate.

This is the heart of the RenTech pivot. Rather than picking one strategy
(winner-take-all), an ensemble blends several signals with weights into a single
long-conviction in [0, 1]. `EnsembleStrategy` adapts that conviction into the
enter/hold/exit contract, so an ensemble runs through the *same* backtest,
walk-forward, and edge-ledger machinery as any strategy — the combiner itself is
validated out-of-sample. Weights are proposed (equal by default, or by the LLM,
or fitted), never trusted: they only matter if the ensemble beats luck.
"""

from __future__ import annotations

import numpy as np

from keel.data import Bars
from keel.indicators import atr
from keel.signals import Signal, default_signals
from keel.strategy import Decision, Enter, Exit, Hold, Position


class Ensemble:
    def __init__(
        self, signals: list[Signal] | None = None, weights: dict[str, float] | None = None
    ):
        self.signals = signals if signals is not None else default_signals()
        self.weights = weights or {s.name: 1.0 for s in self.signals}
        self.warmup = max(s.warmup for s in self.signals)

    def conviction(self, bars: Bars) -> float:
        total = sum(max(0.0, self.weights.get(s.name, 0.0)) for s in self.signals)
        if total <= 0:
            return 0.0
        blended = sum(max(0.0, self.weights.get(s.name, 0.0)) * s.score(bars) for s in self.signals)
        return blended / total

    def contributions(self, bars: Bars) -> dict[str, float]:
        """Per-signal score right now — for transparency in the UI/journal."""
        return {s.name: round(s.score(bars), 3) for s in self.signals}


class EnsembleStrategy:
    """Trade the ensemble: enter when conviction clears `entry`, exit when it
    fades below `exit_`, with an ATR stop. Behaves like any Strategy."""

    lane = "intraday"
    session_flat = True

    def __init__(
        self,
        ensemble: Ensemble | None = None,
        entry: float = 0.55,
        exit_: float = 0.30,
        atr_period: int = 14,
        atr_mult: float = 2.5,
        tail: int = 400,
    ):
        self.ens = ensemble or Ensemble()
        self.entry, self.exit_ = entry, exit_
        self.atr_period, self.atr_mult, self.tail = atr_period, atr_mult, tail
        self.warmup = self.ens.warmup
        self.last_conviction = 0.0

    def on_bar(self, history: Bars, position: Position | None) -> Decision:
        conv = self.ens.conviction(history)
        self.last_conviction = conv
        if position is not None:
            return Exit() if conv < self.exit_ else Hold()
        if conv < self.entry:
            return None
        c = history.close[-self.tail :]
        h, lo = history.high[-self.tail :], history.low[-self.tail :]
        a = atr(h, lo, c, self.atr_period)[-1]
        if np.isnan(a) or a <= 0:
            return None
        stop = float(c[-1] - self.atr_mult * a)
        return Enter(stop=stop) if stop < c[-1] else None
