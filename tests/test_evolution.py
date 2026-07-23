from __future__ import annotations

import csv

from conftest import make_intraday
from keel.advisor import SCHEMA, parse_variants, propose_variants
from keel.config import Config, load_config, save_config
from keel.journal import Journal
from keel.llm import pick_provider, recommend_ollama_model
from keel.roster import active_factory, evolve
from keel.service import LiveService


def _data_dir(tmp_path, n=3, sessions=10):
    for i in range(n):
        b = make_intraday(f"S{i}", n_sessions=sessions, seed=i)
        with (tmp_path / f"S{i}.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "open", "high", "low", "close", "volume"])
            for k in range(len(b)):
                w.writerow([str(b.ts[k]), b.open[k], b.high[k], b.low[k], b.close[k], 1000])
    return tmp_path


# --- evolution / roster ---
def test_evolve_runs_and_writes_roster(tmp_path):
    _data_dir(tmp_path)
    summary = evolve(tmp_path, extra_variants=[("rsi2", {"entry_level": 8.0})])
    assert summary["n_variants"] == 11  # 10 base + 1 extra
    assert (tmp_path / "roster.json").is_file()
    # too little data to clear the gate honestly -> no champion, and that's correct
    for r in summary["variants"]:
        assert "survived" in r


def test_active_factory_defaults_without_champion(tmp_path):
    _data_dir(tmp_path)
    evolve(tmp_path)
    name, factory = active_factory(tmp_path, default_strategy="rsi2")
    assert name == "rsi2"
    assert factory() is not None


# --- advisor / schema ---
def test_parse_variants_validates_and_clamps():
    text = """junk before [
      {"strategy":"rsi2","params":{"entry_level":8,"exit_level":999}},
      {"strategy":"orb","params":{"or_bars":100}},
      {"strategy":"bogus","params":{"x":1}},
      {"strategy":"swing","params":{"fast":15,"mid":40,"slow":150}}
    ] junk after"""
    v = parse_variants(text)
    kinds = [s for s, _ in v]
    assert "bogus" not in kinds
    rsi = dict(v).get("rsi2")
    assert rsi and rsi["exit_level"] <= SCHEMA["rsi2"]["exit_level"][1]
    assert dict(v)["orb"]["or_bars"] <= SCHEMA["orb"]["or_bars"][1]


def test_propose_variants_handles_no_llm():
    assert propose_variants(None, "ctx") == []


# --- llm helpers (no network) ---
def test_recommend_model_scales_with_ram():
    assert "3b" in recommend_ollama_model(4)
    assert recommend_ollama_model(64).endswith("32b-instruct")


def test_pick_provider_none_when_nothing_available(monkeypatch):
    monkeypatch.setattr("keel.llm.OllamaProvider.available", staticmethod(lambda: False))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert pick_provider() is None


# --- config / journal / service ---
def test_config_roundtrip_and_clamp(tmp_path):
    cfg = Config(risk_fraction=0.5, max_positions=0, poll_seconds=1)
    save_config(tmp_path, cfg)
    back = load_config(tmp_path)
    assert back.risk_fraction <= 0.02
    assert back.max_positions >= 1
    assert back.poll_seconds >= 15


def test_journal_append_and_today(tmp_path):
    j = Journal(tmp_path / "j.jsonl")
    j.write("entry", symbol="AAA")
    j.write("exit", symbol="AAA", reason="stop")
    assert len(j.today()) == 2
    assert j.tail(1)[0]["kind"] == "exit"


def test_service_degrades_without_keys(tmp_path, monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    svc = LiveService(tmp_path)
    svc.start()
    status = svc.status()
    assert status["enabled"] is False
    assert status["broker_error"]
