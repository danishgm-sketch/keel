from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np

from keel.data import Bars


class FakeBroker:
    def __init__(self, is_open: bool = True, equity: float = 100_000.0):
        self.is_open = is_open
        self.equity = equity
        self.positions: dict[str, int] = {}
        self.orders: list = []
        self.cancelled = False
        self.flattened = False

    def get_account(self):
        e = str(self.equity)
        return {"equity": e, "cash": e, "buying_power": e}

    def get_clock(self):
        close = (datetime.now(UTC) + timedelta(hours=3)).isoformat()
        return {"is_open": self.is_open, "next_close": close}

    def list_positions(self):
        return [
            {
                "symbol": s,
                "qty": str(q),
                "avg_entry_price": "100",
                "unrealized_pl": "0",
                "market_value": str(q * 100),
            }
            for s, q in self.positions.items()
        ]

    def submit_order(self, symbol, qty, side, **kw):
        self.orders.append((symbol, qty, side))
        if side == "buy":
            self.positions[symbol] = qty
        return {"id": "fake"}

    def close_position(self, symbol):
        self.positions.pop(symbol, None)
        return {}

    def close_all_positions(self):
        self.positions.clear()
        self.flattened = True
        return []

    def cancel_all_orders(self):
        self.cancelled = True
        return []


def entry_bars(symbol: str = "AAA") -> Bars:
    """A steady uptrend with a sharp dip on the final bar — RSI-2 oversold inside
    an uptrend, so Rsi2Reversion will signal an entry on the last bar."""
    n = 260
    c = 100 * np.exp(np.cumsum(np.full(n, 0.002)))
    c[-1] = c[-2] * 0.96
    o = np.concatenate([[c[0]], c[:-1]])
    hi = np.maximum(o, c) * 1.001
    lo = np.minimum(o, c) * 0.999
    ts = np.datetime64("2024-01-02T10:00", "s") + np.arange(n) * np.timedelta64(300, "s")
    return Bars(symbol, ts, o, hi, lo, c, np.full(n, 1000.0))
