"""The meta-brain — picks the best strategy for *this symbol, this moment*.

Instead of running one fixed strategy, `MetaStrategy` chooses, per symbol, the
sub-strategy that has performed best on that symbol's recent history, and
delegates the current decision to it. It re-selects periodically, so as the
regime shifts (trending vs choppy vs volatile) the routing shifts with it. That
is the "mind of its own": at every decision it asks "which of my proven plays
fits what's happening right now?" and uses that one.

Honesty spine intact: it only ever chooses among strategies already in the
playbook, the selection rule is simple and interpretable (recent realized
return, with a trade-count floor so it can't chase a single fluke), and the whole
meta-policy is itself judged by `walk_forward` out-of-sample. Smart, not mystical.
"""

from __future__ import annotations

from keel.backtest import run
from keel.data import Bars
from keel.strategies import OpeningRangeBreakout, Rsi2Reversion, SwingPullback
from keel.strategy import Decision, Position


def default_subs() -> list[tuple[str, object]]:
    return [
        ("rsi2", Rsi2Reversion()),
        ("orb", OpeningRangeBreakout()),
        ("swing", SwingPullback()),
    ]


class MetaStrategy:
    def __init__(
        self,
        subs: list[tuple[str, object]] | None = None,
        reselect_every: int = 30,
        recent_bars: int = 300,
        min_trades: int = 3,
    ):
        self.subs = subs if subs is not None else default_subs()
        self.warmup = max(s.warmup for _, s in self.subs)
        self.reselect_every = reselect_every
        self.recent_bars = recent_bars
        self.min_trades = min_trades
        self._choice: dict[str, tuple[str, object]] = {}
        self._age: dict[str, int] = {}
        self.lane = "intraday"
        self.session_flat = True
        self.last_name: str | None = None

    def _score(self, history: Bars, sub) -> float:
        """Recent realized return of `sub` on this symbol's last `recent_bars`."""
        window = history.tail(self.recent_bars)
        if len(window) <= sub.warmup:
            return -1e18
        res = run(window, sub)
        if len(res.trades) < self.min_trades:
            return -1e18
        return res.total_return

    def select(self, history: Bars) -> tuple[str, object] | None:
        best = None
        for name, sub in self.subs:
            if len(history) <= sub.warmup:
                continue
            score = self._score(history, sub)
            if best is None or score > best[0]:
                best = (score, name, sub)
        return (best[1], best[2]) if best else None

    def on_bar(self, history: Bars, position: Position | None) -> Decision:
        sym = history.symbol
        stale = self._age.get(sym, self.reselect_every) >= self.reselect_every
        # Never re-route while a position is open — finish the trade with the
        # strategy that opened it.
        if position is None and (sym not in self._choice or stale):
            chosen = self.select(history)
            if chosen is not None:
                self._choice[sym] = chosen
                self._age[sym] = 0
        self._age[sym] = self._age.get(sym, 0) + 1
        if sym not in self._choice:
            return None
        name, sub = self._choice[sym]
        self.last_name = name
        self.lane = getattr(sub, "lane", "intraday")
        self.session_flat = getattr(sub, "session_flat", True)
        return sub.on_bar(history, position)

    def chosen_for(self, symbol: str) -> str | None:
        c = self._choice.get(symbol)
        return c[0] if c else None
