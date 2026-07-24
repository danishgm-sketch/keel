"""Signals — the RenTech pivot: many weak predictors, not a few strategies.

Instead of a strategy that says yes/no, a *signal* scores a symbol's recent bars
into a continuous long-conviction in [0, 1] (0 = nothing here, 1 = strong). No
single signal is meant to be an edge — the point is to combine several weak,
different ones (see `ensemble.py`) and let the walk-forward gate judge the
combination. Every signal is causal: it sees only history through the last bar.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from keel.data import Bars
from keel.indicators import atr, ema, rsi


def _clamp01(x: float) -> float:
    return 0.0 if x <= 0 else 1.0 if x >= 1 else float(x)


class Signal(Protocol):
    name: str
    warmup: int

    def score(self, bars: Bars) -> float: ...


class Rsi2Signal:
    """Short-term oversold inside an uptrend — stronger the more oversold."""

    name = "rsi2"

    def __init__(self, period: int = 2, oversold: float = 30.0, trend: int = 200, tail: int = 400):
        self.period, self.oversold, self.trend, self.tail = period, oversold, trend, tail
        self.warmup = trend

    def score(self, bars: Bars) -> float:
        c = bars.close[-self.tail :]
        if len(c) <= self.trend:
            return 0.0
        r = rsi(c, self.period)[-1]
        t = ema(c, self.trend)[-1]
        if np.isnan(r) or np.isnan(t) or c[-1] <= t:
            return 0.0
        return _clamp01((self.oversold - r) / self.oversold)


class MomentumSignal:
    """Trend strength: how far the fast EMA leads the slow one."""

    name = "momentum"

    def __init__(self, fast: int = 20, slow: int = 100, cap: float = 0.06, tail: int = 300):
        self.fast, self.slow, self.cap, self.tail = fast, slow, cap, tail
        self.warmup = slow

    def score(self, bars: Bars) -> float:
        c = bars.close[-self.tail :]
        if len(c) <= self.slow:
            return 0.0
        ef, es = ema(c, self.fast)[-1], ema(c, self.slow)[-1]
        if np.isnan(ef) or np.isnan(es) or es <= 0:
            return 0.0
        return _clamp01((ef - es) / es / self.cap)


class BreakoutSignal:
    """Proximity to (or through) the recent high — momentum breakout."""

    name = "breakout"

    def __init__(self, lookback: int = 20, tail: int = 120):
        self.lookback, self.tail = lookback, tail
        self.warmup = lookback + 1

    def score(self, bars: Bars) -> float:
        h = bars.high[-self.tail :]
        c = bars.close[-self.tail :]
        if len(h) <= self.lookback:
            return 0.0
        prior_high = float(np.max(h[-self.lookback - 1 : -1]))
        if prior_high <= 0:
            return 0.0
        return (
            _clamp01((c[-1] / prior_high - 1) / 0.02 + 0.5) if c[-1] >= prior_high * 0.99 else 0.0
        )


class PullbackSignal:
    """Uptrend pullback that tags the fast EMA and closes back above it."""

    name = "pullback"

    def __init__(self, fast: int = 20, slow: int = 100, tail: int = 300):
        self.fast, self.slow, self.tail = fast, slow, tail
        self.warmup = slow

    def score(self, bars: Bars) -> float:
        c = bars.close[-self.tail :]
        lo = bars.low[-self.tail :]
        if len(c) <= self.slow:
            return 0.0
        ef, es = ema(c, self.fast)[-1], ema(c, self.slow)[-1]
        if np.isnan(ef) or np.isnan(es) or ef <= es:
            return 0.0  # not an uptrend
        if lo[-1] <= ef and c[-1] > ef:  # dipped to the fast EMA and reclaimed
            return _clamp01((ef - lo[-1]) / ef / 0.01)
        return 0.0


class LowVolSignal:
    """Prefer calm names: high when recent volatility is low (quality filter)."""

    name = "lowvol"

    def __init__(self, period: int = 14, cap: float = 0.03, tail: int = 120):
        self.period, self.cap, self.tail = period, cap, tail
        self.warmup = period + 1

    def score(self, bars: Bars) -> float:
        c = bars.close[-self.tail :]
        h, lo = bars.high[-self.tail :], bars.low[-self.tail :]
        if len(c) <= self.period:
            return 0.0
        a = atr(h, lo, c, self.period)[-1]
        if np.isnan(a) or c[-1] <= 0:
            return 0.0
        vol = a / c[-1]
        return _clamp01(1.0 - vol / self.cap)


def default_signals() -> list[Signal]:
    return [Rsi2Signal(), MomentumSignal(), BreakoutSignal(), PullbackSignal(), LowVolSignal()]


SIGNAL_NAMES = [s.name for s in default_signals()]
