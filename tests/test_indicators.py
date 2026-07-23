from __future__ import annotations

import numpy as np

from keel.indicators import atr, ema, rsi, session_dates, session_last_mask


def test_ema_tracks_and_is_causal():
    v = np.array([1.0, 2, 3, 4, 5])
    e = ema(v, span=3)
    assert e[0] == 1.0
    assert np.all(np.diff(e) > 0)  # rising input -> rising ema
    assert e[-1] < v[-1]  # ema lags a rising series


def test_rsi_bounds_and_extremes():
    up = np.arange(1, 60, dtype=float)
    r = rsi(up, period=14)
    assert np.nanmax(r) <= 100.0 and np.nanmin(r) >= 0.0
    assert r[-1] > 99.0  # monotonic up => RSI pinned near 100


def test_rsi_short_period_oscillates():
    x = 100 + np.tile([0, 1, -1, 2, -2], 20).astype(float).cumsum() * 0.0
    x = 100 + np.sin(np.linspace(0, 20 * np.pi, 200))
    r = rsi(x, period=2)
    valid = r[~np.isnan(r)]
    assert valid.min() < 20 and valid.max() > 80  # fires both oversold and overbought


def test_atr_positive_after_warmup():
    n = 50
    rng = np.random.default_rng(0)
    c = 100 + np.cumsum(rng.normal(0, 1, n))
    h, lo = c + 1, c - 1
    a = atr(h, lo, c, period=14)
    assert np.all(np.isnan(a[:14]))
    assert np.all(a[15:] > 0)


def test_session_last_mask():
    ts = np.array(
        ["2022-01-03T09:30", "2022-01-03T09:31", "2022-01-04T09:30", "2022-01-04T09:31"],
        dtype="datetime64[s]",
    )
    mask = session_last_mask(ts)
    assert list(mask) == [False, True, False, True]
    assert len(set(session_dates(ts).tolist())) == 2
