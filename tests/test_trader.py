from __future__ import annotations

from fakes import FakeBroker, entry_bars
from keel.config import Config
from keel.journal import Journal
from keel.strategies import Rsi2Reversion
from keel.trader import LiveTrader


def _trader(tmp_path, broker, armed=True, **cfg):
    config = Config(watchlist=["AAA"], strategy="rsi2", **cfg).clamp()
    journal = Journal(tmp_path / "j.jsonl")
    return LiveTrader(
        broker=broker,
        data_source=lambda s: entry_bars(s),
        make_strategy=lambda: Rsi2Reversion(),
        config=config,
        journal=journal,
        armed=armed,
    )


def test_armed_bot_enters_on_signal(tmp_path):
    broker = FakeBroker(is_open=True)
    t = _trader(tmp_path, broker)
    t.tick()
    assert "AAA" in broker.positions
    assert broker.orders and broker.orders[0][2] == "buy"
    assert any(e["kind"] == "entry" for e in t.journal.today())


def test_disarmed_bot_does_nothing(tmp_path):
    broker = FakeBroker(is_open=True)
    t = _trader(tmp_path, broker, armed=False)
    t.tick()
    assert broker.positions == {}
    assert broker.orders == []


def test_no_trading_when_market_closed(tmp_path):
    broker = FakeBroker(is_open=False)
    t = _trader(tmp_path, broker)
    status = t.tick()
    assert status["market_open"] is False
    assert broker.orders == []


def test_kill_flattens_and_disarms(tmp_path):
    broker = FakeBroker(is_open=True)
    t = _trader(tmp_path, broker)
    t.tick()
    assert broker.positions
    result = t.kill()
    assert result["flattened"] and result["cancelled"]
    assert broker.flattened and broker.cancelled
    assert t.armed is False
    assert broker.positions == {}


def test_daily_new_trade_throttle(tmp_path):
    broker = FakeBroker(is_open=True)
    t = _trader(tmp_path, broker, max_new_per_day=1)
    t.journal.write("entry", symbol="ZZZ", shares=1, price=1, stop=0)  # already 1 today
    t.tick()
    assert "AAA" not in broker.positions  # throttle blocked the new entry
