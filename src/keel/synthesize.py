"""Self-writing — the safe version of the bold swing.

The LLM does not write arbitrary code (that's the dangerous kind). Instead it
proposes an **ensemble specification**: weights over the known signals plus entry
thresholds — a bounded, declarative design the engine can build directly. The
proposal is parsed, validated, and clamped to legal ranges here, then handed to
the walk-forward gate like any other candidate. The model expands the search;
the statistics still decide. No code execution, no way to touch risk.
"""

from __future__ import annotations

import json
import re

from keel.ensemble import Ensemble, EnsembleStrategy
from keel.signals import SIGNAL_NAMES, default_signals

SYSTEM = (
    "You design trading-signal ENSEMBLES to be TESTED, never claiming an edge. You "
    "output ONLY JSON: weights over the given signals plus entry/exit thresholds. "
    "The walk-forward gate will judge it; propose diverse, sensible blends."
)


def build_prompt(context: str, n: int) -> str:
    return (
        f"Signals available: {SIGNAL_NAMES}\n"
        f"Context: {context}\n\n"
        f"Propose {n} ensemble specs to test. Return ONLY JSON: "
        '[{"weights":{"rsi2":1.0,"momentum":0.5},"entry":0.55,"exit":0.3}]'
    )


def parse_specs(text: str) -> list[dict]:
    """Extract validated ensemble specs. Weights clamped to [0,3], restricted to
    known signals; thresholds clamped to sane ranges. Empty/invalid dropped."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    specs = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw = item.get("weights", {}) or {}
        weights = {}
        for k, v in raw.items():
            if k in SIGNAL_NAMES:
                try:
                    val = max(0.0, min(3.0, float(v)))
                except (TypeError, ValueError):
                    continue
                if val > 0:  # drop zero/negative weights rather than storing them
                    weights[k] = val
        if not weights or sum(weights.values()) <= 0:
            continue
        entry = _clamp(item.get("entry", 0.55), 0.3, 0.9)
        exit_ = _clamp(item.get("exit", 0.3), 0.05, entry - 0.05)
        specs.append({"weights": weights, "entry": entry, "exit": exit_})
    return specs


def _clamp(v, lo, hi) -> float:
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return lo


def spec_to_strategy(spec: dict) -> EnsembleStrategy:
    ens = Ensemble(signals=default_signals(), weights=spec["weights"])
    return EnsembleStrategy(ensemble=ens, entry=spec["entry"], exit_=spec["exit"])


def propose_ensembles(llm, context: str = "", n: int = 4) -> list[dict]:
    if llm is None:
        return []
    try:
        text = llm.complete(build_prompt(context, n), system=SYSTEM)
    except Exception:
        return []
    return parse_specs(text)
