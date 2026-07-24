from __future__ import annotations

from intel_helpers import healthy_state
from keel.intelligence import Posture, baseline_action
from keel.intelligence.reasons import ReasonCode


def test_broker_not_reconciled_halts():
    b = baseline_action(healthy_state(broker_reconciled=False))
    assert b.posture == Posture.HALT
    assert ReasonCode.BROKER_NOT_RECONCILED.value in b.reason_codes
    assert b.participation_multiplier == 0.0


def test_unprotected_position_halts():
    st = healthy_state(
        positions=[{"symbol": "AAPL", "market_value": "1000"}],
        protected_symbols=frozenset(),  # cannot confirm protection
    )
    b = baseline_action(st)
    assert b.posture == Posture.HALT
    assert ReasonCode.POSITION_UNPROTECTED.value in b.reason_codes


def test_unhealthy_database_halts():
    b = baseline_action(healthy_state(database_healthy=False))
    assert b.posture == Posture.HALT
    assert ReasonCode.DATABASE_UNHEALTHY.value in b.reason_codes


def test_unhealthy_journal_halts():
    b = baseline_action(healthy_state(journal_healthy=False))
    assert b.posture == Posture.HALT
    assert ReasonCode.JOURNAL_UNHEALTHY.value in b.reason_codes


def test_stale_market_halts():
    b = baseline_action(healthy_state(market_feed_healthy=False))
    assert b.posture == Posture.HALT
    assert ReasonCode.MARKET_DATA_STALE.value in b.reason_codes


def test_uncertified_evidence_is_defensive():
    st = healthy_state(edge_row={"beats_luck": False, "pvalue": 1.0, "n_folds": 3})
    b = baseline_action(st)
    assert b.posture == Posture.DEFENSIVE
    assert ReasonCode.NO_CERTIFIED_EDGE.value in b.reason_codes


def test_healthy_certified_state_can_be_normal():
    b = baseline_action(healthy_state())
    assert b.posture == Posture.NORMAL
    assert b.reason_codes == (ReasonCode.OK.value,)
    assert b.participation_multiplier == 1.0


def test_incomplete_state_never_increases_activity():
    # a state missing everything must never be NORMAL
    st = healthy_state(broker_reconciled=False, database_healthy=False, market_feed_healthy=False)
    b = baseline_action(st)
    assert b.posture == Posture.HALT
    assert b.posture < Posture.NORMAL


def test_high_concentration_restricts():
    st = healthy_state(
        positions=[
            {"symbol": "AAPL", "market_value": "9000"},
            {"symbol": "MSFT", "market_value": "1000"},
        ],
        protected_symbols=frozenset({"AAPL", "MSFT"}),
    )
    b = baseline_action(st)
    # concentration 0.9 > 0.35 -> at most RESTRICTED
    assert b.posture <= Posture.RESTRICTED
    assert ReasonCode.PORTFOLIO_CONCENTRATION_HIGH.value in b.reason_codes
