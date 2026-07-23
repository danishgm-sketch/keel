from __future__ import annotations

import numpy as np

from conftest import make_intraday
from keel.costs import FREE, CostModel
from keel.portfolio import run_portfolio
from keel.strategies import OpeningRangeBreakout, Rsi2Reversion, SwingPullback


def _rsi2():
    return Rsi2Reversion(trend_span=50, tail=200)


def test_book_takes_many_trades_across_symbols():
    data = {f"S{i}": make_intraday(f"S{i}", n_sessions=8, seed=i) for i in range(6)}
    result = run_portfolio(data, _rsi2, max_positions=10, max_new_per_day=20, costs=FREE)
    assert len(result.trades) >= 15
    assert result.trades_per_day > 1.0


def test_intraday_positions_never_held_overnight():
    data = {f"S{i}": make_intraday(f"S{i}", n_sessions=6, seed=i + 10) for i in range(4)}
    result = run_portfolio(data, _rsi2, costs=FREE)
    for t in result.trades:
        assert t.lane == "intraday"
        assert t.entry_ts.astype("datetime64[D]") == t.exit_ts.astype("datetime64[D]")
    # everything is flat by the end: eod closes only apply to swing lanes
    assert all(t.reason in {"signal", "stop", "session_flat"} for t in result.trades)


def test_max_new_per_day_throttle():
    data = {f"S{i}": make_intraday(f"S{i}", n_sessions=6, seed=i + 3) for i in range(8)}
    result = run_portfolio(data, _rsi2, max_new_per_day=2, costs=FREE)
    by_day: dict = {}
    for t in result.trades:
        d = t.entry_ts.astype("datetime64[D]")
        by_day[d] = by_day.get(d, 0) + 1
    assert by_day and max(by_day.values()) <= 2


def test_max_concurrent_positions_respected():
    # 6 symbols, cap of 1: no two trades may overlap in [entry, exit] time.
    data = {f"S{i}": make_intraday(f"S{i}", n_sessions=6, seed=i + 20) for i in range(6)}
    result = run_portfolio(data, _rsi2, max_positions=1, max_new_per_day=99, costs=FREE)
    spans = sorted((t.entry_ts, t.exit_ts) for t in result.trades)
    for (_s1, e1), (s2, _e2) in zip(spans, spans[1:], strict=False):
        assert s2 >= e1  # next entry only after the previous exit


def test_costs_reduce_net_return():
    data = {f"S{i}": make_intraday(f"S{i}", n_sessions=8, seed=i) for i in range(5)}
    free = run_portfolio(data, _rsi2, costs=FREE)
    costly = run_portfolio(data, _rsi2, costs=CostModel(proportional=0.001, per_share=0.005))
    assert costly.total_return < free.total_return
    assert costly.total_costs > 0


def test_no_leverage_equity_stays_bounded():
    data = {f"S{i}": make_intraday(f"S{i}", n_sessions=8, seed=i) for i in range(5)}
    result = run_portfolio(data, _rsi2, max_positions=10, costs=FREE)
    assert np.all(result.daily_equity > 0)


def test_orb_and_swing_lanes_run():
    data = {f"S{i}": make_intraday(f"S{i}", n_sessions=8, seed=i + 30) for i in range(4)}
    orb = run_portfolio(data, lambda: OpeningRangeBreakout(or_bars=6), costs=FREE)
    for t in orb.trades:
        assert t.lane == "intraday"
        assert t.entry_ts.astype("datetime64[D]") == t.exit_ts.astype("datetime64[D]")
    swing = run_portfolio(data, lambda: SwingPullback(fast=10, mid=20, slow=50), costs=FREE)
    assert isinstance(swing.total_return, float)  # runs without error
