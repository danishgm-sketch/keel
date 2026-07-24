from __future__ import annotations

import csv
import json

from conftest import make_intraday
from keel.briefing import briefing
from keel.synthesize import parse_specs, propose_ensembles, spec_to_strategy


def _data_dir(tmp_path, n=3, sessions=8):
    for i in range(n):
        b = make_intraday(f"S{i}", n_sessions=sessions, seed=i)
        with (tmp_path / f"S{i}.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "open", "high", "low", "close", "volume"])
            for k in range(len(b)):
                w.writerow([str(b.ts[k]), b.open[k], b.high[k], b.low[k], b.close[k], 1000])
    return tmp_path


# --- synthesize (safe self-writing) ---
def test_parse_specs_validates_and_clamps():
    text = (
        'junk [{"weights":{"rsi2":2.0,"bogus":9,"momentum":-1},"entry":0.7,"exit":0.4},'
        '{"weights":{"nope":1}}]'
    )
    specs = parse_specs(text)
    assert len(specs) == 1  # second spec has no known signals -> dropped
    w = specs[0]["weights"]
    assert "bogus" not in w and "momentum" not in w  # unknown + negative dropped
    assert w["rsi2"] == 2.0
    assert specs[0]["exit"] < specs[0]["entry"]


def test_spec_becomes_a_gradeable_strategy():
    spec = {"weights": {"rsi2": 1.0, "momentum": 0.5}, "entry": 0.5, "exit": 0.3}
    strat = spec_to_strategy(spec)
    assert strat.warmup > 0
    assert hasattr(strat, "on_bar")


def test_propose_ensembles_no_llm():
    assert propose_ensembles(None, "ctx") == []


def test_propose_ensembles_parses_model_output():
    class LLM:
        def complete(self, *a, **k):
            return '[{"weights":{"breakout":1.0,"lowvol":0.5},"entry":0.6,"exit":0.25}]'

    specs = propose_ensembles(LLM(), "test", n=1)
    assert specs and "breakout" in specs[0]["weights"]


# --- certify (gate as a service) ---
def test_certify_unknown_target(tmp_path):
    from keel.certify import certify

    assert "error" in certify(tmp_path, "nope")


def test_certify_returns_honest_verdict(tmp_path):
    from keel.certify import certify

    _data_dir(tmp_path, n=3, sessions=8)  # too little data -> not certified, no crash
    c = certify(tmp_path, "rsi2", train=20, test=10)
    assert "certified" in c
    assert c["certified"] is False


# --- briefing (the product moment) ---
def test_briefing_three_questions(tmp_path):
    _data_dir(tmp_path, n=2)
    (tmp_path / "edge_ledger.jsonl").write_text(
        json.dumps({"beats_luck": False, "pvalue": 1.0, "oos_sharpe": 0.0, "n_folds": 3}) + "\n"
    )
    b = briefing(tmp_path)
    assert "edge" in b and "activity" in b and "worries" in b
    assert "no proven edge" in b["edge"].lower()
