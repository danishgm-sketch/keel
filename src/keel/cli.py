"""Command line.

    keel run   path/to/bars.csv                 single-symbol SMA-cross demo
    keel trade path/to/csv_dir --strategy rsi2   high-turnover multi-symbol book

`trade` runs the multi-symbol engine over every CSV in a directory (one symbol
per file), fires many intraday/swing trades a day at the next-open with realistic
costs, and reports the honest bootstrap verdict on the daily equity curve.
"""

from __future__ import annotations

import argparse
import sys

from keel import __version__
from keel.backtest import run
from keel.costs import CostModel
from keel.data import load_csv
from keel.portfolio import load_dir, run_portfolio
from keel.stats import bootstrap_pvalue, sharpe
from keel.strategies import OpeningRangeBreakout, Rsi2Reversion, SwingPullback
from keel.strategy import SmaCross

STRATEGIES = {
    "rsi2": Rsi2Reversion,
    "orb": OpeningRangeBreakout,
    "swing": SwingPullback,
}


def _verdict(pval: float) -> str:
    if pval >= 0.05:
        return (
            "verdict: NOT distinguishable from luck. That is the honest default — "
            "at this turnover, costs are the enemy; do not tune to beat noise."
        )
    return (
        "verdict: beats the block-bootstrap null on THIS sample. One p-value is not "
        "an edge — confirm out-of-sample and under the multiple-testing budget before "
        "risking a cent."
    )


def _cmd_run(args) -> int:
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
    print(_verdict(pval))
    return 0


def _cmd_fetch(args) -> int:
    from keel.alpaca import fetch_bars, save_csv
    from keel.env import load_env

    loaded = load_env()
    if loaded:
        print(f"loaded credentials from {loaded}")
    for sym in args.symbols:
        sym = sym.upper()
        bars = fetch_bars(sym, args.start, args.end, timeframe=args.timeframe, feed=args.feed)
        path = save_csv(bars, args.out)
        print(f"{sym}: {len(bars)} bars -> {path}")
    print(f"done. run:  keel trade {args.out} --strategy rsi2")
    return 0


def _cmd_ui(args) -> int:
    from keel.ui import run_ui

    run_ui(args.dir, port=args.port, open_browser=not args.no_browser)
    return 0


def _cmd_app(args) -> int:
    from keel.app import run_app

    run_app(args.dir, port=args.port)
    return 0


def _cmd_trade_live(args) -> int:
    import time

    from keel.env import load_env
    from keel.service import LiveService

    load_env()
    service = LiveService(args.dir)
    service.start()
    if service.trader is None:
        print(f"bot not started: {service.broker_error}")
        return 1
    print(f"paper bot running (armed={service.trader.armed}). Ctrl+C to stop.")
    try:
        while True:
            time.sleep(service.config.poll_seconds)
            s = service.last_status
            print(f"  {s.get('note', '')} | trades_today={s.get('trades_today', '?')}")
    except KeyboardInterrupt:
        service.stop()
        print("\nstopped (positions left as-is; use the UI KILL to flatten)")
    return 0


def _cmd_evolve(args) -> int:
    from keel.env import load_env
    from keel.roster import evolve, load_roster

    load_env()
    extra = []
    if args.use_llm:
        from keel.advisor import propose_variants
        from keel.llm import pick_provider

        llm = pick_provider(args.prefer)
        if llm is None:
            print("no LLM available (no Ollama running, no API keys) — skipping proposals")
        else:
            prev = load_roster(args.dir)
            context = "First run." if not prev else f"Previous champion: {prev.get('champion')}"
            extra = propose_variants(llm, context, n=args.n)
            print(f"{llm.name} proposed {len(extra)} variant(s) to test")
    summary = evolve(args.dir, q=args.q, extra_variants=extra)
    if "error" in summary:
        print(summary["error"])
        return 1
    champ = summary["champion"]
    survivors = [r for r in summary["variants"] if r["survived"]]
    print(f"evaluated {summary['n_variants']} variants, {len(survivors)} survived the gate")
    for r in survivors:
        print(f"  {r['strategy']} {r['params']}  oos_sharpe={r.get('sharpe_oos')}")
    print(f"champion: {champ or 'NONE (honest — keep the default, no validated edge)'}")
    return 0


