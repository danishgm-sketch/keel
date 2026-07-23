"""Signal-generating strategies for a high-turnover (but not HFT) book.

Three lanes, all long-only in v1, all built on causal indicators:

- ``Rsi2Reversion``  — intraday mean reversion. Fades short-term oversold dips
  inside an uptrend. Fires often; this is the workhorse for "many trades a day".
- ``OpeningRangeBreakout`` — intraday momentum. One shot per symbol per session
  when price breaks the opening range.
- ``SwingPullback`` — multi-day trend pullback, held overnight.

None of these is claimed to be a proven edge. Each is a hypothesis the engine
executes honestly and the statistics judge. High turnover means costs are the
enemy: a setup that looks good gross can be dead net, and the backtest is built
to show you that.

Each call recomputes indicators on a bounded tail of history (fast, and enough
for the lookbacks) rather than the whole series.
"""

from __future__ import annotations

import numpy as np

from keel.data import Bars
from keel.indicators import atr, ema, rsi, session_dates
from keel.strategy import Decision, Enter, Exit, Hold, Position


class Rsi2Reversion:
    """Connors-style short-term mean reversion. In an uptrend (price above the
    trend EMA), buy a 2-period-RSI oversold dip; exit when RSI recovers or the
    session ends. Many signals per day across a watchlist."""

    lane = "intraday"
    session_flat = True

    def __init__(
        self,
        rsi_period: int = 2,
        entry_level: float = 10.0,
        exit_level: float = 60.0,
        trend_span: int = 200,
        atr_period: int = 14,
        atr_stop_mult: float = 2.5,
        tail: int = 400,
    ):
        self.rsi_period = rsi_period
        self.entry_level = entry_level
        self.exit_level = exit_level
        self.trend_span = trend_span
        self.atr_period = atr_period
        self.atr_stop_mult = atr_stop_mult
        self.tail = tail
        self.warmup = trend_span

    def on_bar(self, history: Bars, position: Position | None) -> Decision:
        c = history.close[-self.tail :]
        if len(c) <= self.trend_span:
            return Hold() if position else None
        h = history.high[-self.tail :]
        lo = history.low[-self.tail :]
        r = rsi(c, self.rsi_period)
        if position is not None:
            if not np.isnan(r[-1]) and r[-1] >= self.exit_level:
                return Exit()
            return Hold()
        trend = ema(c, self.trend_span)
        if np.isnan(r[-1]) or np.isnan(trend[-1]):
            return None
        if c[-1] > trend[-1] and r[-1] <= self.entry_level:
            a = atr(h, lo, c, self.atr_period)[-1]
            if np.isnan(a) or a <= 0:
                return None
            stop = float(c[-1] - self.atr_stop_mult * a)
            if stop < c[-1]:
                return Enter(stop=stop)
        return None


class OpeningRangeBreakout:
    """Buy when price breaks above the high of the session's first ``or_bars``
    bars; stop at the opening-range low; flattened at the close. One clean shot
    per symbol per day."""

    lane = "intraday"
    session_flat = True

    def __init__(self, or_bars: int = 6, tail: int = 200):
        self.or_bars = or_bars
        self.tail = tail
        self.warmup = 1

    def on_bar(self, history: Bars, position: Position | None) -> Decision:
        if position is not None:
            return Hold()
        ts = history.ts[-self.tail :]
        c = history.close[-self.tail :]
        h = history.high[-self.tail :]
        lo = history.low[-self.tail :]
        dates = session_dates(ts)
        today = dates == dates[-1]
        idx = np.nonzero(today)[0]
        if len(idx) <= self.or_bars:  # opening range not complete yet
            return None
        or_slice = idx[: self.or_bars]
        or_high = float(h[or_slice].max())
        or_low = float(lo[or_slice].min())
        # first breakout bar only: previous close at/below the range, this one above
        if c[-1] > or_high >= c[-2] and or_low < c[-1]:
            return Enter(stop=or_low)
        return None


class SwingPullback:
    """Uptrend (20>50>200 EMA) pullback: buy a close back above the 20 EMA after
    a dip that tagged it; stop below the recent swing low; exit on a close below
    the 50 EMA. Held overnight."""

    lane = "swing"
    session_flat = False

    def __init__(
        self,
        fast: int = 20,
        mid: int = 50,
        slow: int = 200,
        swing_lookback: int = 10,
        tail: int = 400,
    ):
        self.fast, self.mid, self.slow = fast, mid, slow
        self.swing_lookback = swing_lookback
        self.tail = tail
        self.warmup = slow

    def on_bar(self, history: Bars, position: Position | None) -> Decision:
        c = history.close[-self.tail :]
        if len(c) <= self.slow:
            return Hold() if position else None
        lo = history.low[-self.tail :]
        ef, em, es = ema(c, self.fast), ema(c, self.mid), ema(c, self.slow)
        if position is not None:
            if c[-1] < em[-1]:
                return Exit()
            return Hold()
        uptrend = ef[-1] > em[-1] > es[-1]
        tagged = lo[-1] <= ef[-1]  # this bar dipped to the fast EMA
        reclaimed = c[-1] > ef[-1]  # but closed back above it
        if uptrend and tagged and reclaimed:
            stop = float(np.min(lo[-self.swing_lookback :]))
            if stop < c[-1]:
                return Enter(stop=stop)
        return None
