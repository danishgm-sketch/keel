"""The training protocol — the brain learns to improve Keel from its own results.

The loop, all grounded in measured outcomes (never vibes):

1. **Remember.** Every brain decision (the state it saw + what it recommended)
   is appended to `brain_memory.jsonl`.
2. **Grade.** Each past decision is scored by what actually happened next: did
   equity rise when it said 'normal', or fall when it said 'defensive'? Good
   calls get a positive reward, bad calls negative. This is the honest training
   signal.
3. **Distill.** The graded record is summarized into `brain_lessons.md`, which is
   folded back into the model's constitution — so next time it reasons with what
   it has learned. Context-level self-improvement, no GPU required.
4. **Export (optional weight training).** Positively-graded (state -> decision)
   pairs are written as a chat fine-tune dataset, and an Ollama `Modelfile` bakes
   the Keel-only constitution into a custom local model (`keel-brain`). Run it
   when you want an actually-fine-tuned model; the running system improves
   without it via steps 1-3.

Nothing here can touch risk sizing or invent a strategy — it only makes the
brain's *judgement* better at serving Keel.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from keel.knowledge import IDENTITY, LESSONS_FILE, system_context

MEMORY_FILE = "brain_memory.jsonl"
DATASET_FILE = "brain_finetune.jsonl"
MODELFILE = "Modelfile.keel-brain"


# --- 1. remember ---
def append_memory(data_dir: str | Path, briefing: dict, recommendation: dict) -> None:
    row = {
        "ts": datetime.now(UTC).isoformat(),
        "briefing": briefing,
        "recommendation": recommendation,
    }
    with (Path(data_dir) / MEMORY_FILE).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def read_memory(data_dir: str | Path, n: int | None = None) -> list[dict]:
    p = Path(data_dir) / MEMORY_FILE
    if not p.is_file():
        return []
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return rows[-n:] if n else rows


def _equity(row: dict) -> float | None:
    e = (row.get("briefing") or {}).get("equity")
    try:
        return float(e)
    except (TypeError, ValueError):
        return None


# --- 2. grade by measured outcome ---
def grade(data_dir: str | Path) -> list[dict]:
    """Score each past decision by the equity move that followed it. A 'normal'
    call is good if equity rose; a 'defensive' call is good if it fell (it saved
    exposure). Only rows with a numeric equity and a successor are graded."""
    rows = read_memory(data_dir)
    graded = []
    for cur, nxt in zip(rows, rows[1:], strict=False):
        e0, e1 = _equity(cur), _equity(nxt)
        if e0 is None or e1 is None or e0 == 0:
            continue
        delta = (e1 - e0) / abs(e0)
        posture = (cur.get("recommendation") or {}).get("risk_posture", "defensive")
        up = delta > 0
        good = (posture == "normal" and up) or (posture == "defensive" and not up)
        graded.append(
            {
                "briefing": cur.get("briefing", {}),
                "recommendation": cur.get("recommendation", {}),
                "equity_delta": round(delta, 5),
                "reward": round((1 if good else -1) * min(1.0, abs(delta) * 20 + 0.1), 3),
                "good": good,
            }
        )
    return graded


# --- 3. distill lessons back into context ---
def distill_lessons(data_dir: str | Path, graded: list[dict]) -> str:
    if not graded:
        text = "- Not enough graded history yet. Stay defensive until edge is proven."
    else:
        total = len(graded)
        good = sum(1 for g in graded if g["good"])
        by_posture: dict[str, list[bool]] = {}
        by_regime: dict[str, list[bool]] = {}
        for g in graded:
            rec = g["recommendation"]
            by_posture.setdefault(rec.get("risk_posture", "?"), []).append(g["good"])
            by_regime.setdefault(g["briefing"].get("regime", "?"), []).append(g["good"])
        lines = [f"- Overall: {good}/{total} of your past calls were right by outcome."]
        for p, hits in by_posture.items():
            lines.append(f"- '{p}' posture was right {sum(hits)}/{len(hits)} times.")
        for r, hits in by_regime.items():
            if r != "?":
                lines.append(f"- In '{r}' regime you were right {sum(hits)}/{len(hits)} times.")
        lines.append("- Keep pressing what graded well; stay defensive when edge is unproven.")
        text = "\n".join(lines)
    (Path(data_dir) / LESSONS_FILE).write_text(text + "\n", encoding="utf-8")
    return text


# --- 4. export for optional weight fine-tuning ---
def export_dataset(data_dir: str | Path, graded: list[dict]) -> tuple[Path, int]:
    """Write positively-graded (state -> decision) pairs as a chat fine-tune
    dataset (JSONL). These are the examples of the brain judging Keel *well*."""
    path = Path(data_dir) / DATASET_FILE
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for g in graded:
            if not g["good"]:
                continue
            f.write(
                json.dumps(
                    {
                        "messages": [
                            {"role": "system", "content": IDENTITY},
                            {"role": "user", "content": json.dumps(g["briefing"])},
                            {"role": "assistant", "content": json.dumps(g["recommendation"])},
                        ]
                    }
                )
                + "\n"
            )
            n += 1
    return path, n


def write_modelfile(data_dir: str | Path, base_model: str = "qwen3") -> tuple[Path, str]:
    """Bake the Keel-only constitution (+ learned lessons) into an Ollama
    Modelfile, so `ollama create keel-brain` yields a model that knows only Keel."""
    context = system_context(data_dir).replace('"""', "'''")
    path = Path(data_dir) / MODELFILE
    path.write_text(
        f'FROM {base_model}\nPARAMETER temperature 0.3\nSYSTEM """{context}"""\n',
        encoding="utf-8",
    )
    return path, f"ollama create keel-brain -f {path}"


def run_training(data_dir: str | Path, base_model: str = "qwen3") -> dict:
    graded = grade(data_dir)
    distill_lessons(data_dir, graded)
    dataset_path, n_examples = export_dataset(data_dir, graded)
    modelfile_path, create_cmd = write_modelfile(data_dir, base_model)
    good = sum(1 for g in graded if g["good"])
    return {
        "graded": len(graded),
        "good": good,
        "dataset": str(dataset_path),
        "examples": n_examples,
        "modelfile": str(modelfile_path),
        "create_cmd": create_cmd,
        "set_model": "set KEEL_OLLAMA_MODEL=keel-brain to run the trained model",
    }
