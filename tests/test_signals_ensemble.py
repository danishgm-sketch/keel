from __future__ import annotations

from conftest import make_intraday
from keel.ensemble import Ensemble, EnsembleStrategy
from keel.signals import SIGNAL_NAMES, default_signals


def _bars():
    return make_intraday("X", n_sessions=12, bars_per_session=30, seed=3)


def test_signals_score_in_unit_interval():
    bars = _bars()
    for s in default_signals():
        for i in range(s.warmup + 1, len(bars), 20):
            v = s.score(bars.upto(i))
            assert 0.0 <= v <= 1.0


def test_signal_names_are_unique():
    assert len(SIGNAL_NAMES) == len(set(SIGNAL_NAMES))


def test_ensemble_conviction_bounded_and_weighted():
    bars = _bars()
    ens = Ensemble()
    view = bars.upto(len(bars) - 1)
    assert 0.0 <= ens.conviction(view) <= 1.0
    # zero weights -> zero conviction
    zero = Ensemble(weights={n: 0.0 for n in SIGNAL_NAMES})
    assert zero.conviction(view) == 0.0


def test_ensemble_contributions_cover_all_signals():
    ens = Ensemble()
    c = ens.contributions(_bars().upto(300))
    assert set(c) == set(SIGNAL_NAMES)


def test_ensemble_strategy_enters_on_high_conviction():
    # force conviction high by weighting only signals and lowering the entry bar
    strat = EnsembleStrategy(entry=0.01, exit_=0.0)
    bars = _bars()
    seen_enter = False
    from keel.strategy import Enter

    for i in range(strat.warmup + 1, len(bars)):
        d = strat.on_bar(bars.upto(i), None)
        if isinstance(d, Enter):
            assert d.stop < bars.close[i]
            seen_enter = True
            break
    assert seen_enter


def test_ensemble_runs_through_the_engine():
    from keel.portfolio import run_portfolio

    data = {f"S{i}": make_intraday(f"S{i}", n_sessions=10, seed=i) for i in range(3)}
    res = run_portfolio(data, lambda: EnsembleStrategy(entry=0.4))
    assert isinstance(res.total_return, float)  # gated like any strategy
