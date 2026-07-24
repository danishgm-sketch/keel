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
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from keel.config import Config, load_config
from keel.intelligence import KeelRuntime, build_state
from keel.intelligence.policy import LegacyLlmShadowPolicy, NoModelPolicy
from keel.intelligence.state_builder import RuntimeInputs
from keel.journal import Journal
from keel.operations.database import open_database
from keel.operations.incidents import IncidentCategory, IncidentSeverity, new_incident


class LiveService:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config: Config = load_config(self.data_dir)
        # Stable identity for this running process — stamped on journal and state.
        self.process_instance_id = uuid.uuid4().hex[:12]
        self.deployment_id = "dev-local"
        self.journal = Journal(
            self.data_dir / "journal.jsonl",
            process_instance_id=self.process_instance_id,
            deployment_id=self.deployment_id,
        )
        # Durable truth store + shadow intelligence runtime. The runtime OBSERVES
        # each cycle and records a decision; it never mutates limits or places
        # orders. A general LLM is admitted only as a shadow challenger.
        self.db = open_database(self.data_dir)
        self.intelligence = KeelRuntime(
            policy=LegacyLlmShadowPolicy() if self.config.qualitative else NoModelPolicy()
        )
        self.latest_intel: dict = {"available": False}
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
        self.latest_overlay: dict = {"avoid": [], "notes": {}}
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
        """LEGACY posture application (default OFF, gated by config.legacy_posture_apply).

        When enabled, the old brain recommendation directly tightens the live limits.
        In the v1 architecture this path is superseded by the shadow intelligence
        runtime, which observes without ever mutating limits. It can only tighten
        risk; it can never loosen it."""
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

    def _build_inputs(self) -> RuntimeInputs:
        """Snapshot the live runtime into explicit, validated intelligence inputs.

        Missing or unconfirmed safety facts stay degraded — never asserted healthy.
        We only mark a position 'protected' when the broker reports a confirmed
        stop order for it, and broker reconciliation is only True after a clean
        account/positions read."""
        from keel.brain import _read_json, _tail_jsonl

        edge = _tail_jsonl(self.data_dir / "edge_ledger.jsonl", 1)
        roster = _read_json(self.data_dir / "roster.json") or {}
        champ = roster.get("champion")
        certified = tuple(
            r["strategy"]
            for r in roster.get("variants", [])
            if r.get("survived") and r.get("strategy")
        )

        inp = RuntimeInputs(
            deployment_id=self.deployment_id,
            candidate_id="baseline",
            model_bundle_id=self.intelligence.policy.model_bundle_id,
            process_instance_id=self.process_instance_id,
            edge_row=(edge[-1] if edge else None),
            champion=(champ.get("strategy") if isinstance(champ, dict) else champ),
            certified_strategies=certified,
            active_strategies=(self.config.strategy,),
            risk_fraction=self.config.risk_fraction,
            market_feed_healthy=bool(self._bars),
            database_healthy=self.db.healthy(),
            journal_healthy=self.journal.verify()[0],
            open_incidents=self.db.count_open_incidents(),
            observation_ts=datetime.now(UTC),
        )

        if self.broker is not None:
            try:
                acct = self.broker.get_account()
                positions = self.broker.list_positions()
                clock = self.broker.get_clock()
                # A position is 'protected' only if the broker holds an open stop
                # order guarding it — anything we cannot confirm stays unprotected.
                protected: set[str] = set()
                try:
                    for o in self.broker.list_orders(status="open"):
                        otype = str(o.get("type", "")).lower()
                        if "stop" in otype and o.get("symbol"):
                            protected.add(o["symbol"])
                except Exception:
                    protected = set()
                inp.account = acct
                inp.positions = positions
                inp.clock = clock
                inp.protected_symbols = frozenset(protected)
                inp.broker_reachable = True
                inp.broker_reconciled = True
                inp.pending_orders = 0
            except Exception as e:
                # Broker read failed — leave degraded defaults and raise an incident.
                inp.broker_reachable = False
                inp.broker_reconciled = False
                self._raise_incident(
                    IncidentCategory.BROKER_RECONCILIATION_FAILURE,
                    IncidentSeverity.ERROR,
                    f"broker reconciliation failed: {e}",
                )
        return inp

    def _raise_incident(self, category, severity, message: str) -> None:
        try:
            self.db.record_incident(
                new_incident(category, severity, message, deployment_id=self.deployment_id)
            )
        except Exception as e:
            self._last_error(f"incident error: {e}")

    def _run_intelligence(self) -> None:
        """One shadow intelligence pass. Builds the canonical state, evaluates the
        deterministic baseline and any shadow proposal, validates fail-closed, and
        records a durable, auditable decision. It NEVER mutates trading limits,
        risk, strategy activation, or places orders."""
        try:
            state = build_state(self._build_inputs())
            result = self.intelligence.evaluate(state)
            summary = KeelRuntime.summarise(result)
            correlation_id = uuid.uuid4().hex[:12]
            try:
                decision_id = self.db.record_shadow(result, correlation_id=correlation_id)
                summary["decision_id"] = decision_id
            except Exception as e:
                self._raise_incident(
                    IncidentCategory.DATABASE_FAILURE,
                    IncidentSeverity.ERROR,
                    f"failed to persist shadow decision: {e}",
                )
            self.journal.write("intelligence_shadow", correlation_id=correlation_id, **summary)
            summary["available"] = True
            self.latest_intel = summary
        except Exception as e:
            self._last_error(f"intelligence error: {e}")
            self.latest_intel = {"available": False, "error": str(e)}

    def _run_overlay(self) -> None:
        """The qualitative parallel limb: read candidate news and set the trader's
        veto blocklist. It can only remove names from fresh entry, never add."""
        if not self.config.qualitative or self.trader is None:
            return
        try:
            from keel.catalysts import fetch_news, news_digest
            from keel.llm import pick_provider
            from keel.overlay import assess

            candidates = list(self.config.watchlist)[: self.config.top_n]
            if not candidates:
                return
            digests = news_digest(fetch_news(candidates))
            result = assess(pick_provider(), digests, set(candidates))
            self.latest_overlay = result
            self.trader.blocklist = set(result["avoid"])
            if result["avoid"]:
                self.journal.write("qualitative_veto", avoid=result["avoid"])
        except Exception as e:
            self._last_error(f"overlay error: {e}")

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
                    self._run_intelligence()  # v1: observe + record, never mutate limits
                    if self.config.legacy_posture_apply:
                        self._run_brain()  # legacy: directly tighten limits (default off)
                    self._run_overlay()  # qualitative limb: news veto of entries
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

    def _intelligence_status(self) -> dict:
        """Surface the shadow runtime's latest observation for the UI/CLI. Read-only."""
        intel = dict(self.latest_intel)
        intel["mode"] = "shadow"  # v1 is always shadow — the AI cannot apply
        intel["model_bundle"] = self.intelligence.policy.model_bundle_id
        intel["legacy_posture_apply"] = bool(self.config.legacy_posture_apply)
        try:
            intel["open_incidents"] = self.db.count_open_incidents()
            intel["database_healthy"] = self.db.healthy()
        except Exception:
            intel["database_healthy"] = False
        intel["journal_healthy"] = self.journal.verify()[0]
        return intel

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
            "overlay": self.latest_overlay,
            "intelligence": self._intelligence_status(),
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
