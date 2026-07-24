from __future__ import annotations

import pytest

from intel_helpers import FIXED_TS, healthy_state
from keel.intelligence import evaluate_shadow
from keel.intelligence.policy import LegacyLlmShadowPolicy
from keel.operations.database import KeelDatabase, open_database
from keel.operations.incidents import IncidentCategory, IncidentSeverity, new_incident
from keel.operations.order_intent import idempotency_key, make_intent


def test_schema_initialises_cleanly(tmp_path):
    db = open_database(tmp_path)
    assert db.schema_version() == 1
    assert db.healthy() is True
    db.close()


def test_migrations_are_repeatable(tmp_path):
    open_database(tmp_path).close()
    db = open_database(tmp_path)  # reopen — should not error or double-apply
    assert db.schema_version() == 1
    db.close()


def test_transaction_rollback(tmp_path):
    db = open_database(tmp_path)
    inc = new_incident(IncidentCategory.DATABASE_FAILURE, IncidentSeverity.ERROR, "x")
    with pytest.raises(RuntimeError), db.transaction() as c:
        c.execute(
            "INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?);",
            (
                inc.incident_id,
                inc.category.value,
                inc.severity.value,
                inc.status.value,
                inc.message,
                None,
                None,
                inc.created_at.isoformat(),
                inc.updated_at.isoformat(),
            ),
        )
        raise RuntimeError("boom")
    assert db.list_incidents() == []  # rolled back
    db.close()


def test_shadow_decision_is_persisted_and_retrievable(tmp_path):
    db = open_database(tmp_path)
    r = evaluate_shadow(
        healthy_state(),
        LegacyLlmShadowPolicy(reason_fn=lambda s: {"risk_posture": "defensive"}),
        at=FIXED_TS,
    )
    decision_id = db.record_shadow(r, correlation_id="corr-1")
    row = db.get_decision(decision_id)
    assert row is not None
    assert row["state_id"] == r.state.state_id
    assert row["validated_source"] == "model"
    assert row["correlation_id"] == "corr-1"
    assert db.get_state(r.state.state_id) is not None
    db.close()


def test_incident_persisted_and_listed(tmp_path):
    db = open_database(tmp_path)
    inc = new_incident(
        IncidentCategory.BROKER_RECONCILIATION_FAILURE, IncidentSeverity.CRITICAL, "no recon"
    )
    db.record_incident(inc)
    open_ = db.list_incidents(status="OPEN")
    assert len(open_) == 1 and open_[0]["category"] == "BROKER_RECONCILIATION_FAILURE"
    assert db.count_open_incidents() == 1
    db.close()


def test_idempotency_key_is_stable():
    args = ("dep", "cand", "rsi2", "AAPL", "2024-01-02T10:00:00Z", "buy", 10, 95.0)
    assert idempotency_key(*args) == idempotency_key(*args)
    # any identity change alters the key
    changed = ("dep", "cand", "rsi2", "AAPL", "2024-01-02T10:00:00Z", "buy", 11, 95.0)
    assert idempotency_key(*args) != idempotency_key(*changed)


def test_duplicate_order_intent_detected(tmp_path):
    db = open_database(tmp_path)
    i1 = make_intent("dep", "cand", "rsi2", "AAPL", "2024-01-02T10:00:00Z", "buy", 10, 95.0)
    i2 = make_intent("dep", "cand", "rsi2", "AAPL", "2024-01-02T10:00:00Z", "buy", 10, 95.0)
    _, dup1 = db.record_order_intent(i1)
    _, dup2 = db.record_order_intent(i2)
    assert dup1 is False
    assert dup2 is True  # same idempotency key
    db.close()


def test_database_is_sqlite_file(tmp_path):
    db = open_database(tmp_path)
    assert (tmp_path / "keel.db").exists()
    assert isinstance(db, KeelDatabase)
    db.close()
