from __future__ import annotations

import numpy as np
import pytest

from keel.alpaca import AlpacaError, _bars_from_rows, credentials, save_csv


def test_bars_from_rows_builds_valid_bars():
    rows = [
        {"t": "2024-01-02T14:30:00Z", "o": 10, "h": 11, "l": 9.5, "c": 10.5, "v": 100},
        {"t": "2024-01-02T14:31:00Z", "o": 10.5, "h": 12, "l": 10.4, "c": 11.9, "v": 200},
    ]
    bars = _bars_from_rows("AAPL", rows)
    assert bars.symbol == "AAPL"
    assert len(bars) == 2
    assert np.isclose(bars.close[-1], 11.9)


def test_bars_from_rows_empty_raises():
    with pytest.raises(AlpacaError, match="no bars"):
        _bars_from_rows("AAPL", [])


def test_credentials_missing_raises(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    with pytest.raises(AlpacaError, match="ALPACA_API_KEY"):
        credentials()


def test_save_csv_roundtrips_through_loader(tmp_path):
    from keel.data import load_csv

    rows = [
        {"t": "2024-01-02T14:30:00Z", "o": 10, "h": 11, "l": 9.5, "c": 10.5, "v": 100},
        {"t": "2024-01-02T14:31:00Z", "o": 10.5, "h": 12, "l": 10.4, "c": 11.9, "v": 200},
    ]
    bars = _bars_from_rows("AAPL", rows)
    path = save_csv(bars, tmp_path)
    reloaded = load_csv(path)
    assert len(reloaded) == 2
    assert np.isclose(reloaded.close[-1], 11.9)
