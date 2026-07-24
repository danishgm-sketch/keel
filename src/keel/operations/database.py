"""Durable structured truth store (SQLite).

The authoritative record of deployments, intelligence states, decisions
(baseline / proposal / validated / applied), authority grants, incidents, order
intents, broker observations, and episodes. JSONL journals remain as a
human-inspectable audit stream; both carry the same correlation IDs.

Concurrency: one connection guarded by a lock (single writer). WAL mode allows
external readers. Callers should treat this object as owned by one service
instance; it is not a general multi-process writer.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from keel.intelligence.contracts import DeploymentState, KeelState, canonical_json
from keel.intelligence.runtime import ShadowResult
from keel.operations.incidents import Incident
from keel.operations.order_intent import OrderIntent

SCHEMA_VERSION = 1

_MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS deployments (
            deployment_id TEXT PRIMARY KEY,
            candidate_id  TEXT NOT NULL,
            model_bundle_id TEXT NOT NULL,
            created_at    TEXT NOT NULL,
            payload       TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS intelligence_states (
            state_id     TEXT PRIMARY KEY,
            created_at   TEXT NOT NULL,
            completeness REAL NOT NULL,
            payload      TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS decisions (
            decision_id     TEXT PRIMARY KEY,
            correlation_id  TEXT,
            state_id        TEXT NOT NULL REFERENCES intelligence_states(state_id),
            created_at      TEXT NOT NULL,
            validated_posture TEXT NOT NULL,
            validated_source  TEXT NOT NULL,
            valid           INTEGER NOT NULL,
            baseline_json   TEXT NOT NULL,
            proposal_json   TEXT,
            validated_json  TEXT NOT NULL,
            applied_json    TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS authority_grants (
            grant_id      TEXT PRIMARY KEY,
            model_bundle_id TEXT NOT NULL,
            candidate_id  TEXT NOT NULL,
            level         TEXT NOT NULL,
            expires_at    TEXT NOT NULL,
            created_at    TEXT NOT NULL,
            payload       TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS incidents (
            incident_id   TEXT PRIMARY KEY,
            category      TEXT NOT NULL,
            severity      TEXT NOT NULL,
            status        TEXT NOT NULL,
            message       TEXT NOT NULL,
            correlation_id TEXT,
            deployment_id TEXT,
            created_at    TEXT NOT NULL,
            updated_at    TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS order_intents (
            intent_id       TEXT PRIMARY KEY,
            idempotency_key TEXT NOT NULL UNIQUE,
            deployment_id   TEXT NOT NULL,
            candidate_id    TEXT NOT NULL,
            strategy_id     TEXT NOT NULL,
            symbol          TEXT NOT NULL,
            side            TEXT NOT NULL,
            quantity        INTEGER NOT NULL,
            intended_stop   REAL,
            order_class     TEXT NOT NULL,
            status          TEXT NOT NULL,
            broker_order_id TEXT,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS broker_observations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            payload    TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS episodes (
            episode_id   TEXT PRIMARY KEY,
            state_id     TEXT NOT NULL REFERENCES intelligence_states(state_id),
            created_at   TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            payload      TEXT NOT NULL
        );
        """,
    ),
]


def _now() -> str:
    return datetime.now(UTC).isoformat()


class KeelDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._migrate()

    # --- schema ---
    def _migrate(self) -> None:
        with self._lock:
            self._conn.execute("CREATE TABLE IF NOT EXISTS schema_meta (version INTEGER NOT NULL);")
            cur = self._conn.execute("SELECT COALESCE(MAX(version), 0) AS v FROM schema_meta;")
            current = cur.fetchone()["v"]
            for version, sql in _MIGRATIONS:
                if version > current:
                    self._conn.executescript(sql)
                    self._conn.execute("INSERT INTO schema_meta (version) VALUES (?);", (version,))
            self._conn.commit()

    def schema_version(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS v FROM schema_meta;"
            ).fetchone()
            return int(row["v"])

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    # --- writers ---
    def record_deployment(self, dep: DeploymentState) -> None:
        with self.transaction() as c:
            c.execute(
                "INSERT OR REPLACE INTO deployments VALUES (?,?,?,?,?);",
                (
                    dep.deployment_id,
                    dep.candidate_id,
                    dep.model_bundle_id,
                    _now(),
                    canonical_json(dep),
                ),
            )

    def record_state(self, state: KeelState) -> str:
        with self.transaction() as c:
            c.execute(
                "INSERT OR IGNORE INTO intelligence_states VALUES (?,?,?,?);",
                (state.state_id, _now(), state.completeness, canonical_json(state)),
            )
        return state.state_id

    def record_shadow(
        self,
        result: ShadowResult,
        correlation_id: str | None = None,
    ) -> str:
        state = result.state
        v = result.validated
        decision_id = hashlib.sha256(
            f"{state.state_id}:{v.action_id}:{correlation_id or ''}".encode()
        ).hexdigest()[:32]
        with self.transaction() as c:
            c.execute(
                "INSERT OR IGNORE INTO intelligence_states VALUES (?,?,?,?);",
                (state.state_id, _now(), state.completeness, canonical_json(state)),
            )
            c.execute(
                "INSERT OR REPLACE INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?);",
                (
                    decision_id,
                    correlation_id,
                    state.state_id,
                    _now(),
                    v.posture.label,
                    v.source.value,
                    int(v.valid),
                    canonical_json(result.baseline),
                    canonical_json(result.proposal) if result.proposal else None,
                    canonical_json(v),
                    canonical_json(result.applied),
                ),
            )
            ep = result.episode
            c.execute(
                "INSERT OR IGNORE INTO episodes VALUES (?,?,?,?,?);",
                (ep.episode_id, state.state_id, _now(), ep.content_hash, canonical_json(ep)),
            )
        return decision_id

    def record_incident(self, inc: Incident) -> None:
        with self.transaction() as c:
            c.execute(
                "INSERT OR REPLACE INTO incidents VALUES (?,?,?,?,?,?,?,?,?);",
                (
                    inc.incident_id,
                    inc.category.value,
                    inc.severity.value,
                    inc.status.value,
                    inc.message,
                    inc.correlation_id,
                    inc.deployment_id,
                    inc.created_at.isoformat(),
                    inc.updated_at.isoformat(),
                ),
            )

    def record_order_intent(self, intent: OrderIntent) -> tuple[OrderIntent, bool]:
        """Returns (stored_intent, is_duplicate). Duplicate = same idempotency key."""
        with self.transaction() as c:
            existing = c.execute(
                "SELECT intent_id FROM order_intents WHERE idempotency_key = ?;",
                (intent.idempotency_key,),
            ).fetchone()
            if existing is not None:
                return intent, True
            c.execute(
                "INSERT INTO order_intents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?);",
                (
                    intent.intent_id,
                    intent.idempotency_key,
                    intent.deployment_id,
                    intent.candidate_id,
                    intent.strategy_id,
                    intent.symbol,
                    intent.side.value,
                    intent.quantity,
                    intent.intended_stop,
                    intent.intended_order_class,
                    intent.status.value,
                    intent.broker_order_id,
                    intent.created_at.isoformat(),
                    intent.updated_at.isoformat(),
                ),
            )
        return intent, False

    def record_broker_observation(self, payload: dict) -> None:
        with self.transaction() as c:
            c.execute(
                "INSERT INTO broker_observations (created_at, payload) VALUES (?,?);",
                (_now(), json.dumps(payload, sort_keys=True, separators=(",", ":"))),
            )

    # --- readers ---
    def get_state(self, state_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM intelligence_states WHERE state_id = ?;", (state_id,)
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def get_decision(self, decision_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM decisions WHERE decision_id = ?;", (decision_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_incidents(self, status: str | None = None, limit: int = 100) -> list[dict]:
        with self._lock:
            if status:
                rows = self._conn.execute(
                    "SELECT * FROM incidents WHERE status = ? ORDER BY created_at DESC LIMIT ?;",
                    (status, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM incidents ORDER BY created_at DESC LIMIT ?;", (limit,)
                ).fetchall()
        return [dict(r) for r in rows]

    def count_open_incidents(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM incidents WHERE status = 'OPEN';"
            ).fetchone()
            return int(row["n"])

    def recent_decisions(self, limit: int = 20) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT decision_id, state_id, validated_posture, validated_source, valid, "
                "created_at FROM decisions ORDER BY created_at DESC LIMIT ?;",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def healthy(self) -> bool:
        try:
            with self._lock:
                self._conn.execute("SELECT 1;").fetchone()
            return True
        except Exception:
            return False

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def open_database(data_dir: str | Path) -> KeelDatabase:
    return KeelDatabase(Path(data_dir) / "keel.db")
