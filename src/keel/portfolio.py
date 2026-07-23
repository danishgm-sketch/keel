"""Multi-symbol, multi-position backtest engine — the high-turnover book.

One strategy instance per symbol runs over a shared clock. On any bar the
strategy proposes; the *portfolio* decides which proposals to take given its
throttles (max concurrent positions, max new trades per day) and its capital
(no leverage — deployed notional never exceeds equity). This is what turns a
per-symbol signal into "dozens of trades a day across a watchlist" without being
HFT: decisions are per-bar, fills are at the *next* bar's open, and nothing is
sub-bar.

Discipline carried over from the single-symbol engine:
- no look-ahead: a strategy sees only ``bars.upto(i)``; fills happen at i+1 open
- resting stops fill at the stop, or worse on a gap
- costs are charged on every fill
- intraday-lane positions are force-flattened at the session close
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from keel.costs import CostModel
from keel.data import Bars
from keel.indicators import session_dates, session_last_mask
from keel.risk import DEFAULT_RISK_FRACTION, size_from_stop
from keel.strategy import Enter, Exit, Hold, Position, Strategy


@dataclass(frozen=True)
class PortfolioTrade:
    symbol: str
    lane: str
    entry_ts: np.datetime64
    exit_ts: np.datetime64
    entry_price: float
    exit_price: float
    shares: int
    costs: float
    pnl: float  # net of costs
    reason: str  # "signal" | "stop" | "session_flat" | "eod"


@dataclass
class PortfolioResult:
    daily_dates: np.ndarray  # datetime64[D], one per session
    daily_equity: np.ndarray  # equity marked to market at each session close
    trades: list[PortfolioTrade] = field(default_factory=list)
    starting_equity: float = 0.0

    @property
    def returns(self) -> np.ndarray:
        eq = self.daily_equity
        return np.diff(eq) / eq[:-1] if len(eq) > 1 else np.zeros(0)

    @property
    def total_return(self) -> float:
        eq = self.daily_equity
        return float(eq[-1] / eq[0] - 1) if len(eq) else 0.0

    @property
    def trades_per_day(self) -> float:
        n_days = len(self.daily_dates)
        return len(self.trades) / n_days if n_days else 0.0

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        return sum(1 for t in self.trades if t.pnl > 0) / len(self.trades)

    @property
    def total_costs(self) -> float:
        return sum(t.costs for t in self.trades)


@dataclass
class _Pos:
    entry_price: float
    stop: float
    shares: int
    entry_cost: float
    lane: str
    entry_ts: np.datetime64


def run_portfolio(
    data: dict[str, Bars],
    make_strategy: Callable[[], Strategy],
    starting_equity: float = 100_000.0,
    risk_fraction: float = DEFAULT_RISK_FRACTION,
    max_positions: int = 10,
    max_new_per_day: int = 20,
    costs: CostModel | None = None,
) -> PortfolioResult:
    if costs is None:
        costs = CostModel()
    symbols = sorted(data)
    strat = {s: make_strategy() for s in symbols}
    last_mask = {s: session_last_mask(data[s].ts) for s in symbols}

    # Global event stream: (timestamp, symbol, local_index), time-then-symbol order.
    events: list[tuple[int, str, int]] = []
    for s in symbols:
        ts_int = data[s].ts.astype("int64")
        events.extend((int(t), s, i) for i, t in enumerate(ts_int))
    events.sort(key=lambda e: (e[0], e[1]))

    realized_equity = starting_equity
    deployed = 0.0
    positions: dict[str, _Pos] = {}
    pending: dict[str, object] = {}
    last_close: dict[str, float] = {}
    trades: list[PortfolioTrade] = []
    daily_dates: list[np.datetime64] = []
    daily_equity: list[float] = []

    def mtm() -> float:
        unreal = 0.0
        for s, p in positions.items():
            px = last_close.get(s, p.entry_price)
            unreal += (px - p.entry_price) * p.shares - p.entry_cost
        return realized_equity + unreal

    def close(s: str, price: float, ts: np.datetime64, reason: str) -> None:
        nonlocal realized_equity, deployed
        p = positions.pop(s)
        exit_cost = costs.fill_cost(price, p.shares)
        pnl = (price - p.entry_price) * p.shares - p.entry_cost - exit_cost
        realized_equity += pnl
        deployed -= p.entry_price * p.shares
        trades.append(
            PortfolioTrade(
                s,
                p.lane,
                p.entry_ts,
                ts,
                p.entry_price,
                price,
                p.shares,
                p.entry_cost + exit_cost,
                pnl,
                reason,
            )
        )

    cur_date: np.datetime64 | None = None
    new_today = 0

    for _ts_int, s, i in events:
        bars = data[s]
        ts = bars.ts[i]
        date = ts.astype("datetime64[D]")
        if cur_date is None:
            cur_date = date
        elif date != cur_date:
            daily_dates.append(cur_date)
            daily_equity.append(mtm())
            cur_date = date
            new_today = 0

        # 1. Execute the decision made on this symbol's previous bar, at this open.
        decision = pending.pop(s, None)
        open_px = float(bars.open[i])
        if isinstance(decision, Enter) and s not in positions:
            room = len(positions) < max_positions and new_today < max_new_per_day
            if room and decision.stop < open_px:
                sizing = size_from_stop(realized_equity, open_px, decision.stop, risk_fraction)
                notional = sizing.shares * open_px
                if sizing.shares > 0 and deployed + notional <= realized_equity:
                    positions[s] = _Pos(
                        open_px,
                        decision.stop,
                        sizing.shares,
                        costs.fill_cost(open_px, sizing.shares),
                        getattr(strat[s], "lane", "swing"),
                        ts,
                    )
                    deployed += notional
                    new_today += 1
        elif isinstance(decision, Exit) and s in positions:
            close(s, open_px, ts, "signal")

        # 2. Resting stop (long-only): gap through the stop fills at the open.
        if s in positions and float(bars.low[i]) <= positions[s].stop:
            fill = min(open_px, positions[s].stop)
            close(s, fill, ts, "stop")

        # 3. Session flatten for intraday-lane positions.
        if s in positions and positions[s].lane == "intraday" and last_mask[s][i]:
            close(s, float(bars.close[i]), ts, "session_flat")

        last_close[s] = float(bars.close[i])

        # 4. Ask the strategy (history through i only; never on the final bar).
        if i >= strat[s].warmup and i < len(bars) - 1:
            pos_view = None
            if s in positions:
                p = positions[s]
                pos_view = Position(p.entry_price, p.stop, p.shares, i)
            d = strat[s].on_bar(bars.upto(i), pos_view)
            if isinstance(d, Hold) and s in positions:
                if d.stop is not None and d.stop > positions[s].stop:
                    positions[s].stop = d.stop
            elif isinstance(d, Enter | Exit):
                pending[s] = d

    # Final session mark + close everything still open at its last seen close.
    if cur_date is not None:
        for s in list(positions):
            close(s, last_close[s], data[s].ts[-1], "eod")
        daily_dates.append(cur_date)
        daily_equity.append(mtm())

    return PortfolioResult(
        np.array(daily_dates, dtype="datetime64[D]"),
        np.array(daily_equity, dtype=float),
        trades,
        starting_equity,
    )


def load_dir(path) -> dict[str, Bars]:
    """Load every ``*.csv`` in a directory as one symbol each (filename = symbol)."""
    from pathlib import Path

    from keel.data import load_csv

    out: dict[str, Bars] = {}
    for p in sorted(Path(path).glob("*.csv")):
        out[p.stem] = load_csv(p)
    return out


# session_dates re-exported for callers building intraday fixtures/reports.
__all__ = ["PortfolioResult", "PortfolioTrade", "run_portfolio", "load_dir", "session_dates"]
