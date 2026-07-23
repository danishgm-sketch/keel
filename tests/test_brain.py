from __future__ import annotations

from keel.brain import (
    AiBrain,
    apply_posture,
    parse_recommendation,
    run_brain_cycle,
    situational_briefing,
)


class FakeLLM:
    name = "fake"

    def __init__(self, reply):
        self.reply = reply

    def complete(self, prompt, system=""):
        return self.reply


def test_parse_recommendation_validates_and_defaults():
    rec = parse_recommendation(
        'noise {"regime":"trend","risk_posture":"aggressive",'
        '"favor":["rsi2","bogus"],"avoid":["swing"],"rationale":"x"} tail'
    )
    assert rec["risk_posture"] == "defensive"  # invalid posture -> safe default
    assert rec["favor"] == ["rsi2"]  # unknown strategy dropped
    assert rec["avoid"] == ["swing"]
    assert rec["regime"] == "trend"


def test_parse_recommendation_garbage_is_defensive():
    rec = parse_recommendation("the model rambled with no json")
    assert rec["risk_posture"] == "defensive"
    assert rec["favor"] == [] and rec["avoid"] == []


def test_apply_posture_only_tightens():
    assert apply_posture(8, 30, "normal") == (8, 30)
    assert apply_posture(8, 30, "defensive") == (4, 15)
    # never raises risk, never below 1
    assert apply_posture(1, 1, "defensive") == (1, 1)


def test_brain_reason_with_fake_llm():
    llm = FakeLLM(
        '{"regime":"range","risk_posture":"normal","favor":["rsi2"],'
        '"avoid":[],"rationale":"choppy tape favors mean reversion"}'
    )
    rec = AiBrain(llm).reason({"has_proven_edge": True})
    assert rec["risk_posture"] == "normal"
    assert rec["favor"] == ["rsi2"]


def test_brain_reason_survives_llm_error():
    class Boom:
        name = "boom"

        def complete(self, *a, **k):
            raise RuntimeError("model down")

    rec = AiBrain(Boom()).reason({})
    assert rec["risk_posture"] == "defensive"  # errors fail safe


def test_situational_briefing_reads_state(tmp_path):
    (tmp_path / "edge_ledger.jsonl").write_text('{"beats_luck": false, "pvalue": 1.0}\n')
    status = {
        "account": {"equity": "100000"},
        "positions": [{"symbol": "AAPL"}],
        "candidates": ["AAPL", "MSFT"],
        "universe_size": 5000,
        "last": {"market_open": True, "trades_today": 3},
    }
    b = situational_briefing(tmp_path, status)
    assert b["open_positions"] == 1
    assert b["universe_size"] == 5000
    assert b["has_proven_edge"] is False


def test_run_brain_cycle_without_llm_is_available_false(tmp_path):
    result = run_brain_cycle(tmp_path, status={}, llm=None)
    # no provider configured in the test env -> gracefully unavailable, defensive
    assert result["available"] is False
    assert result["recommendation"]["risk_posture"] == "defensive"
