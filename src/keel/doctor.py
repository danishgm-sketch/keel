"""`keel doctor` — the whole machine's honest state in one view.

A real running machine needs a single place that answers: is it wired up, does it
have data, has it found any edge yet, and is it safe? This reads the local state
(and optionally pings the broker and the LLM) and reports it plainly — including
the honest verdict that there is no proven edge, when that is the truth.
"""

from __future__ import annotations

from pathlib import Path

from keel.config import load_config


def diagnose(data_dir: str | Path, check_network: bool = False) -> dict:
    data_dir = Path(data_dir)
    cfg = load_config(data_dir)

    csvs = sorted(p.stem for p in data_dir.glob("*.csv"))

    roster = _read_json(data_dir / "roster.json")
    champion = roster.get("champion") if roster else None
    survivors = sum(1 for r in roster.get("variants", []) if r.get("survived")) if roster else 0

    edge = _last_jsonl(data_dir / "edge_ledger.jsonl")
    has_edge = bool(edge and edge.get("beats_luck"))

    report: dict = {
        "data_symbols": len(csvs),
        "config": {
            "mode": "whole-market" if cfg.universe else "watchlist",
            "timeframe": cfg.timeframe,
            "risk_fraction": cfg.risk_fraction,
            "qualitative_limb": cfg.qualitative,
        },
        "roster": {"champion": champion, "validated_survivors": survivors},
        "edge": {
            "has_proven_edge": has_edge,
            "last_pvalue": edge.get("pvalue") if edge else None,
            "last_oos_sharpe": edge.get("oos_sharpe") if edge else None,
            "folds": edge.get("n_folds") if edge else None,
        },
        "brain_memory": _count_lines(data_dir / "brain_memory.jsonl"),
    }

    if check_network:
        report["broker"] = _check_broker()
        report["llm"] = _check_llm()

    report["verdict"] = _verdict(report)
    return report


def _verdict(report: dict) -> str:
    if report["data_symbols"] == 0:
        return "NOT READY — no market data yet. Run `keel fetch` or let the bot scan."
    if report["edge"]["has_proven_edge"]:
        return (
            "EDGE PRESENT out-of-sample on the last walk-forward — real, but keep "
            "accumulating folds before trusting size. This is what gates live money."
        )
    return (
        "HONEST STATE: no proven edge yet. The machine is wired and safe; it should "
        "trade minimally/defensively while research continues. This is correct, not a bug."
    )


def _check_broker() -> dict:
    try:
        from keel.broker import AlpacaBroker

        clock = AlpacaBroker().get_clock()
        return {"reachable": True, "market_open": clock.get("is_open")}
    except Exception as e:
        return {"reachable": False, "reason": str(e)[:120]}


def _check_llm() -> dict:
    try:
        from keel.llm import pick_provider

        p = pick_provider()
        return {"available": p is not None, "provider": getattr(p, "name", None)}
    except Exception as e:
        return {"available": False, "reason": str(e)[:120]}


def _read_json(path: Path) -> dict | None:
    import json

    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _last_jsonl(path: Path) -> dict | None:
    import json

    if not path.is_file():
        return None
    lines = [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    return json.loads(lines[-1]) if lines else None


def _count_lines(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(1 for x in path.read_text(encoding="utf-8").splitlines() if x.strip())
