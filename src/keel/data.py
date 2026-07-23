"""OHLCV bar container and CSV loading.

Bars are immutable column arrays validated at construction: strictly ascending
timestamps, equal lengths, positive prices, high >= low. Nothing downstream
needs to re-check these invariants.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import numpy as np


class DataError(ValueError):
    """Raised when input data violates a bar invariant."""


@dataclass(frozen=True)
class Bars:
    symbol: str
    ts: np.ndarray  # datetime64[s], strictly ascending
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray

    def __post_init__(self) -> None:
        n = len(self.ts)
        for name in ("open", "high", "low", "close", "volume"):
            if len(getattr(self, name)) != n:
                raise DataError(f"{self.symbol}: column '{name}' length != ts length")
        if n == 0:
            return
        if np.any(np.diff(self.ts.astype("int64")) <= 0):
            raise DataError(f"{self.symbol}: timestamps not strictly ascending")
        for name in ("open", "high", "low", "close"):
            if np.any(getattr(self, name) <= 0):
                raise DataError(f"{self.symbol}: non-positive price in '{name}'")
        if np.any(self.high < self.low):
            raise DataError(f"{self.symbol}: high < low")

    def __len__(self) -> int:
        return len(self.ts)

    def upto(self, i: int) -> Bars:
        """History through bar index i inclusive. This slice is the ONLY thing a
        strategy is ever shown; future bars are not present to be peeked at."""
        s = slice(0, i + 1)
        return Bars(
            self.symbol,
            self.ts[s],
            self.open[s],
            self.high[s],
            self.low[s],
            self.close[s],
            self.volume[s],
        )

    def tail(self, k: int) -> Bars:
        """The most recent k bars (for fast recent-form scoring)."""
        s = slice(max(0, len(self) - k), len(self))
        return Bars(
            self.symbol,
            self.ts[s],
            self.open[s],
            self.high[s],
            self.low[s],
            self.close[s],
            self.volume[s],
        )


def load_csv(path: str | Path, symbol: str | None = None) -> Bars:
    """Load bars from a CSV with columns: date,open,high,low,close,volume.

    `date` is ISO (YYYY-MM-DD or full timestamp). Rows must already be in
    chronological order; validation rejects anything else.
    """
    path = Path(path)
    ts, o, h, lo, c, v = [], [], [], [], [], []
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            raw = row["date"].strip()
            when = date.fromisoformat(raw) if len(raw) == 10 else datetime.fromisoformat(raw)
            ts.append(np.datetime64(when, "s"))
            o.append(float(row["open"]))
            h.append(float(row["high"]))
            lo.append(float(row["low"]))
            c.append(float(row["close"]))
            v.append(float(row.get("volume", 0) or 0))
    return Bars(
        symbol or path.stem,
        np.array(ts, dtype="datetime64[s]"),
        np.array(o),
        np.array(h),
        np.array(lo),
        np.array(c),
        np.array(v),
    )
