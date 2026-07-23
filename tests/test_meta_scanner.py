from __future__ import annotations

from conftest import make_intraday
from keel.broker import tradable_symbols
from keel.meta import MetaStrategy, default_subs
from keel.scanner import rank_candidates, snapshot_price_volume
from keel.strategy import Position


# --- meta-brain ---
def test_meta_warmup_is_max_of_subs():
    m = MetaStrategy()
    assert m.warmup == max(s.warmup for _, s in default_subs())


def test_meta_selects_and_delegates_without_error():
    m = MetaStrategy(reselect_every=5, recent_bars=200)
    bars = make_intraday("XYZ", n_sessions=12, bars_per_session=30, seed=1)
    chosen_seen = set()
    for i in range(m.warmup + 1, len(bars)):
        m.on_bar(bars.upto(i), None)
        if m.chosen_for("XYZ"):
            chosen_seen.add(m.chosen_for("XYZ"))
    assert chosen_seen  # it picked at least one concrete strategy
    assert chosen_seen <= {"rsi2", "orb", "swing"}


def test_meta_does_not_reroute_while_in_position():
    m = MetaStrategy(reselect_every=1)
    bars = make_intraday("XYZ", n_sessions=12, bars_per_session=30, seed=2)
    view = bars.upto(len(bars) - 1)
    m.on_bar(view, None)
    picked = m.chosen_for("XYZ")
    held = Position(entry_price=100.0, stop=95.0, shares=10, entry_index=len(view) - 1)
    m.on_bar(view, held)  # re-selection must be skipped while holding
    assert m.chosen_for("XYZ") == picked


# --- scanner ---
def test_snapshot_price_volume_reads_fields():
    snap = {"latestTrade": {"p": 12.5}, "dailyBar": {"v": 1_000_000, "c": 12.0}}
    price, vol = snapshot_price_volume(snap)
    assert price == 12.5 and vol == 1_000_000


def test_rank_candidates_filters_and_ranks():
    snaps = {
        "BIG": {"latestTrade": {"p": 100}, "dailyBar": {"v": 5_000_000}},  # $500M
        "MID": {"latestTrade": {"p": 20}, "dailyBar": {"v": 2_000_000}},  # $40M
        "PENNY": {"latestTrade": {"p": 1.0}, "dailyBar": {"v": 9_000_000}},  # price floor
        "THIN": {"latestTrade": {"p": 50}, "dailyBar": {"v": 1000}},  # $50k, too thin
    }
    out = rank_candidates(snaps, min_price=3.0, min_dollar_volume=5_000_000, top_n=10)
    assert out == ["BIG", "MID"]  # penny & thin filtered; ranked by dollar volume


def test_rank_candidates_respects_top_n():
    snaps = {
        f"S{i}": {"latestTrade": {"p": 10 + i}, "dailyBar": {"v": 10_000_000}} for i in range(20)
    }
    assert len(rank_candidates(snaps, top_n=5)) == 5


# --- universe filter ---
def test_tradable_symbols_filters():
    assets = [
        {"symbol": "AAPL", "tradable": True, "status": "active"},
        {"symbol": "OLD", "tradable": False, "status": "active"},
        {"symbol": "BRK.B", "tradable": True, "status": "active"},  # dot -> dropped
        {"symbol": "INACT", "tradable": True, "status": "inactive"},
    ]
    assert tradable_symbols(assets) == ["AAPL"]
