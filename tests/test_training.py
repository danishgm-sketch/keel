from __future__ import annotations

import json

from keel.knowledge import IDENTITY, system_context
from keel.training import (
    append_memory,
    distill_lessons,
    export_dataset,
    grade,
    read_memory,
    run_training,
    write_modelfile,
)


def _mem(data_dir, equity, posture, regime="range"):
    append_memory(
        data_dir,
        {"equity": str(equity), "regime": regime, "has_proven_edge": False},
        {"risk_posture": posture, "regime": regime, "favor": [], "avoid": [], "rationale": "x"},
    )


# --- constitution / context memory ---
def test_system_context_is_all_keel():
    ctx = system_context("/nonexistent")
    assert "Keel-Brain" in ctx and "improve keel" in ctx.lower()
    assert "rsi2" in ctx and "walk-forward" in ctx.lower()
    # the honesty spine is baked in
    assert "risk sizing is a constant" in ctx.lower()
    assert ctx.lower().count("keel") >= 5  # its whole world is Keel


def test_lessons_fold_into_context(tmp_path):
    (tmp_path / "brain_lessons.md").write_text("- defensive worked in volatile regimes\n")
    ctx = system_context(tmp_path)
    assert "defensive worked in volatile regimes" in ctx


# --- memory ---
def test_memory_roundtrip(tmp_path):
    _mem(tmp_path, 100000, "normal")
    _mem(tmp_path, 101000, "normal")
    rows = read_memory(tmp_path)
    assert len(rows) == 2
    assert rows[-1]["briefing"]["equity"] == "101000"


# --- grading by measured outcome ---
def test_grade_rewards_correct_calls(tmp_path):
    _mem(tmp_path, 100000, "normal")  # then equity rises -> normal was right
    _mem(tmp_path, 102000, "defensive")  # then equity falls -> defensive was right
    _mem(tmp_path, 99000, "normal")  # (terminal; no successor)
    graded = grade(tmp_path)
    assert len(graded) == 2
    assert graded[0]["good"] is True and graded[0]["reward"] > 0
    assert graded[1]["good"] is True and graded[1]["reward"] > 0


def test_grade_penalises_wrong_calls(tmp_path):
    _mem(tmp_path, 100000, "normal")  # equity falls after 'normal' -> wrong
    _mem(tmp_path, 97000, "normal")
    graded = grade(tmp_path)
    assert graded[0]["good"] is False and graded[0]["reward"] < 0


# --- distill + export + modelfile ---
def test_distill_writes_lessons(tmp_path):
    _mem(tmp_path, 100000, "normal")
    _mem(tmp_path, 101000, "normal")
    text = distill_lessons(tmp_path, grade(tmp_path))
    assert "past calls" in text
    assert (tmp_path / "brain_lessons.md").is_file()


def test_export_dataset_only_good_pairs(tmp_path):
    _mem(tmp_path, 100000, "normal")  # good
    _mem(tmp_path, 102000, "normal")  # good
    _mem(tmp_path, 99000, "normal")  # this one graded bad (fell after)
    graded = grade(tmp_path)
    path, n = export_dataset(tmp_path, graded)
    lines = path.read_text().strip().splitlines()
    assert n == len(lines)
    rec = json.loads(lines[0])
    assert rec["messages"][0]["content"] == IDENTITY
    assert {"system", "user", "assistant"} == {m["role"] for m in rec["messages"]}


def test_modelfile_bakes_keel_constitution(tmp_path):
    path, cmd = write_modelfile(tmp_path, base_model="qwen3")
    text = path.read_text()
    assert text.startswith("FROM qwen3")
    assert "SYSTEM" in text and "Keel-Brain" in text
    assert "ollama create keel-brain" in cmd


def test_run_training_end_to_end(tmp_path):
    for eq, p in [(100000, "normal"), (101000, "defensive"), (100500, "normal")]:
        _mem(tmp_path, eq, p)
    s = run_training(tmp_path)
    assert s["graded"] >= 1
    assert (tmp_path / "brain_finetune.jsonl").is_file()
    assert (tmp_path / "Modelfile.keel-brain").is_file()
    assert (tmp_path / "brain_lessons.md").is_file()
