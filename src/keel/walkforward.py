"""Walk-forward validation — the honest test of the *evolving* system.

`evolve` uses a single train/test split to pick a champion. That answers "did
this variant look good once?" It does not answer the real question: **does the
adaptive process itself — pick a champion on the past, trade it forward, repeat —
make money out-of-sample?** That is what walk-forward measures, and it is the one
number that should gate real money.

The procedure (anchored, expanding history, non-overlapping test windows):

    for each fold:
        history up to train_end  ->  pick the champion by in-sample Sharpe
        trade THAT champion across the next `test` sessions (out-of-sample)
        append those out-of-sample returns
    the concatenated OOS curve is the system's true track record

Then the block-bootstrap null judges the whole OOS curve. No look-ahead: each
fold's champion is chosen only from data before the window it is judged on.

Every run is appended to `edge_ledger.jsonl` so the answer is tracked over time
as data accumulates — the honest version of "it keeps getting better".
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from keel.data import Bars
from keel.indicators import session_dates
from keel.portfolio import PortfolioResult, load_dir, run_portfolio
from keel.roster import VARIANTS, build_factory
from keel.stats import bootstrap_pvalue, sharpe

EDGE_LEDGER = "edge_ledger.jsonl"


def _mask_bars(bars: Bars, mask: np.ndarray) -> Bars:
    return Bars(
        bars.symbol,
        bars.ts[mask],
        bars.open[mask],
        bars.high[mask],
        bars.low[mask],
        bars.close[mask],
        bars.volume[mask],
    )


def truncate(data: dict[str, Bars], upto: np.datetime64, min_bars: int = 30) -> dict[str, Bars]:
    """All history for each symbol with session date <= `upto` (gives warmup,
    never the future)."""
    out: dict[str, Bars] = {}
    for sym, bars in data.items():
        mask = session_dates(bars.ts) <= upto
        if int(mask.sum()) >= min_bars:
            out[sym] = _mask_bars(bars, mask)
    return out


def _returns_by_date(res: PortfolioResult) -> dict[str, float]:
    if len(res.daily_equity) < 2:
        return {}
    rets = np.diff(res.daily_equity) / res.daily_equity[:-1]
    return {str(d): float(r) for d, r in zip(res.daily_dates[1:], rets, strict=True)}


def all_session_dates(data: dict[str, Bars]) -> list[np.datetime64]:
    seen: set = set()
    for bars in data.values():
        seen.update(session_dates(bars.ts).tolist())
    return sorted(seen)


def walk_forward(
    data: dict[str, Bars],
    variants=VARIANTS,
    train: int = 60,
    test: int = 20,
    min_trades: int = 8,
) -> dict:
    """Roll the pick-champion-then-trade-forward process across history and judge
    the concatenated out-of-sample curve."""
    dates = all_session_dates(data)
    oos: list[float] = []
    picks: list[dict] = []
    i = train
    while i + test <= len(dates):
        train_dates = {str(d) for d in dates[i - train : i]}
        train_end = dates[i - 1]
        tdata = truncate(data, train_end)

        best = None
        for strategy, params in variants:
            res = run_portfolio(tdata, build_factory(strategy, params))
            if len(res.trades) < min_trades:
                continue
            rbd = _returns_by_date(res)
            tw = np.array([r for d, r in rbd.items() if d in train_dates])
            if len(tw) > 5:
                sh = sharpe(tw)
                if best is None or sh > best[0]:
                    best = (sh, strategy, params)

        if best is not None:
            test_dates = [str(d) for d in dates[i : i + test]]
            res = run_portfolio(
                truncate(data, dates[i + test - 1]), build_factory(best[1], best[2])
            )
            rbd = _returns_by_date(res)
            fold_oos = [rbd[d] for d in test_dates if d in rbd]
            oos.extend(fold_oos)
            picks.append(
                {
                    "train_end": str(train_end),
                    "champion": f"{best[1]} {best[2]}",
                    "train_sharpe": round(best[0], 2),
                    "oos_days": len(fold_oos),
                }
            )
        i += test

    arr = np.array(oos) if oos else np.zeros(0)
    pval = bootstrap_pvalue(arr) if len(arr) >= 20 else 1.0
    return {
        "n_folds": len(picks),
        "oos_days": len(arr),
        "oos_sharpe": round(sharpe(arr), 2),
        "oos_total_return": round(float(np.prod(1 + arr) - 1), 4) if len(arr) else 0.0,
        "pvalue": round(pval, 4),
        "beats_luck": bool(pval < 0.05),
        "picks": picks,
    }


def record_edge(data_dir: str | Path, verdict: dict) -> Path:
    """Append a walk-forward verdict to the edge ledger (the truth over time)."""
    path = Path(data_dir) / EDGE_LEDGER
    row = {
        "ts": datetime.now(UTC).isoformat(),
        **{k: v for k, v in verdict.items() if k != "picks"},
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return path


def run_walkforward(data_dir: str | Path, train: int = 60, test: int = 20) -> dict:
    data = load_dir(data_dir)
    if not data:
        return {"error": f"no data in {data_dir} — fetch bars first"}
    verdict = walk_forward(data, train=train, test=test)
    record_edge(data_dir, verdict)
    return verdict
