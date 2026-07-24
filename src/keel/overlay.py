"""The qualitative limb — the parallel, veto-only decision layer.

Runs alongside the quantitative engine. It reads recent news/catalysts for the
current candidates and flags names with material near-term event risk that make a
FRESH entry unwise (imminent earnings, halts, M&A rumors, regulatory/guidance
news, big gap headlines). Its output is an **avoid-list** the trader honours.

Hard boundary, on purpose: this limb can only *remove* names from consideration.
It cannot create a buy signal, size a position, or touch risk. Entry signals come
only from the validated quantitative playbook; the qualitative limb's job is to
keep the bot out of the landmines a chart cannot see. Unproven "news alpha" never
gets to open a trade.
"""

from __future__ import annotations

import json
import re

SYSTEM = (
    "You are Keel's qualitative risk limb. You are given candidate tickers and their "
    "recent headlines. Flag ONLY tickers with material near-term event/news risk that "
    "makes a fresh long entry unwise right now (imminent earnings, trading halt, "
    "M&A/rumor, regulatory action, guidance cut, large news gap). You can ONLY avoid; "
    "you must never suggest buying. Respond with ONLY JSON: "
    '{"avoid":["TICK"],"notes":{"TICK":"why"}}'
)


def build_prompt(digests: dict[str, str]) -> str:
    lines = [f"{sym}: {text}" for sym, text in list(digests.items())[:40]]
    body = "\n".join(lines) if lines else "(no fresh headlines)"
    return (
        "Candidate tickers and recent headlines:\n" + body + "\n\n"
        'Return ONLY: {"avoid":[...],"notes":{...}} — avoid must be a subset of the '
        "tickers above; never recommend buying."
    )


def parse_overlay(text: str, candidates: set[str]) -> dict:
    """Extract and hard-bound the limb's output: avoid must be a subset of the
    candidates; nothing here can add a name to trade."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    data = {}
    if match:
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            data = {}
    avoid = [s for s in data.get("avoid", []) if s in candidates]
    notes = {k: str(v)[:200] for k, v in (data.get("notes") or {}).items() if k in candidates}
    return {"avoid": avoid, "notes": notes}


def assess(llm, digests: dict[str, str], candidates: set[str]) -> dict:
    """Ask the limb which candidates to avoid. Fails safe to no-veto (never
    fabricates avoids on error — the quant engine still has its own risk rules)."""
    if llm is None or not digests:
        return {"avoid": [], "notes": {}}
    try:
        text = llm.complete(build_prompt(digests), system=SYSTEM)
    except Exception:
        return {"avoid": [], "notes": {}}
    return parse_overlay(text, candidates)
