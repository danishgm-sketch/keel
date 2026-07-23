"""Causal indicators: every value at index i uses only bars 0..i. No indicator
here can see the future, so no strategy built on them can either.

Plain numpy, aligned to the input length (leading positions are NaN until the
lookback is satisfied).
"""

from __future__ import annotations

import numpy as np


def ema(values: np.ndarray, span: int) -> np.ndarray:
    v = np.asarray(values, dtype=float)
    out = np.full(len(v), np.nan)
    if len(v) == 0:
        return out
    alpha = 2.0 / (span + 1.0)
    out[0] = v[0]
    for i in range(1, len(v)):
        out[i] = alpha * v[i] + (1 - alpha) * out[i - 1]
    return out


def rsi(values: np.ndarray, period: int) -> np.ndarray:
    """Wilder's RSI. Short periods (2-3) are the classic short-term
    mean-reversion signal and fire often."""
    v = np.asarray(values, dtype=float)
    out = np.full(len(v), np.nan)
    if len(v) <= period:
        return out
    delta = np.diff(v)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = gain[:period].mean()
    avg_loss = loss[:period].mean()
    for i in range(period, len(v)):
        g = gain[i - 1]
        loss_i = loss[i - 1]
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + loss_i) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else np.inf
        out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """Wilder's Average True Range — the volatility unit for stops and sizing."""
    h, lo, c = (np.asarray(x, dtype=float) for x in (high, low, close))
    n = len(c)
    out = np.full(n, np.nan)
    if n < 2:
        return out
    prev_close = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - lo, np.maximum(np.abs(h - prev_close), np.abs(lo - prev_close)))
    if n <= period:
        return out
    a = tr[1 : period + 1].mean()
    out[period] = a
    for i in range(period + 1, n):
        a = (a * (period - 1) + tr[i]) / period
        out[i] = a
    return out


def session_dates(ts: np.ndarray) -> np.ndarray:
    """Calendar date of each bar (the trading session it belongs to)."""
    return np.asarray(ts, dtype="datetime64[D]")


def session_last_mask(ts: np.ndarray) -> np.ndarray:
    """True on the last bar of each session — where an intraday position must
    be flattened."""
    d = session_dates(ts)
    if len(d) == 0:
        return np.zeros(0, dtype=bool)
    mask = np.empty(len(d), dtype=bool)
    mask[-1] = True
    mask[:-1] = d[:-1] != d[1:]
    return mask
