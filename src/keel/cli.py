"""Command line: run a backtest on a CSV of bars and report honestly.

keel run path/to/bars.csv [--fast 20 --slow 50] [--risk 0.01]
"""

from __future__ import annotations

import argparse
import sys

from keel import __version__
from keel.backtest import run
from keel.data import load_csv
from keel.stats import bootstrap_pvalue, sharpe
from keel.strategy import SmaCross


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="keel", description=__doc__)
    parser.add_argument("--version", action="version", version=f"keel {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="backtest the example SMA-cross strategy on a CSV")
    p_run.add_argument("csv", help="CSV with columns date,open,high,low,close,volume")
    p_run.add_argument("--symbol", default=None)
    p_run.add_argument("--fast", type=int, default=20)
    p_run.add_argument("--slow", type=int, default=50)
    p_run.add_argument("--risk", type=float, default=0.01)

    args = parser.parse_args(argv)
    bars = load_csv(args.csv, args.symbol)
    result = run(bars, SmaCross(args.fast, args.slow), risk_fraction=args.risk)
    pval = bootstrap_pvalue(result.returns)

    wins = sum(1 for t in result.trades if t.pnl > 0)
    print(
        f"{result.symbol}: {len(bars)} bars, {len(result.trades)} trades "
        f"({wins} wins), total return {result.total_return:+.2%}, "
        f"Sharpe {sharpe(result.returns):.2f}"
    )
    print(f"bootstrap p-value vs block-resampled null: {pval:.3f}")
    if pval >= 0.05:
        print(
            "verdict: NOT distinguishable from luck on this series. "
            "That is the honest default; do not tune until it flips."
        )
    else:
        print(
            "verdict: interesting on THIS series only — one p-value is not an "
            "edge. Test out-of-sample and across the multiple-testing budget."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
