from __future__ import annotations

from fakes import FakeBroker, entry_bars
from keel.catalysts import _headlines_from_payload, news_digest
from keel.config import Config
from keel.journal import Journal
from keel.overlay import assess, parse_overlay
from keel.strategies import Rsi2Reversion
from keel.trader import LiveTrader


class FakeLLM:
    def __init__(self, reply):
        self.reply = reply

    def complete(self, prompt, system=""):
        return self.reply


# --- catalysts (news feed) ---
def test_headlines_group_by_symbol():
    payload = {
        "news": [
            {"headline": "AAPL beats earnings", "symbols": ["AAPL"]},
            {"headline": "Sector rally", "symbols": ["AAPL", "MSFT"]},
            {"headline": "", "symbols": ["NVDA"]},  # empty dropped
        ]
    }
    h = _headlines_from_payload(payload)
    assert h["AAPL"] == ["AAPL beats earnings", "Sector rally"]
    assert h["MSFT"] == ["Sector rally"]
    assert "NVDA" not in h


def test_news_digest_limits_per_symbol():
    h = {"AAPL": ["a", "b", "c", "d"]}
    assert news_digest(h, per_symbol=2)["AAPL"] == "a | b"


# --- overlay (the qualitative limb) is veto-only and bounded ---
def test_overlay_avoid_is_subset_of_candidates():
    text = '{"avoid":["AAPL","GHOST"],"notes":{"AAPL":"earnings tonight","GHOST":"x"}}'
    out = parse_overlay(text, candidates={"AAPL", "MSFT"})
    assert out["avoid"] == ["AAPL"]  # GHOST not a candidate -> dropped
    assert "GHOST" not in out["notes"]


def test_overlay_cannot_add_buys():
    # even if the model returns a 'buy' field, only 'avoid' is honoured
    text = '{"avoid":[],"buy":["AAPL"],"notes":{}}'
    out = parse_overlay(text, candidates={"AAPL"})
    assert out == {"avoid": [], "notes": {}}
    assert "buy" not in out


def test_assess_fails_safe_to_no_veto():
    class Boom:
        def complete(self, *a, **k):
            raise RuntimeError("news model down")

    assert assess(Boom(), {"AAPL": "news"}, {"AAPL"}) == {"avoid": [], "notes": {}}
    assert assess(None, {"AAPL": "news"}, {"AAPL"}) == {"avoid": [], "notes": {}}


def test_assess_parses_veto():
    llm = FakeLLM('{"avoid":["AAPL"],"notes":{"AAPL":"halted"}}')
    out = assess(llm, {"AAPL": "halt news"}, {"AAPL", "MSFT"})
    assert out["avoid"] == ["AAPL"]


# --- trader honours the veto ---
def test_blocklisted_symbol_gets_no_new_entry(tmp_path):
    broker = FakeBroker(is_open=True)
    config = Config(watchlist=["AAA"], strategy="rsi2").clamp()
    trader = LiveTrader(
        broker=broker,
        data_source=lambda s: entry_bars(s),
        make_strategy=lambda: Rsi2Reversion(),
        config=config,
        journal=Journal(tmp_path / "j.jsonl"),
        armed=True,
        blocklist={"AAA"},  # qualitative limb vetoed this name
    )
    trader.tick()
    assert "AAA" not in broker.positions  # veto held; no entry despite the signal
