"""The AI brain — a local open-source LLM woven into the whole system.

This is where Keel and an LLM become one program. Every cycle the brain builds a
*situational briefing* from the entire live state — account, open positions, the
decision journal, the edge ledger (does the system actually have an edge yet?),
the market regime, the candidate shortlist, the validated roster — and asks a
local reasoning model (Qwen3 / Llama via Ollama, or Claude/Gemini) to read the
situation and recommend a posture.

Crucially, its authority is bounded so intelligence never becomes recklessness:

- It may set risk posture to **defensive**, which only ever *reduces* throughput
  (fewer new trades, fewer concurrent positions). It can never loosen risk.
- It may *favor* or *avoid* strategies, but only ones already in the validated
  playbook — it cannot invent an unproven edge or touch position sizing.
- Everything it says is journaled and shown in the monitor, so the reasoning is
  auditable.

A smart system that can only make itself more careful, and can only choose among
things it has already proven. That is the honest meaning of "artificial
intelligence trading program".
"""

from __future__ import annotations

import json
import re
from pathlib import Path

VALID_STRATEGIES = {"rsi2", "orb", "swing"}
VALID_POSTURE = {"normal", "defensive"}

SYSTEM = (
    "You are the risk-and-strategy brain of an automated PAPER trading system. "
    "You read the system's live state and respond with ONLY a JSON object. You "
    "cannot increase risk; 'defensive' posture reduces activity. You may favor or "
    "avoid strategies only from the provided validated set. Be concise and honest — "
    "if there is no proven edge, say so and prefer defensive."
)


def situational_briefing(data_dir: str | Path, status: dict) -> dict:
    """Assemble a compact briefing from the whole system state."""
    data_dir = Path(data_dir)
    edge = _tail_jsonl(data_dir / "edge_ledger.jsonl", 5)
    roster = _read_json(data_dir / "roster.json")
    champion = roster.get("champion") if roster else None
    survivors = (
        [f"{r['strategy']} {r['params']}" for r in roster.get("variants", []) if r.get("survived")]
        if roster
        else []
    )
    last = status.get("last", {}) if status else {}
    return {
        "market_open": last.get("market_open"),
        "equity": (status.get("account") or {}).get("equity"),
        "open_positions": len(status.get("positions", []) or []),
        "trades_today": last.get("trades_today", 0),
        "candidates": (status.get("candidates") or [])[:25],
        "universe_size": status.get("universe_size", 0),
        "champion": champion,
        "validated_survivors": survivors,
        "edge_ledger_recent": edge,
        "has_proven_edge": bool(edge and edge[-1].get("beats_luck")),
    }


def build_prompt(briefing: dict) -> str:
    return (
        "Live system state:\n"
        f"{json.dumps(briefing, indent=2)}\n\n"
        "Validated strategies you may favor/avoid: "
        f"{sorted(VALID_STRATEGIES)}\n\n"
        'Respond with ONLY: {"regime":"trend|range|volatile|unclear",'
        '"risk_posture":"normal|defensive","favor":[],"avoid":[],'
        '"rationale":"one or two sentences"}'
    )


def parse_recommendation(text: str) -> dict:
    """Extract and hard-validate the brain's JSON. Anything out of bounds is
    dropped; the safe default is defensive."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    rec = {}
    if match:
        try:
            rec = json.loads(match.group(0))
        except json.JSONDecodeError:
            rec = {}
    posture = rec.get("risk_posture")
    posture = posture if posture in VALID_POSTURE else "defensive"
    favor = [s for s in rec.get("favor", []) if s in VALID_STRATEGIES]
    avoid = [s for s in rec.get("avoid", []) if s in VALID_STRATEGIES]
    return {
        "regime": str(rec.get("regime", "unclear"))[:40],
        "risk_posture": posture,
        "favor": favor,
        "avoid": avoid,
        "rationale": str(rec.get("rationale", ""))[:400],
    }


class AiBrain:
    def __init__(self, llm, system: str | None = None):
        self.llm = llm
        self.system = system or SYSTEM

    def reason(self, briefing: dict) -> dict:
        try:
            text = self.llm.complete(build_prompt(briefing), system=self.system)
        except Exception as e:
            return {**_default_defensive(), "rationale": f"brain error, staying defensive: {e}"}
        return parse_recommendation(text)


def _default_defensive() -> dict:
    return {
        "regime": "unclear",
        "risk_posture": "defensive",
        "favor": [],
        "avoid": [],
        "rationale": "no reasoning available",
    }


def apply_posture(base_max_positions: int, base_max_new: int, posture: str) -> tuple[int, int]:
    """Translate posture into concrete limits — defensive only ever tightens,
    normal restores the base. There is no path here that raises risk."""
    if posture == "defensive":
        return max(1, base_max_positions // 2), max(1, base_max_new // 2)
    return base_max_positions, base_max_new


def run_brain_cycle(data_dir: str | Path, status: dict, llm=None) -> dict:
    """One reasoning pass. Returns {available, briefing, recommendation}."""
    if llm is None:
        from keel.llm import pick_provider

        llm = pick_provider()
    briefing = situational_briefing(data_dir, status)
    if llm is None:
        return {"available": False, "briefing": briefing, "recommendation": _default_defensive()}

    from keel.knowledge import system_context
    from keel.training import append_memory

    rec = AiBrain(llm, system=system_context(data_dir)).reason(briefing)
    append_memory(data_dir, briefing, rec)  # remember for the training loop
    return {
        "available": True,
        "provider": getattr(llm, "name", "?"),
        "briefing": briefing,
        "recommendation": rec,
    }


def _tail_jsonl(path: Path, n: int) -> list[dict]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(x) for x in lines[-n:] if x.strip()]


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
