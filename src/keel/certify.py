"""Certify — the honesty gate, as a service.

Run any built-in strategy or ensemble through Keel's full validation — real
walk-forward, out-of-sample, block-bootstrap — and get back a plain verdict. In a
field drowning in fake backtests, an honest "certified or not" is the rarest
thing. This is the reusable form of what the whole system does to itself.

Built-in targets only, on purpose: loading arbitrary user code is the unsafe part
and is out of scope here. Contribute a strategy by adding it to the registry.
"""

from __future__ import annotations

from pathlib import Path

from keel.ensemble import EnsembleStrategy
from keel.portfolio import load_dir
from keel.roster import build_factory
from keel.walkforward import walk_forward

TARGETS = {
    "rsi2": lambda: build_factory("rsi2", {})(),
    "orb": lambda: build_factory("orb", {})(),
    "swing": lambda: build_factory("swing", {})(),
    "ensemble": lambda: EnsembleStrategy(),
}


def certify(data_dir: str | Path, target: str, train: int = 60, test: int = 20) -> dict:
    """Return an honest certificate for a built-in strategy/ensemble."""
    if target not in TARGETS:
        return {"error": f"unknown target {target!r}; choose from {sorted(TARGETS)}"}
    data = load_dir(data_dir)
    if not data:
        return {"error": f"no data in {data_dir} — fetch bars first"}

    factory = TARGETS[target]
    verdict = (
        walk_forward(data, variants=[(target, {})], train=train, test=test)
        if target in ("rsi2", "orb", "swing")
        else _wf_single(data, factory, train, test)
    )

    passed = verdict["beats_luck"] and verdict["n_folds"] >= 5
    return {
        "target": target,
        "certified": bool(passed),
        "oos_sharpe": verdict["oos_sharpe"],
        "oos_return": verdict["oos_total_return"],
        "pvalue": verdict["pvalue"],
        "folds": verdict["n_folds"],
        "statement": (
            "CERTIFIED: beat the block-bootstrap null out-of-sample across "
            f"{verdict['n_folds']} folds (p={verdict['pvalue']}). Not a promise of "
            "future returns — a statement that the past evidence is honest."
            if passed
            else "NOT CERTIFIED: did not beat luck out-of-sample. The honest verdict."
        ),
    }


def _wf_single(data, factory, train, test) -> dict:
    """Walk-forward a single non-registry strategy (e.g. the ensemble): trade it
    forward each fold and judge the concatenated out-of-sample curve."""
    import numpy as np

    from keel.portfolio import run_portfolio
    from keel.stats import bootstrap_pvalue, sharpe
    from keel.walkforward import _returns_by_date, all_session_dates, truncate

    dates = all_session_dates(data)
    oos: list[float] = []
    folds = 0
    i = train
    while i + test <= len(dates):
        test_dates = [str(d) for d in dates[i : i + test]]
        res = run_portfolio(truncate(data, dates[i + test - 1]), lambda: factory)
        rbd = _returns_by_date(res)
        got = [rbd[d] for d in test_dates if d in rbd]
        if got:
            oos.extend(got)
            folds += 1
        i += test
    arr = np.array(oos) if oos else np.zeros(0)
    pval = bootstrap_pvalue(arr) if len(arr) >= 20 else 1.0
    return {
        "n_folds": folds,
        "oos_sharpe": round(sharpe(arr), 2),
        "oos_total_return": round(float(np.prod(1 + arr) - 1), 4) if len(arr) else 0.0,
        "pvalue": round(pval, 4),
        "beats_luck": bool(pval < 0.05),
    }
