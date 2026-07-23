from __future__ import annotations

import pytest

from keel.broker import LIVE_TRADING_ENABLED, PAPER_BASE, AlpacaBroker, BrokerError


def test_live_trading_is_disabled():
    assert LIVE_TRADING_ENABLED is False


def test_non_paper_endpoint_refused(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    with pytest.raises(BrokerError, match="PAPER"):
        AlpacaBroker(base_url="https://api.alpaca.markets")


def test_missing_keys_refused(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    with pytest.raises(BrokerError, match="ALPACA_API_KEY"):
        AlpacaBroker()


def test_constructs_with_keys_and_targets_paper(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    b = AlpacaBroker()
    assert b.base == PAPER_BASE
