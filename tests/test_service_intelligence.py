from __future__ import annotations

from fakes import FakeBroker
from keel.service import LiveService


def _svc(tmp_path) -> LiveService:
    svc = LiveService(tmp_path)
    svc.broker = FakeBroker()
    svc.broker.positions = {"AAPL": 10}
    svc._bars = {"AAPL": object()}  # non-empty -> market feed considered healthy
    return svc


def test_shadow_never_mutates_trading_limits(tmp_path):
    svc = _svc(tmp_path)
    before = (svc.config.max_positions, svc.config.max_new_per_day, svc.config.risk_fraction)
    svc._run_intelligence()
    after = (svc.config.max_positions, svc.config.max_new_per_day, svc.config.risk_fraction)
    assert before == after  # the AI observed, it did not touch limits
    assert svc.latest_intel.get("available") is True
    assert svc.latest_intel["mode"] == "shadow"


def test_shadow_places_no_orders(tmp_path):
    svc = _svc(tmp_path)
    svc._run_intelligence()
    assert svc.broker.orders == []  # intelligence never submits
    assert svc.broker.flattened is False
    assert svc.broker.cancelled is False


def test_shadow_decision_is_persisted(tmp_path):
    svc = _svc(tmp_path)
    svc._run_intelligence()
    decision_id = svc.latest_intel.get("decision_id")
    assert decision_id is not None
    assert svc.db.get_decision(decision_id) is not None


def test_broker_failure_raises_incident(tmp_path):
    svc = _svc(tmp_path)

    class Broken(FakeBroker):
        def get_account(self):
            raise RuntimeError("broker down")

    svc.broker = Broken()
    assert svc.db.count_open_incidents() == 0
    svc._run_intelligence()
    assert svc.db.count_open_incidents() >= 1
    open_ = svc.db.list_incidents(status="OPEN")
    assert any(i["category"] == "BROKER_RECONCILIATION_FAILURE" for i in open_)


def test_legacy_posture_apply_defaults_off(tmp_path):
    svc = LiveService(tmp_path)
    assert svc.config.legacy_posture_apply is False


def test_status_exposes_intelligence_block(tmp_path):
    svc = _svc(tmp_path)
    svc._run_intelligence()
    st = svc.status()
    assert "intelligence" in st
    intel = st["intelligence"]
    assert intel["mode"] == "shadow"
    assert intel["model_bundle"] == svc.intelligence.policy.model_bundle_id
    assert "database_healthy" in intel
    assert "journal_healthy" in intel
