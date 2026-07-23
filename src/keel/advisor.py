"""The evolution brain's *proposer*.

Given a summary of how the current playbook is doing, ask an LLM to propose new
strategy variants to try — strictly within a schema the engine can run and that
cannot alter risk. The proposals are parsed, validated, and clamped here; invalid
or out-of-range suggestions are dropped silently. Whatever survives is handed to
`roster.evolve`, where the honest statistics decide if any of it is real.

The LLM widens the search intelligently. It does not get to be right by
assertion — the bootstrap and FDR gates still rule.
"""

from __future__ import annotations

import json
import re

# The only knobs the LLM may turn, with hard ranges. Anything outside is dropped.
SCHEMA = {
    "rsi2": {
        "entry_level": (2.0, 25.0),
        "exit_level": (45.0, 80.0),
        "trend_span": (50, 200),
        "atr_stop_mult": (1.0, 4.0),
    },
    "orb": {"or_bars": (2, 20)},
    "swing": {"fast": (5, 30), "mid": (20, 80), "slow": (100, 250), "swing_lookback": (5, 30)},
}

SYSTEM = (
    "You are a quantitative research assistant proposing trading-strategy variants "
    "to TEST. You never claim an edge; you propose hypotheses that will be validated "
    "by out-of-sample bootstrap and false-discovery-rate control. Respond with ONLY a "
    "JSON array, no prose."
)


def build_prompt(context: str, n: int) -> str:
    return (
        f"The engine supports these strategies and parameter ranges:\n"
        f"{json.dumps(SCHEMA, indent=2)}\n\n"
        f"Recent performance context:\n{context}\n\n"
        f"Propose {n} NEW variants worth testing (diverse, within range). "
        f'Return JSON: [{{"strategy":"rsi2","params":{{"entry_level":8}},'
        f'"rationale":"..."}}]. JSON only.'
    )


def _clamp(strategy: str, params: dict) -> dict | None:
    spec = SCHEMA.get(strategy)
    if not spec:
        return None
    out: dict = {}
    for k, v in params.items():
        if k not in spec:
            continue
        lo, hi = spec[k]
        try:
            val = float(v)
        except (TypeError, ValueError):
            continue
        val = max(lo, min(hi, val))
        out[k] = int(val) if isinstance(lo, int) else round(val, 3)
    return out


def parse_variants(text: str) -> list[tuple[str, dict]]:
    """Extract [(strategy, params)] from an LLM response, validated and clamped."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    variants: list[tuple[str, dict]] = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        strategy = str(item.get("strategy", "")).lower()
        params = _clamp(strategy, item.get("params", {}) or {})
        if params is None:
            continue
        key = (strategy, tuple(sorted(params.items())))
        if key in seen:
            continue
        seen.add(key)
        variants.append((strategy, params))
    return variants


def propose_variants(llm, context: str, n: int = 5) -> list[tuple[str, dict]]:
    """Ask the LLM for variants; returns validated (strategy, params) pairs (may
    be empty if the model is unavailable or unhelpful — that is fine)."""
    if llm is None:
        return []
    try:
        text = llm.complete(build_prompt(context, n), system=SYSTEM)
    except Exception:
        return []
    return parse_variants(text)
