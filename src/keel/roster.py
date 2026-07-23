"""Evolution — the *disciplined* kind.

`evolve` is how Keel's playbook grows without fooling itself. It searches a space
of strategy variants, evaluates each with a real train/test split, and promotes
only those that (a) beat the block-bootstrap null in-sample **after**
Benjamini–Hochberg correction across every variant tried, AND (b) still beat it
out-of-sample. Survivors are written to `roster.json`; the best survivor becomes
the champion the live trader runs.

What this deliberately does NOT do: rewrite risk management, tune toward recent
noise, or promote anything that only looks good in-sample. Risk sizing is a
constant. Growth means *validated* additions to the playbook, not self-mutation.
If nothing survives, the honest outcome is "no champion" and the trader keeps the
default — that is a feature.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from keel.portfolio import load_dir, run_portfolio
from keel.stats import benjamini_hochberg, bootstrap_pvalue, sharpe
from keel.strategies import OpeningRangeBreakout, Rsi2Reversion, SwingPullback

ROSTER_NAME = "roster.json"

# The search space. Each entry: (strategy_name, params). Kept small on purpose —
# a huge grid is just more ways to overfit; FDR punishes breadth anyway.
VARIANTS: list[tuple[str, dict]] = [
    ("rsi2", {"entry_level": 5.0}),
    ("rsi2", {"entry_level": 10.0}),
    ("rsi2", {"entry_level": 15.0}),
    ("rsi2", {"entry_level": 10.0, "exit_level": 50.0}),
    ("rsi2", {"entry_level": 10.0, "exit_level": 70.0}),
    ("orb", {"or_bars": 3}),
    ("orb", {"or_bars": 6}),
    ("orb", {"or_bars": 10}),
    ("swing", {"fast": 10, "mid": 20, "slow": 50}),
    ("swing", {"fast": 20, "mid": 50, "slow": 200}),
]

_CLASSES = {"rsi2": Rsi2Reversion, "orb": OpeningRangeBreakout, "swing": SwingPullback}


def build_factory(strategy: str, params: dict):
    cls = _CLASSES[strategy]
    return lambda: cls(**params)


def _split_pvalues(data, factory) -> tuple[float, float, dict]:
    """Run the book, split the daily-return series 70/30, and return
    (in-sample p, out-of-sample p, metrics)."""
    res = run_portfolio(data, factory)
    rets = res.returns
    if len(rets) < 40:
        return 1.0, 1.0, {"trades": len(res.trades), "sharpe": 0.0, "ret": 0.0}
    cut = int(len(rets) * 0.7)
    is_p = bootstrap_pvalue(rets[:cut], n_iter=500)
    oos = rets[cut:]
    oos_p = bootstrap_pvalue(oos, n_iter=500) if len(oos) >= 20 else 1.0
    metrics = {
        "trades": len(res.trades),
        "trades_per_day": round(res.trades_per_day, 2),
        "sharpe_oos": round(sharpe(oos), 2),
        "ret_oos": round(float(np.prod(1 + oos) - 1), 4),
    }
    return is_p, oos_p, metrics


def evolve(
    data_dir: str | Path,
    q: float = 0.10,
    extra_variants: list[tuple[str, dict]] | None = None,
) -> dict:
    """Evaluate every variant, apply FDR in-sample, confirm out-of-sample, and
    write roster.json. Returns the summary dict.

    `extra_variants` (e.g. LLM-proposed) are appended to the fixed search space
    and judged by the same gates — proposal never means promotion."""
    data = load_dir(data_dir)
    if not data:
        return {"error": f"no data in {data_dir} — fetch bars first"}

    candidates = list(VARIANTS) + list(extra_variants or [])
    rows = []
    for strategy, params in candidates:
        is_p, oos_p, metrics = _split_pvalues(data, build_factory(strategy, params))
        rows.append(
            {
                "strategy": strategy,
                "params": params,
                "is_p": round(is_p, 4),
                "oos_p": round(oos_p, 4),
                **metrics,
            }
        )

    is_sig = benjamini_hochberg([r["is_p"] for r in rows], q=q)
    for r, sig in zip(rows, is_sig, strict=True):
        r["is_significant"] = bool(sig)
        r["survived"] = bool(sig and r["oos_p"] < 0.05)

    survivors = [r for r in rows if r["survived"]]
    champion = max(survivors, key=lambda r: r.get("sharpe_oos", 0.0), default=None)
    summary = {
        "generated": datetime.now(UTC).isoformat(),
        "q": q,
        "n_variants": len(rows),
        "variants": rows,
        "champion": (
            {"strategy": champion["strategy"], "params": champion["params"]} if champion else None
        ),
    }
    path = Path(data_dir) / ROSTER_NAME
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def load_roster(data_dir: str | Path) -> dict | None:
    p = Path(data_dir) / ROSTER_NAME
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def active_factory(data_dir: str | Path, default_strategy: str = "rsi2"):
    """The champion strategy factory if evolution has produced one, else the
    configured default. This is what the live trader runs."""
    roster = load_roster(data_dir)
    if roster and roster.get("champion"):
        c = roster["champion"]
        return c["strategy"], build_factory(c["strategy"], c["params"])
    return default_strategy, build_factory(default_strategy, {})
