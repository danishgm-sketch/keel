from __future__ import annotations

from datetime import UTC, datetime

from keel.intelligence import RuntimeInputs, build_state

FIXED_TS = datetime(2024, 1, 2, 15, 0, 0, tzinfo=UTC)

MODEL_BUNDLE = "legacy-llm-shadow"


def healthy_inputs(**over) -> RuntimeInputs:
    """A fully healthy, certified runtime snapshot — the only case where the
    baseline can reach NORMAL. Override any field via kwargs."""
    base = RuntimeInputs(
        deployment_id="dep-test",
        candidate_id="baseline",
        model_bundle_id=MODEL_BUNDLE,
        process_instance_id="test-proc",
        edge_row={"beats_luck": True, "pvalue": 0.01, "oos_sharpe": 1.2, "n_folds": 12},
        champion="ensemble {}",
        certified_strategies=("rsi2", "ensemble"),
        active_strategies=("rsi2",),
        clock={"is_open": True, "next_close": "2024-01-02T21:00:00Z"},
        market_feed_healthy=True,
        last_bar_age_seconds=5.0,
        account={"equity": "100000", "buying_power": "100000"},
        positions=[],
        protected_symbols=frozenset(),
        broker_reachable=True,
        broker_reconciled=True,
        pending_orders=0,
        database_healthy=True,
        journal_healthy=True,
        open_incidents=0,
        observation_ts=FIXED_TS,
    )
    for k, v in over.items():
        setattr(base, k, v)
    return base


def healthy_state(**over):
    return build_state(healthy_inputs(**over))
