from __future__ import annotations

import numpy as np
import pytest

from keel.data import Bars


def make_bars(closes: list[float] | np.ndarray, symbol: str = "TEST") -> Bars:
    """Bars from a close series: open = previous close (first open = first
    close), high/low bracket both."""
    c = np.asarray(closes, dtype=float)
    o = np.concatenate([[c[0]], c[:-1]])
    hi = np.maximum(o, c) * 1.001
    lo = np.minimum(o, c) * 0.999
    ts = np.datetime64("2020-01-01", "s") + np.arange(len(c)) * np.timedelta64(86400, "s")
    return Bars(symbol, ts, o, hi, lo, c, np.full(len(c), 1000.0))


@pytest.fixture
def trending_bars() -> Bars:
    rng = np.random.default_rng(7)
    closes = 100 * np.exp(np.cumsum(rng.normal(0.002, 0.01, 400)))
    return make_bars(closes)


def make_intraday(
    symbol: str,
    n_sessions: int = 8,
    bars_per_session: int = 60,
    seed: int = 0,
    drift: float = 0.0004,
    osc: float = 0.012,
) -> Bars:
    """Synthetic intraday bars: gentle uptrend + within-session oscillation +
    noise, so short-term-oversold and breakout setups actually trigger. One bar
    per minute, sessions on consecutive weekdays."""
    rng = np.random.default_rng(seed)
    n = n_sessions * bars_per_session
    t = np.arange(n)
    phase = 2 * np.pi * (t % bars_per_session) / bars_per_session
    log_price = drift * t + osc * np.sin(phase) + np.cumsum(rng.normal(0, 0.0015, n))
    close = 100 * np.exp(log_price)
    o = np.concatenate([[close[0]], close[:-1]])
    hi = np.maximum(o, close) * (1 + np.abs(rng.normal(0, 0.0008, n)))
    lo = np.minimum(o, close) * (1 - np.abs(rng.normal(0, 0.0008, n)))
    ts = []
    day = np.datetime64("2022-01-03T09:30", "s")
    for k in range(n):
        session = k // bars_per_session
        bar = k % bars_per_session
        ts.append(day + session * np.timedelta64(1, "D") + bar * np.timedelta64(60, "s"))
    return Bars(symbol, np.array(ts, dtype="datetime64[s]"), o, hi, lo, close, np.full(n, 5000.0))