def _cmd_walkforward(args) -> int:
    from keel.env import load_env
    from keel.walkforward import run_walkforward

    load_env()
    v = run_walkforward(args.dir, train=args.train, test=args.test)
    if "error" in v:
        print(v["error"])
        return 1
    print(
        f"walk-forward: {v['n_folds']} folds, {v['oos_days']} out-of-sample days | "
        f"OOS return {v['oos_total_return']:+.2%}, OOS Sharpe {v['oos_sharpe']}"
    )
    print(f"bootstrap p-value on the OUT-OF-SAMPLE curve: {v['pvalue']}")
    if v["beats_luck"]:
        print(
            "VERDICT: the adaptive system beat luck out-of-sample here. Real, but "
            "keep accumulating folds — this is the number that gates live money."
        )
    else:
        print(
            "VERDICT: no out-of-sample edge yet. This is the honest state of the "
            "system today; adding features will not change it — finding signal will."
        )
    print("(appended to edge_ledger.jsonl — the truth tracked over time)")
    return 0


def _cmd_llm(args) -> int:
    from keel.env import load_env
    from keel.llm import (
        ClaudeProvider,
        GeminiProvider,
        OllamaProvider,
        pick_provider,
        recommend_ollama_model,
        total_ram_gb,
    )

    load_env()
    if args.action == "recommend":
        ram = total_ram_gb()
        model = recommend_ollama_model(ram)
        print(f"detected ~{ram:.0f} GB RAM -> recommended local model: {model}")
        print(f"install it with:  ollama pull {model}")
        return 0
    if args.action == "status":
        print(f"ollama running: {OllamaProvider.available()}")
        print(f"claude key present: {ClaudeProvider().available()}")
        print(f"gemini key present: {GeminiProvider().available()}")
        p = pick_provider(args.prefer)
        print(f"active provider: {p.name if p else 'NONE'}")
        return 0
    # test
    p = pick_provider(args.prefer)
    if p is None:
        print("no provider available")
        return 1
    print(f"[{p.name}] {p.complete('Reply with exactly: keel llm online', system='Be terse.')}")
    return 0


