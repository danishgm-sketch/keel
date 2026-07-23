from __future__ import annotations

import csv

from conftest import make_intraday
from keel.env import load_env
from keel.ui import backtest_payload


def _write_dir(tmp_path, n=5):
    for i in range(n):
        b = make_intraday(f"S{i}", n_sessions=8, seed=i)
        with (tmp_path / f"S{i}.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "open", "high", "low", "close", "volume"])
            for k in range(len(b)):
                w.writerow([str(b.ts[k]), b.open[k], b.high[k], b.low[k], b.close[k], 1000])
    return tmp_path


def test_payload_has_everything_the_dashboard_renders(tmp_path):
    _write_dir(tmp_path)
    p = backtest_payload(tmp_path, "rsi2", {"max_new_per_day": 20})
    for key in (
        "total_return",
        "sharpe",
        "pvalue",
        "beats_luck",
        "costs_paid",
        "gross_pnl",
        "equity",
        "per_day",
        "recent_trades",
        "trades_per_day",
    ):
        assert key in p
    assert p["equity"]["values"]
    assert isinstance(p["beats_luck"], bool)


def test_payload_empty_dir(tmp_path):
    assert "error" in backtest_payload(tmp_path, "rsi2", {})


def test_payload_unknown_strategy(tmp_path):
    _write_dir(tmp_path, n=1)
    try:
        backtest_payload(tmp_path, "nope", {})
    except ValueError as e:
        assert "unknown strategy" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_load_env_reads_file(tmp_path, monkeypatch):
    monkeypatch.delenv("KEEL_TEST_VAR", raising=False)
    (tmp_path / ".env").write_text('KEEL_TEST_VAR="hello"\n# comment\n')
    loaded = load_env(tmp_path)
    assert loaded is not None
    import os

    assert os.environ["KEEL_TEST_VAR"] == "hello"
