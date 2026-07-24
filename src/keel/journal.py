"""Append-only, tamper-evident journal of every live decision and order.

One JSON object per line. Beyond the human-readable fields, each record carries a
hash chain: a sequence number, the previous record's hash, and this record's hash
over its canonical content. Any edit to a past line breaks the chain, so
`verify()` can detect after-the-fact modification.

This is **tamper-evident, not tamper-proof**: it detects modification of an
existing file; it does not prevent someone with write access from rebuilding the
whole chain. It is not cryptographic non-repudiation.

Backward compatible: all previous fields remain at the top level, so existing
readers keep working; the chain fields are additive.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

_GENESIS = "genesis"


def _canonical(record: dict) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"))


def _hash(record_without_hash: dict) -> str:
    return hashlib.sha256(_canonical(record_without_hash).encode()).hexdigest()


class Journal:
    def __init__(
        self,
        path: str | Path,
        process_instance_id: str | None = None,
        deployment_id: str | None = None,
    ):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.process_instance_id = process_instance_id or uuid.uuid4().hex[:12]
        self.deployment_id = deployment_id
        self.correlation_id: str | None = None
        self._seq, self._last_hash = self._load_tail()

    def _load_tail(self) -> tuple[int, str]:
        if not self.path.is_file():
            return 0, _GENESIS
        lines = [x for x in self.path.read_text(encoding="utf-8").splitlines() if x.strip()]
        if not lines:
            return 0, _GENESIS
        try:
            last = json.loads(lines[-1])
            return int(last.get("seq", len(lines))) + 1, str(last.get("hash", _GENESIS))
        except (json.JSONDecodeError, ValueError):
            return len(lines), _GENESIS

    def write(self, kind: str, **fields) -> dict:
        base = {
            "seq": self._seq,
            "ts": datetime.now(UTC).isoformat(),
            "kind": kind,
            "process_instance_id": self.process_instance_id,
            "deployment_id": self.deployment_id,
            "correlation_id": fields.pop("correlation_id", self.correlation_id),
            "prev_hash": self._last_hash,
            **fields,
        }
        h = _hash(base)
        record = {**base, "hash": h}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        self._seq += 1
        self._last_hash = h
        return record

    def tail(self, n: int = 100) -> list[dict]:
        if not self.path.is_file():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(x) for x in lines[-n:] if x.strip()]

    def today(self) -> list[dict]:
        day = datetime.now(UTC).date().isoformat()
        return [e for e in self.tail(5000) if e.get("ts", "").startswith(day)]

    def verify(self) -> tuple[bool, str]:
        """Re-derive the hash chain and confirm nothing was modified. Only records
        that carry a `hash` field participate (legacy records are skipped)."""
        return verify_journal(self.path)


def verify_journal(path: str | Path) -> tuple[bool, str]:
    p = Path(path)
    if not p.is_file():
        return True, "no journal file (nothing to verify)"
    prev = _GENESIS
    checked = 0
    for i, line in enumerate(x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            return False, f"line {i}: not valid JSON"
        if "hash" not in rec:  # legacy record, chain begins after it
            prev = rec.get("hash", prev)
            continue
        stored = rec["hash"]
        body = {k: v for k, v in rec.items() if k != "hash"}
        if _hash(body) != stored:
            return False, f"line {i} (seq {rec.get('seq')}): content hash mismatch (modified)"
        if "prev_hash" in rec and checked > 0 and rec["prev_hash"] != prev:
            return False, f"line {i} (seq {rec.get('seq')}): prev_hash does not chain"
        prev = stored
        checked += 1
    return True, f"chain intact: {checked} records verified"
