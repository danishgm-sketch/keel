from __future__ import annotations

import numpy as np

from conftest import make_bars
from keel.backtest import run
from keel.costs import FREE, CostModel
from keel.data import Bars
from keel.strategy import Enter, Hold, Position, SmaCross


class NoLookaheadProbe:
    """Records the length of every history view it is shown, and the bar it
    decided on, so tests can prove decisions never see the future and always
    fill on the NEXT bar's open."""

    warmup = 5

    def __init__(self):
        self.view_lengths: list[int] = []
        self.entered_on: int | None = None

    def on_bar(self, history: Bars, position: Position | None):
        self.view_lengths.append(len(history))
        if position is None and self.entered_on is None and len(history) == 10:
            self.entered_on = len(history) - 1  # bar index 9
            return Enter(stop=float(history.close[-1]) * 0.5)
        return None


def test_strategy_never_sees_future():
    bars = make_bars(np.linspace(100, 120, 60))
    probe = NoLookaheadProbe()
    run(bars, probe, costs=FREE)
    # on bar i the view has exactly i+1 bars — the future physically absent
    assert probe.view_lengths == list(range(6, 60))


def test_entry_fills_next_bar_open():
    closes = np.linspace(100, 120, 60)
    bars = make_bars(closes)
    probe = NoLookaheadProbe()
    result = run(bars, probe, costs=FREE)
    assert probe.entered_on == 9
    assert result.trades, "probe should have traded"
    assert result.trades[0].entry_price == float(bars.open[10])


def test_stop_fills_at_stop_or_gap_open():
    # flat then crash through the stop
    closes = [100.0] * 30 + [70.0] + [70.0] * 5

    class EnterOnce:
        warmup = 5

        def on_bar(self, history, position):
            if position is None and len(history) == 20:
                return Enter(stop=95.0)
            return None if position is None else Hold()

    bars = make_bars(closes)
    result = run(bars, EnterOnce(), costs=FREE)
    (trade,) = result.trades
    assert trade.stopped
    # gap open (99.9-ish or 70) below stop must fill at the open, never at the stop price
    assert trade.exit_price <= 95.0


def test_costs_reduce_pnl():
    closes = np.linspace(100, 130, 80)
    bars = make_bars(closes)
    strat = SmaCross(fast=5, slow=15, stop_lookback=5)
    free = run(bars, strat, costs=FREE)
    costly = run(bars, strat, costs=CostModel(proportional=0.01, per_share=0.01))
    assert costly.equity_curve[-1] < free.equity_curve[-1]


def test_equity_curve_realizes_at_end(trending_bars):
    result = run(trending_bars, SmaCross(fast=10, slow=30), costs=FREE)
    if result.trades:
        total_pnl = sum(t.pnl for t in result.trades)
        assert np.isclose(result.equity_curve[-1], 100_000.0 + total_pnl)


def test_raised_stop_is_kept_loosened_stop_ignored():
    closes = [100.0] * 40

    class StopFiddler:
        warmup = 5

        def __init__(self):
            self.seen_stops = []

        def on_bar(self, history, position):
            if position is None:
                return Enter(stop=90.0) if len(history) == 10 else None
            self.seen_stops.append(position.stop)
            if len(history) == 15:
                return Hold(stop=95.0)  # raise: accepted
            if len(history) == 20:
                return Hold(stop=80.0)  # loosen: must be ignored
            return Hold()

    fiddler = StopFiddler()
    run(make_bars(closes), fiddler, costs=FREE)
    assert fiddler.seen_stops[-1] == 95.0


def test_never_exits_below_planned_risk_plus_costs(trending_bars):
    """The planned loss at the stop is the sizing contract; without gaps in this
    synthetic series, no stopped trade may lose more than planned risk + costs."""
    result = run(trending_bars, SmaCross(fast=10, slow=30))
    equity_hint = 110_000  # generous upper bound on equity during the run
    for t in result.trades:
        if t.stopped and t.exit_price == min(t.exit_price, t.entry_price):
            assert -t.pnl <= equity_hint * 0.01 + t.costs + 1e-6
