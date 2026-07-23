"""Point-in-time tradeable universe.

Every membership row carries the dates it was true for. There is deliberately
no way to construct a universe from "the current list of symbols" — that path
is how survivorship bias gets in, so it does not exist here. If you only know
today's membership, you must record today as the start date and your backtests
before that date will (correctly) see an empty universe.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class Membership:
    symbol: str
    start: date
    end: date | None = None  # None = still a member

    def active_on(self, when: date) -> bool:
        return self.start <= when and (self.end is None or when <= self.end)


@dataclass(frozen=True)
class Universe:
    members: tuple[Membership, ...]

    def as_of(self, when: date) -> frozenset[str]:
        return frozenset(m.symbol for m in self.members if m.active_on(when))

    @classmethod
    def from_csv(cls, path: str | Path) -> Universe:
        """Columns: symbol,start,end — `end` empty for current members."""
        rows = []
        with Path(path).open(newline="") as f:
            for row in csv.DictReader(f):
                end_raw = (row.get("end") or "").strip()
                rows.append(
                    Membership(
                        symbol=row["symbol"].strip(),
                        start=date.fromisoformat(row["start"].strip()),
                        end=date.fromisoformat(end_raw) if end_raw else None,
                    )
                )
        return cls(tuple(rows))
