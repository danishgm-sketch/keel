"""The automated paper-trading loop — the part that runs by itself.

Each `tick` (called on a timer during market hours) it: reads the account and
live positions from the broker, pulls recent bars for each watchlist symbol,
asks the active strategy for a decision, and submits paper orders — sizing every
entry at the guarded risk fraction from its stop, respecting the turnover
throttles, enforcing stops, and flattening intraday names near the close.

Safety is first-class:
- `armed` gates all order submission; it starts however config says (paper only).
- `kill()` is the panic button: cancel every order and flatten every position.
- Nothing here can reach real money — see `keel.broker` (paper-only).

The broker is duck-typed (`Broker` protocol) so tests and dry-runs use a fake.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from keel.config import Config
from keel.data import Bars
from keel.journal import Journal
from keel.risk import size_from_stop
from keel.strategy import Enter, Exit, Position, Strategy


class Broker(Protocol):
    def get_account(self) -> dict: ...
    def get_clock(self) -> dict: ...
    def list_positions(self) -> list: ...
    def submit_order(self, symbol: str, qty: int, side: str, **kw) -> dict: ...
    def close_position(self, symbol: str) -> dict: ...
    def close_all_positions(self) -> list: ...
    def cancel_all_orders(self) -> list: ...


DataSource = Callable[[str], Bars | None]


@dataclass
class LiveTrader:
    broker: Broker
    data_source: DataSource
    make_strategy: Callable[[], Strategy]
    config: Config
    journal: Journal
    armed: bool = False
    stops: dict[str, float] = field(default_factory=dict)
    _last_error: str | None = None

    # --- control ---
    def arm(self) -> None:
        self.armed = True
        self.journal.write("armed")

    def disarm(self) -> None:
        self.armed = False
        self.journal.write("disarmed")

    def kill(self) -> dict:
        """Panic button: stop trading, cancel all orders, flatten everything."""
        self.armed = False
        result = {"cancelled": False, "flattened": False}
        try:
            self.broker.cancel_all_orders()
            result["cancelled"] = True
            self.broker.close_all_positions()
            result["flattened"] = True
        except Exception as e:  # never let the kill switch raise
            self._last_error = str(e)
        self.stops.clear()
        self.journal.write("kill", **result)
        return result

    # --- helpers ---
    def _new_today(self) -> int:
        return sum(1 for e in self.journal.today() if e.get("kind") == "entry")

    def _minutes_to_close(self, clock: dict) -> float:
        try:
            close = datetime.fromisoformat(clock["next_close"].replace("Z", "+00:00"))
            return (close - datetime.now(UTC)).total_seconds() / 60.0
        except Exception:
            return 999.0

    # --- the loop body ---
    def tick(self) -> dict:
        if not self.armed:
            return self.status(market_open=None, note="disarmed")
        try:
            clock = self.broker.get_clock()
        except Exception as e:
            self._last_error = str(e)
            return self.status(market_open=None, note=f"broker error: {e}")

        if not clock.get("is_open"):
            return self.status(market_open=False, note="market closed")

        account = self.broker.get_account()
        equity = float(account.get("equity", 0) or 0)
        positions = {p["symbol"]: p for p in self.broker.list_positions()}
        strat = self.make_strategy()
        flatten_soon = strat.session_flat and self._minutes_to_close(clock) <= max(
            2 * self.config.poll_seconds / 60.0, 5.0
        )
        new_today = self._new_today()
        actions = 0

        for sym in self.config.watchlist:
            held = sym in positions and float(positions[sym].get("qty", 0)) > 0
            if flatten_soon and held:
                self._exit(sym, "session_flat")
                actions += 1
                continue

            bars = self.data_source(sym)
            if bars is None or len(bars) <= strat.warmup:
                continue
            price = float(bars.close[-1])

            # enforce our stop first
            if held and sym in self.stops and price <= self.stops[sym]:
                self._exit(sym, "stop")
                actions += 1
                continue

            pos_view = None
            if held:
                avg = float(positions[sym].get("avg_entry_price", price))
                pos_view = Position(avg, self.stops.get(sym, 0.0), 1, len(bars) - 1)
            decision = strat.on_bar(bars, pos_view)

            if isinstance(decision, Enter) and not held:
                room = len(positions) < self.config.max_positions and (
                    new_today < self.config.max_new_per_day
                )
                if room and decision.stop < price:
                    shares = size_from_stop(
                        equity, price, decision.stop, self.config.risk_fraction
                    ).shares
                    if shares > 0:
                        self._enter(sym, shares, price, decision.stop)
                        positions[sym] = {"symbol": sym, "qty": str(shares)}
                        new_today += 1
                        actions += 1
            elif isinstance(decision, Exit) and held:
                self._exit(sym, "signal")
                actions += 1

        return self.status(market_open=True, note=f"{actions} actions", equity=equity)

    def _enter(self, symbol: str, shares: int, price: float, stop: float) -> None:
        self.broker.submit_order(symbol, shares, "buy")
        self.stops[symbol] = stop
        self.journal.write("entry", symbol=symbol, shares=shares, price=price, stop=stop)

    def _exit(self, symbol: str, reason: str) -> None:
        try:
            self.broker.close_position(symbol)
        except Exception as e:
            self._last_error = str(e)
        self.stops.pop(symbol, None)
        self.journal.write("exit", symbol=symbol, reason=reason)

    def status(self, market_open, note: str = "", equity: float | None = None) -> dict:
        return {
            "armed": self.armed,
            "market_open": market_open,
            "strategy": self.config.strategy,
            "watchlist": self.config.watchlist,
            "open_stops": dict(self.stops),
            "trades_today": self._new_today(),
            "equity": equity,
            "note": note,
            "last_error": self._last_error,
        }
