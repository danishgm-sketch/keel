from __future__ import annotations

import numpy as np

from conftest import make_intraday
from keel.walkforward import (
    all_session_dates,
    record_edge,
    truncate,
    walk_forward,
)

SMALL = [("rsi2", {"entry_level": 10.0}), ("orb", {"or_bars": 6})]


def _data(n=4, sessions=120):
    return {
        f"S{i}": make_intraday(f"S{i}", n_sessions=sessions, bars_per_session=10, seed=i)
        for i in range(n)
    }


def test_truncate_keeps_only_past():
    data = _data(n=2, sessions=30)
    dates = all_session_dates(data)
    cut = dates[15]
    tdata = truncate(data, cut, min_bars=1)
    for bars in tdata.values():
        assert bars.ts.astype("datetime64[D]").max() <= cut


def test_walk_forward_returns_oos_verdict():
    data = _data(n=4, sessions=120)
    v = walk_forward(data, variants=SMALL, train=40, test=20)
    assert v["n_folds"] >= 2
    assert "beats_luck" in v and isinstance(v["beats_luck"], bool)
    assert v["oos_days"] >= 0
    # picks are chosen only from history before each test window
    assert all("champion" in p for p in v["picks"])


def test_walk_forward_no_lookahead_dates_increase():
    data = _data(n=3, sessions=120)
    v = walk_forward(data, variants=SMALL, train=40, test=20)
    ends = [p["train_end"] for p in v["picks"]]
    assert ends == sorted(ends)  # folds march forward in time


def test_record_edge_appends(tmp_path):
    verdict = {"pvalue": 1.0, "beats_luck": False, "oos_sharpe": 0.0, "picks": [{"x": 1}]}
    record_edge(tmp_path, verdict)
    record_edge(tmp_path, verdict)
    lines = (tmp_path / "edge_ledger.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    import json

    assert "picks" not in json.loads(lines[0])  # ledger stays compact


def test_short_history_is_honest_not_crash():
    data = {
        f"S{i}": make_intraday(f"S{i}", n_sessions=10, bars_per_session=8, seed=i) for i in range(2)
    }
    v = walk_forward(data, variants=SMALL, train=40, test=20)
    assert v["n_folds"] == 0
    assert v["beats_luck"] is False
    assert np.isclose(v["oos_total_return"], 0.0)
