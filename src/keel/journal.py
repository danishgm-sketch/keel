"""Append-only journal of every live decision and order.

One JSONL line per event. This is the irreplaceable record: paper caches and
candle files can be rebuilt, but the sequence of decisions the bot actually made
in real time cannot. It is also the raw material the evolution loop learns from.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


class Journal:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, kind: str, **fields) -> dict:
        event = {"ts": datetime.now(UTC).isoformat(), "kind": kind, **fields}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
        return event

    def tail(self, n: int = 100) -> list[dict]:
        if not self.path.is_file():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(x) for x in lines[-n:] if x.strip()]

    def today(self) -> list[dict]:
        day = datetime.now(UTC).date().isoformat()
        return [e for e in self.tail(2000) if e.get("ts", "").startswith(day)]
