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
