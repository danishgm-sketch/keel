"""LiveService — the always-on brain that starts when you open Keel.

Owns the broker, the meta-strategy trader, and a background scheduler. Each cycle
it (re)scans the **whole tradable market** down to the most liquid candidates,
pulls their recent bars in one batched request, and lets the meta-brain pick the
best play per name per moment. Degrades gracefully: no keys / no network → the UI
still runs and shows why the bot isn't live.
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from keel.config import Config, load_config
from keel.journal import Journal


class LiveService:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config: Config = load_config(self.data_dir)
        self.journal = Journal(self.data_dir / "journal.jsonl")
        self.broker = None
        self.broker_error: str | None = None
        self.trader = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._universe: list[str] = []
        self._bars: dict = {}
        self._last_scan = 0.0
        self._universe_day: str | None = None
        self._base_limits = (self.config.max_positions, self.config.max_new_per_day)
        self.latest_brain: dict = {"available": False}
        self.last_status: dict = {"note": "starting"}

    def _ensure_broker(self) -> None:
        try:
            from keel.broker import AlpacaBroker

            self.broker = AlpacaBroker()
            self.broker_error = None
        except Exception as e:
            self.broker = None
            self.broker_error = str(e)

    def _build_trader(self) -> None:
        from keel.roster import active_meta_factory
        from keel.trader import LiveTrader

        self.trader = LiveTrader(
            broker=self.broker,
            data_source=lambda sym: self._bars.get(sym),
            make_strategy=active_meta_factory(self.data_dir),
            config=self.config,
            journal=self.journal,
            armed=bool(self.config.autostart_armed),
        )

    # --- market scan (whole universe -> liquid candidates -> bars) ---
    def _refresh_universe(self) -> None:
        from keel.broker import tradable_symbols

        today = datetime.now(UTC).date().isoformat()
        if self._universe and self._universe_day == today:
            return
        try:
            self._universe = tradable_symbols(self.broker.list_assets())
            self._universe_day = today
        except Exception as e:
            self._last_error(f"universe error: {e}")

    def _scan(self) -> None:
        from keel.alpaca import fetch_bars_multi, fetch_snapshots
        from keel.scanner import rank_candidates

        cfg = self.config
        try:
            if cfg.universe:
                self._refresh_universe()
                snaps = fetch_snapshots(self._universe, feed=cfg.feed)
                candidates = rank_candidates(
                    snaps,
                    min_price=cfg.min_price,
                    min_dollar_volume=cfg.min_dollar_volume,
                    top_n=cfg.top_n,
                )
                cfg.watchlist = candidates or cfg.watchlist
            end = datetime.now(UTC)
            start = end - timedelta(days=10)
            self._bars = fetch_bars_multi(
                cfg.watchlist,
                start.date().isoformat(),
                end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                timeframe=cfg.timeframe,
                feed=cfg.feed,
            )
        except Exception as e:
            self._last_error(f"scan error: {e}")

    def _run_brain(self) -> None:
        """One AI reasoning pass; its recommendation can only tighten risk."""
        from keel.brain import apply_posture, run_brain_cycle

        base_mp, base_mn = self._base_limits
        try:
            result = run_brain_cycle(self.data_dir, self.status())
            self.latest_brain = result
            if result.get("available"):
                rec = result["recommendation"]
                mp, mn = apply_posture(base_mp, base_mn, rec["risk_posture"])
                self.config.max_positions, self.config.max_new_per_day = mp, mn
                self.journal.write("ai_briefing", **rec, provider=result.get("provider"))
            else:
                self.config.max_positions, self.config.max_new_per_day = base_mp, base_mn
        except Exception as e:
            self._last_error(f"brain error: {e}")

    def _last_error(self, msg: str) -> None:
        self.last_status = {**self.last_status, "note": msg}

    def start(self) -> None:
        self._ensure_broker()
        if self.broker is None:
            self.last_status = {"note": self.broker_error or "no broker", "armed": False}
            return
        self._build_trader()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while self._running and self.trader is not None:
            try:
                if time.time() - self._last_scan >= self.config.scan_seconds or not self._bars:
                    self._scan()
                    self._run_brain()  # AI reads the fresh state and sets posture
                    self._last_scan = time.time()
                self.last_status = self.trader.tick()
            except Exception as e:
                self.last_status = {"note": f"tick error: {e}", "armed": self.trader.armed}
            time.sleep(self.config.poll_seconds)

    def stop(self) -> None:
        self._running = False

    # --- control passthrough ---
    def arm(self) -> dict:
        if self.trader:
            self.trader.arm()
        return self.status()

    def disarm(self) -> dict:
        if self.trader:
            self.trader.disarm()
        return self.status()

    def kill(self) -> dict:
        if self.trader:
            self.trader.kill()
        return self.status()

    def status(self) -> dict:
        out = {
            "enabled": self.trader is not None,
            "broker_error": self.broker_error,
            "mode": "whole-market" if self.config.universe else "watchlist",
            "universe_size": len(self._universe),
            "candidates": list(self.config.watchlist),
            "config": {
                "strategy": "auto (meta-brain)",
                "timeframe": self.config.timeframe,
                "max_positions": self.config.max_positions,
                "max_new_per_day": self.config.max_new_per_day,
                "risk_fraction": self.config.risk_fraction,
                "top_n": self.config.top_n,
            },
            "last": self.last_status,
            "brain": self.latest_brain,
            "journal_today": self.journal.today()[-50:],
        }
        if self.broker is not None:
            try:
                acct = self.broker.get_account()
                out["account"] = {
                    "equity": acct.get("equity"),
                    "cash": acct.get("cash"),
                    "buying_power": acct.get("buying_power"),
                }
                out["clock"] = self.broker.get_clock()
                out["positions"] = [
                    {
                        "symbol": p.get("symbol"),
                        "qty": p.get("qty"),
                        "avg_entry_price": p.get("avg_entry_price"),
                        "unrealized_pl": p.get("unrealized_pl"),
                        "market_value": p.get("market_value"),
                    }
                    for p in self.broker.list_positions()
                ]
            except Exception as e:
                out["account_error"] = str(e)
        return out
