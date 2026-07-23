"""Walk-forward backtest engine.

No look-ahead by construction: at bar i the strategy is handed `bars.upto(i)` —
a slice that physically does not contain the future — and every decision it
makes is executed at bar i+1's open. Stops are checked against bar i+1's range
before the decision fill, since the stop was already resting.

Long-only in v0.1. One position at a time. Costs charged on every fill.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from keel.costs import CostModel
from keel.data import Bars
from keel.risk import DEFAULT_RISK_FRACTION, size_from_stop
from keel.strategy import Enter, Exit, Hold, Position, Strategy


@dataclass(frozen=True)
class Trade:
    symbol: str
    entry_ts: np.datetime64
    exit_ts: np.datetime64
    entry_price: float
    exit_price: float
    shares: int
    costs: float
    pnl: float  # net of costs
    stopped: bool


@dataclass
class Result:
    symbol: str
    equity_curve: np.ndarray  # mark-to-market equity at each bar close
    trades: list[Trade] = field(default_factory=list)

    @property
    def returns(self) -> np.ndarray:
        """Per-bar simple returns of the equity curve."""
        eq = self.equity_curve
        return np.diff(eq) / eq[:-1]

    @property
    def total_return(self) -> float:
        eq = self.equity_curve
        return float(eq[-1] / eq[0] - 1) if len(eq) else 0.0


def run(
    bars: Bars,
    strategy: Strategy,
    starting_equity: float = 100_000.0,
    risk_fraction: float = DEFAULT_RISK_FRACTION,
    costs: CostModel | None = None,
) -> Result:
    if costs is None:
        costs = CostModel()
    n = len(bars)
    equity = starting_equity
    curve = np.full(n, starting_equity, dtype=float)
    position: Position | None = None
    entry_ts: np.datetime64 | None = None
    entry_costs = 0.0
    trades: list[Trade] = []

    def close_out(i: int, price: float, stopped: bool) -> None:
        nonlocal equity, position, entry_costs
        assert position is not None and entry_ts is not None
        exit_cost = costs.fill_cost(price, position.shares)
        pnl = (price - position.entry_price) * position.shares - entry_costs - exit_cost
        equity += pnl
        trades.append(
            Trade(
                bars.symbol,
                entry_ts,
                bars.ts[i],
                position.entry_price,
                price,
                position.shares,
                entry_costs + exit_cost,
                pnl,
                stopped,
            )
        )
        position = None
        entry_costs = 0.0

    pending = None  # decision made on bar i, to be executed at bar i+1's open
    for i in range(n):
        # 1. Execute at this bar's open what was decided on the previous bar.
        if pending is not None:
            if isinstance(pending, Enter) and position is None:
                entry = float(bars.open[i])
                if pending.stop < entry:  # a gap below the stop voids the setup
                    sizing = size_from_stop(equity, entry, pending.stop, risk_fraction)
                    if sizing.shares > 0:
                        entry_costs = costs.fill_cost(entry, sizing.shares)
                        position = Position(entry, pending.stop, sizing.shares, i)
                        entry_ts = bars.ts[i]
            elif isinstance(pending, Exit) and position is not None:
                close_out(i, float(bars.open[i]), stopped=False)
            pending = None

        # 2. Resting stop: a gap through the stop fills at the open, else at the stop.
        if position is not None and float(bars.low[i]) <= position.stop:
            fill = min(float(bars.open[i]), position.stop)
            close_out(i, fill, stopped=True)

        # 3. Mark to market.
        if position is not None:
            unrealized = (float(bars.close[i]) - position.entry_price) * position.shares
            curve[i] = equity + unrealized - entry_costs
        else:
            curve[i] = equity

        # 4. Ask the strategy, showing it only history through bar i.
        if i >= strategy.warmup and i < n - 1:
            decision = strategy.on_bar(bars.upto(i), position)
            if isinstance(decision, Hold) and position is not None:
                if decision.stop is not None and decision.stop > position.stop:
                    position = Position(
                        position.entry_price,
                        decision.stop,
                        position.shares,
                        position.entry_index,
                    )
            elif isinstance(decision, Enter | Exit):
                pending = decision

    # Close any open position at the final close so the report is fully realized.
    if position is not None:
        close_out(n - 1, float(bars.close[n - 1]), stopped=False)
        curve[n - 1] = equity

    return Result(bars.symbol, curve, trades)