def _cmd_trade(args) -> int:
    data = load_dir(args.dir)
    if not data:
        print(f"no CSVs found in {args.dir}")
        return 1
    strat_cls = STRATEGIES[args.strategy]
    result = run_portfolio(
        data,
        strat_cls,
        starting_equity=args.equity,
        risk_fraction=args.risk,
        max_positions=args.max_positions,
        max_new_per_day=args.max_new_per_day,
        costs=CostModel(proportional=args.spread, per_share=args.per_share),
    )
    rets = result.returns
    gross = sum(t.pnl + t.costs for t in result.trades)
    print(
        f"{args.strategy}: {len(data)} symbols, {len(result.daily_dates)} sessions, "
        f"{len(result.trades)} trades ({result.trades_per_day:.1f}/day, "
        f"{result.win_rate:.0%} win)"
    )
    print(
        f"net total return {result.total_return:+.2%}  |  Sharpe {sharpe(rets):.2f}  |  "
        f"costs paid {result.total_costs:,.0f} on {gross:+,.0f} gross P&L"
    )
    pval = bootstrap_pvalue(rets)
    print(f"bootstrap p-value vs block-resampled null: {pval:.3f}")
    print(_verdict(pval))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="keel", description=__doc__)
    parser.add_argument("--version", action="version", version=f"keel {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="single-symbol SMA-cross demo on one CSV")
    p_run.add_argument("csv", help="CSV with columns date,open,high,low,close,volume")
    p_run.add_argument("--symbol", default=None)
    p_run.add_argument("--fast", type=int, default=20)
    p_run.add_argument("--slow", type=int, default=50)
    p_run.add_argument("--risk", type=float, default=0.01)
    p_run.set_defaults(func=_cmd_run)

    p_tr = sub.add_parser("trade", help="high-turnover multi-symbol book over a CSV dir")
    p_tr.add_argument("dir", help="directory of per-symbol CSVs")
    p_tr.add_argument("--strategy", choices=sorted(STRATEGIES), default="rsi2")
    p_tr.add_argument("--equity", type=float, default=100_000.0)
    p_tr.add_argument("--risk", type=float, default=0.01)
    p_tr.add_argument("--max-positions", type=int, default=10, dest="max_positions")
    p_tr.add_argument("--max-new-per-day", type=int, default=20, dest="max_new_per_day")
    p_tr.add_argument(
        "--spread",
        type=float,
        default=0.0005,
        help="per-side proportional cost (half-spread + slippage)",
    )
    p_tr.add_argument("--per-share", type=float, default=0.0002, dest="per_share")
    p_tr.set_defaults(func=_cmd_trade)

    p_f = sub.add_parser("fetch", help="download real bars from Alpaca (uses .env)")
    p_f.add_argument("symbols", nargs="+", help="ticker symbols, e.g. AAPL MSFT")
    p_f.add_argument("--start", required=True, help="ISO date, e.g. 2024-01-01")
    p_f.add_argument("--end", required=True, help="ISO date, e.g. 2024-03-01")
    p_f.add_argument(
        "--timeframe", default="1Min", help="1Min | 5Min | 15Min | 30Min | 1Hour | 1Day"
    )
    p_f.add_argument("--feed", default="iex", help="iex (free) or sip (paid)")
    p_f.add_argument("--out", default="data", help="output directory")
    p_f.set_defaults(func=_cmd_fetch)

    p_ui = sub.add_parser("ui", help="launch the local dashboard")
    p_ui.add_argument("--dir", default="data", help="data directory to browse")
    p_ui.add_argument("--port", type=int, default=8787)
    p_ui.add_argument("--no-browser", action="store_true", dest="no_browser")
    p_ui.set_defaults(func=_cmd_ui)

    p_app = sub.add_parser("app", help="open the desktop app (native window if available)")
    p_app.add_argument("--dir", default="data", help="data directory to browse")
    p_app.add_argument("--port", type=int, default=None)
    p_app.set_defaults(func=_cmd_app)

    p_tl = sub.add_parser("trade-live", help="run the automated PAPER bot headless")
    p_tl.add_argument("--dir", default="data")
    p_tl.set_defaults(func=_cmd_trade_live)

    p_ev = sub.add_parser("evolve", help="search + validate strategy variants, promote survivors")
    p_ev.add_argument("--dir", default="data")
    p_ev.add_argument("--q", type=float, default=0.10, help="FDR level")
    p_ev.add_argument(
        "--use-llm",
        action="store_true",
        dest="use_llm",
        help="let an LLM propose extra variants (still gated)",
    )
    p_ev.add_argument("--prefer", default=None, help="ollama | claude | gemini")
    p_ev.add_argument("--n", type=int, default=5, help="LLM proposals to request")
    p_ev.set_defaults(func=_cmd_evolve)

    p_wf = sub.add_parser("walkforward", help="honest out-of-sample test of the adaptive system")
    p_wf.add_argument("--dir", default="data")
    p_wf.add_argument("--train", type=int, default=60, help="training sessions per fold")
    p_wf.add_argument("--test", type=int, default=20, help="out-of-sample sessions per fold")
    p_wf.set_defaults(func=_cmd_walkforward)

    p_llm = sub.add_parser("llm", help="LLM provider status / model recommendation / test")
    p_llm.add_argument(
        "action", choices=["status", "recommend", "test"], default="status", nargs="?"
    )
    p_llm.add_argument("--prefer", default=None, help="ollama | claude | gemini")
    p_llm.set_defaults(func=_cmd_llm)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
