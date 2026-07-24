from __future__ import annotations

from keel.allocator import allocate, gross_exposure
from keel.decay import assess_decay
from keel.riskbudget import Limits, check_order, drawdown_posture
from keel.stress import stress_book


# --- allocator (cross-sectional book) ---
def test_allocate_picks_top_and_splits_risk():
    conv = {"A": 0.9, "B": 0.8, "C": 0.4, "D": 0.7}
    out = allocate(conv, risk_fraction=0.03, max_positions=2, min_conviction=0.5, tilt=False)
    assert set(out) == {"A", "B"}  # top 2 above floor
    assert abs(sum(out.values()) - 0.03) < 1e-9
    assert out["A"] == out["B"]  # equal risk when not tilted


def test_allocate_tilts_toward_conviction():
    out = allocate({"A": 0.9, "B": 0.5}, risk_fraction=0.02, tilt=True)
    assert out["A"] > out["B"]
    assert abs(sum(out.values()) - 0.02) < 1e-6


def test_allocate_empty_when_nothing_qualifies():
    assert allocate({"A": 0.2}, min_conviction=0.5) == {}


def test_gross_exposure_sums_market_value():
    assert gross_exposure([{"market_value": "1000"}, {"market_value": "500"}]) == 1500


# --- decay monitor ---
def test_decay_retires_on_sustained_decline():
    series = [0.8, 0.7, 0.9, 0.6, 0.8, 0.7, -0.3, -0.4, -0.5, -0.6]
    assert assess_decay(series, recent=4)["retire"] is True


def test_decay_holds_when_stable():
    series = [0.4, 0.5, 0.6, 0.5, 0.4, 0.5, 0.6, 0.5, 0.4, 0.5]
    assert assess_decay(series)["retire"] is False


def test_decay_needs_history():
    assert assess_decay([0.5, -0.5])["retire"] is False


# --- risk budget ---
def test_check_order_blocks_over_exposure():
    lim = Limits(max_gross_exposure=1.0, max_positions=20)
    ok, _ = check_order(100_000, 95_000, 5, 10_000, lim)
    assert ok is False  # would exceed 100% gross


def test_check_order_blocks_position_cap():
    lim = Limits(max_positions=3)
    ok, reason = check_order(100_000, 0, 3, 1000, lim)
    assert ok is False and "position cap" in reason


def test_check_order_allows_within_limits():
    ok, _ = check_order(100_000, 10_000, 2, 5_000, Limits())
    assert ok is True


def test_drawdown_posture_flips_defensive():
    lim = Limits(daily_drawdown_budget=0.03)
    assert drawdown_posture([100, 101, 102, 98], lim) == "defensive"  # ~-3.9% from peak
    assert drawdown_posture([100, 101, 100.5], lim) == "normal"


# --- stress test (honest gap risk) ---
def test_stress_charges_full_shock_on_gap_through_stop():
    # stop at 95, but a -30% shock gaps to 70 -> loss is full, not capped at the stop
    book = [{"price": 100, "shares": 10, "stop": 95}]
    report = stress_book(book, {"gap -30%": -0.30})
    assert report["scenarios"]["gap -30%"]["pnl"] == (70 - 100) * 10


def test_stress_caps_loss_at_stop_on_orderly_move():
    book = [{"price": 100, "shares": 10, "stop": 95}]
    report = stress_book(book, {"mild -3%": -0.03})  # 97 >= stop 95 -> stop out at 95
    assert report["scenarios"]["mild -3%"]["pnl"] == (95 - 100) * 10
