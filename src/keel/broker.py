"""Alpaca broker client — PAPER ONLY, by construction.

The base URL is the paper endpoint and there is no code path to the live
trading endpoint. Turning on real money is a deliberate future decision that
must pass the honest gates first; it is not a flag you can flip by accident
here. This client only talks to paper.

Stdlib urllib; credentials from the environment (loaded by `keel.env`), sent
only to Alpaca over HTTPS, never logged.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

PAPER_BASE = "https://paper-api.alpaca.markets"

# Live trading is intentionally not implemented. This constant documents intent;
# there is deliberately no LIVE_BASE and no way to target it from this module.
LIVE_TRADING_ENABLED = False


class BrokerError(RuntimeError):
    pass


class AlpacaBroker:
    """Thin paper-trading client. Duck-typed so a FakeBroker can stand in for
    tests and dry-runs."""

    def __init__(self, base_url: str = PAPER_BASE):
        if base_url != PAPER_BASE:
            raise BrokerError("Keel only trades the Alpaca PAPER endpoint.")
        self.base = base_url
        key = os.getenv("ALPACA_API_KEY")
        secret = os.getenv("ALPACA_SECRET_KEY")
        if not key or not secret:
            raise BrokerError("ALPACA_API_KEY / ALPACA_SECRET_KEY not set (put them in .env).")
        self._headers = {
            "APCA-API-KEY-ID": key,
            "APCA-API-SECRET-KEY": secret,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, body: dict | None = None) -> dict | list:
        url = self.base + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 https only
                raw = resp.read().decode()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:  # pragma: no cover - network path
            detail = e.read().decode(errors="replace")
            raise BrokerError(f"Alpaca {method} {path} -> HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:  # pragma: no cover - network path
            raise BrokerError(f"cannot reach Alpaca: {e.reason}") from e

    # --- read ---
    def get_account(self) -> dict:
        return self._request("GET", "/v2/account")  # type: ignore[return-value]

    def get_clock(self) -> dict:
        return self._request("GET", "/v2/clock")  # type: ignore[return-value]

    def list_positions(self) -> list:
        return self._request("GET", "/v2/positions")  # type: ignore[return-value]

    def list_orders(self, status: str = "open") -> list:
        return self._request("GET", f"/v2/orders?status={status}")  # type: ignore[return-value]

    # --- write ---
    def submit_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        order_type: str = "market",
        time_in_force: str = "day",
        stop_price: float | None = None,
        limit_price: float | None = None,
    ) -> dict:
        body: dict = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
        }
        if stop_price is not None:
            body["stop_price"] = str(round(stop_price, 2))
        if limit_price is not None:
            body["limit_price"] = str(round(limit_price, 2))
        return self._request("POST", "/v2/orders", body)  # type: ignore[return-value]

    def submit_bracket(
        self,
        symbol: str,
        qty: int,
        stop_price: float,
        take_profit: float | None = None,
        time_in_force: str = "day",
    ) -> dict:
        """Buy with a protective stop that rests SERVER-SIDE, so a dropped
        connection or a sleeping laptop can never leave a naked position. Uses a
        bracket (stop + target) when a target is given, else a stop-attached
        one-triggers-other order."""
        body: dict = {
            "symbol": symbol,
            "qty": str(qty),
            "side": "buy",
            "type": "market",
            "time_in_force": time_in_force,
            "stop_loss": {"stop_price": str(round(stop_price, 2))},
        }
        if take_profit is not None:
            body["order_class"] = "bracket"
            body["take_profit"] = {"limit_price": str(round(take_profit, 2))}
        else:
            body["order_class"] = "oto"
        return self._request("POST", "/v2/orders", body)  # type: ignore[return-value]

    def close_position(self, symbol: str) -> dict:
        return self._request("DELETE", f"/v2/positions/{symbol}")  # type: ignore[return-value]

    def close_all_positions(self) -> list:
        return self._request("DELETE", "/v2/positions?cancel_orders=true")  # type: ignore[return-value]

    def cancel_all_orders(self) -> list:
        return self._request("DELETE", "/v2/orders")  # type: ignore[return-value]

    def list_assets(self) -> list:
        """Every active, tradable US equity — the whole market."""
        return self._request(  # type: ignore[return-value]
            "GET", "/v2/assets?status=active&asset_class=us_equity"
        )


def tradable_symbols(assets: list) -> list[str]:
    """Pure filter: symbols that are active, tradable, and not weird (no dots/
    slashes that the data API won't like)."""
    out = []
    for a in assets:
        sym = a.get("symbol", "")
        if a.get("tradable") and a.get("status") == "active" and sym.isalpha():
            out.append(sym)
    return out
