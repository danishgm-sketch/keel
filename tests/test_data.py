from __future__ import annotations

import numpy as np
import pytest

from conftest import make_bars
from keel.data import Bars, DataError, load_csv


def test_valid_bars_construct(trending_bars):
    assert len(trending_bars) == 400


def test_non_ascending_timestamps_rejected():
    b = make_bars([1.0, 2.0, 3.0])
    ts = b.ts.copy()
    ts[2] = ts[1]
    with pytest.raises(DataError, match="ascending"):
        Bars(b.symbol, ts, b.open, b.high, b.low, b.close, b.volume)


def test_non_positive_price_rejected():
    b = make_bars([1.0, 2.0, 3.0])
    close = b.close.copy()
    close[1] = 0.0
    with pytest.raises(DataError, match="non-positive"):
        Bars(b.symbol, b.ts, b.open, b.high, b.low, close, b.volume)


def test_high_below_low_rejected():
    b = make_bars([1.0, 2.0, 3.0])
    high = b.high.copy()
    high[1] = b.low[1] - 0.5
    with pytest.raises(DataError, match="high < low"):
        Bars(b.symbol, b.ts, b.open, high, b.low, b.close, b.volume)


def test_upto_contains_no_future():
    b = make_bars(list(range(1, 51)))
    view = b.upto(9)
    assert len(view) == 10
    assert view.ts[-1] == b.ts[9]


def test_load_csv_roundtrip(tmp_path):
    p = tmp_path / "abc.csv"
    p.write_text(
        "date,open,high,low,close,volume\n"
        "2024-01-02,10,11,9.5,10.5,100\n"
        "2024-01-03,10.5,12,10.4,11.9,200\n"
    )
    bars = load_csv(p)
    assert bars.symbol == "abc"
    assert len(bars) == 2
    assert np.isclose(bars.close[1], 11.9)
