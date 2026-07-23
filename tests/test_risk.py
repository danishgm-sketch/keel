from __future__ import annotations

import pytest

from keel.risk import size_from_stop


def test_risk_never_exceeds_fraction():
    for equity, entry, stop in [(100_000, 50, 48), (10_000, 5, 4.9), (1_000, 300, 250)]:
        s = size_from_stop(equity, entry, stop, risk_fraction=0.01)
        assert s.cash_risk <= equity * 0.01 + 1e-9


def test_tight_stop_cannot_leverage():
    s = size_from_stop(100_000, 100.0, 99.99)
    assert s.shares * 100.0 <= 100_000


def test_degenerate_inputs_size_zero():
    assert size_from_stop(100_000, 50, 50).shares == 0
    assert size_from_stop(0, 50, 48).shares == 0
    assert size_from_stop(-5, 50, 48).shares == 0


def test_risk_fraction_bounds_enforced():
    with pytest.raises(ValueError):
        size_from_stop(100_000, 50, 48, risk_fraction=0.5)
    with pytest.raises(ValueError):
        size_from_stop(100_000, 50, 48, risk_fraction=0.0)


def test_known_example():
    # 1% of 100k = $1000 risk; $2 stop distance -> 500 shares
    s = size_from_stop(100_000, 50.0, 48.0)
    assert s.shares == 500
    assert s.cash_risk == pytest.approx(1000.0)
