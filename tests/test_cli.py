from __future__ import annotations

import numpy as np

from keel.cli import main


def test_cli_run_prints_honest_verdict(tmp_path, capsys):
    rng = np.random.default_rng(11)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 300)))
    rows = ["date,open,high,low,close,volume"]
    day = np.datetime64("2022-01-03")
    prev = closes[0]
    for i, c in enumerate(closes):
        o = prev
        hi, lo = max(o, c) * 1.001, min(o, c) * 0.999
        rows.append(f"{day + i},{o:.4f},{hi:.4f},{lo:.4f},{c:.4f},1000")
        prev = c
    p = tmp_path / "rand.csv"
    p.write_text("\n".join(rows) + "\n")

    assert main(["run", str(p)]) == 0
    out = capsys.readouterr().out
    assert "rand:" in out
    assert "verdict:" in out
