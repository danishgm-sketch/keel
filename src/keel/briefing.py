"""The Keel Briefing — the product moment.

Not a dashboard. Three honest questions, answered in a breath:

    1. Is there proven edge yet?
    2. What did the machine do?
    3. What is it worried about?

Everything the system knows, distilled to what a human actually needs to decide
whether to care today. Built from the same honest state `keel doctor` reads.
"""

from __future__ import annotations

from pathlib import Path

from keel.doctor import diagnose
from keel.journal import Journal


def briefing(data_dir: str | Path) -> dict:
    data_dir = Path(data_dir)
    d = diagnose(data_dir)
    j = Journal(data_dir / "journal.jsonl")
    today = j.today()

    entries = [e for e in today if e.get("kind") == "entry"]
    exits = [e for e in today if e.get("kind") == "exit"]
    vetoes = [e for e in today if e.get("kind") == "qualitative_veto"]
    ai = [e for e in today if e.get("kind") == "ai_briefing"]

    # 1 — is there edge?
    edge = d["edge"]
    if edge["has_proven_edge"]:
        q1 = (
            f"Yes — beat luck out-of-sample (p={edge['last_pvalue']}, {edge['folds']} folds). "
            "Keep accumulating folds before trusting size."
        )
    elif d["data_symbols"] == 0:
        q1 = "Unknown — no market data yet. Nothing has been tested."
    else:
        q1 = (
            "No proven edge yet. This is the honest default; the bot should be "
            "minimal/defensive while research continues."
        )

    # 2 — what did it do?
    q2 = (
        f"{len(entries)} entries, {len(exits)} exits today"
        + (f" · {len(vetoes)} names vetoed on news" if vetoes else "")
        + (f" · champion: {d['roster']['champion']}" if d["roster"]["champion"] else "")
    )

    # 3 — what is it worried about?
    worries = []
    if not edge["has_proven_edge"] and d["data_symbols"] > 0:
        worries.append("no validated edge — do not scale")
    if ai:
        last = ai[-1]
        if last.get("risk_posture") == "defensive":
            worries.append(f"AI brain is defensive ({last.get('rationale', '')[:80]})")
    if vetoes:
        avoided = sorted({s for v in vetoes for s in v.get("avoid", [])})
        if avoided:
            worries.append("event risk on: " + ", ".join(avoided[:8]))
    q3 = "; ".join(worries) if worries else "nothing flagged"

    return {
        "edge": q1,
        "activity": q2,
        "worries": q3,
        "verdict": d["verdict"],
    }
