"""Alpaca market-data source — real bars into Keel's `Bars`, stdlib only.

Reads credentials from the environment (loaded from .env by `keel.env`):
``ALPACA_API_KEY`` and ``ALPACA_SECRET_KEY``. Credentials never leave the
process — they are sent only to Alpaca over HTTPS, never logged or persisted.

This is market *data* only. Nothing here can place an order.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

from keel.data import Bars

_DATA_URL = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"

TIMEFRAMES = {"1Min", "5Min", "15Min", "30Min", "1Hour", "1Day"}


class AlpacaError(RuntimeError):
    pass


def credentials() -> tuple[str, str]:
    key = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise AlpacaError(
            "ALPACA_API_KEY and ALPACA_SECRET_KEY not found. Put them in a .env "
            "file at your project root (keel loads it automatically)."
        )
    return key, secret


def _bars_from_rows(symbol: str, rows: list[dict]) -> Bars:
    """Build validated `Bars` from Alpaca bar dicts (t,o,h,l,c,v). Pure, no I/O."""
    if not rows:
        raise AlpacaError(f"{symbol}: no bars returned for the requested window")
    ts = np.array([np.datetime64(r["t"][:19], "s") for r in rows], dtype="datetime64[s]")
    o = np.array([float(r["o"]) for r in rows])
    h = np.array([float(r["h"]) for r in rows])
    lo = np.array([float(r["l"]) for r in rows])
    c = np.array([float(r["c"]) for r in rows])
    v = np.array([float(r.get("v", 0)) for r in rows])
    return Bars(symbol, ts, o, h, lo, c, v)


def fetch_bars(
    symbol: str,
    start: str,
    end: str,
    timeframe: str = "1Min",
    feed: str = "iex",
    limit: int = 10_000,
) -> Bars:
    """Fetch historical bars for one symbol (paginated). `start`/`end` are ISO
    dates or RFC3339 timestamps; `feed` is 'iex' (free) or 'sip' (paid)."""
    if timeframe not in TIMEFRAMES:
        raise AlpacaError(f"timeframe must be one of {sorted(TIMEFRAMES)}")
    key, secret = credentials()
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    rows: list[dict] = []
    page_token: str | None = None
    while True:
        params = {
            "timeframe": timeframe,
            "start": start,
            "end": end,
            "limit": limit,
            "feed": feed,
            "adjustment": "all",  # split & dividend adjusted
        }
        if page_token:
            params["page_token"] = page_token
        url = _DATA_URL.format(symbol=symbol) + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (https only)
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:  # pragma: no cover - network path
            raise AlpacaError(f"{symbol}: Alpaca HTTP {e.code} — {e.reason}") from e
        except urllib.error.URLError as e:  # pragma: no cover - network path
            raise AlpacaError(f"{symbol}: cannot reach Alpaca — {e.reason}") from e
        rows.extend(payload.get("bars") or [])
        page_token = payload.get("next_page_token")
        if not page_token:
            break
    return _bars_from_rows(symbol, rows)


_SNAPSHOTS_URL = "https://data.alpaca.markets/v2/stocks/snapshots"
_MULTIBARS_URL = "https://data.alpaca.markets/v2/stocks/bars"


def _get(url: str, params: dict, headers: dict) -> dict:
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 https only
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:  # pragma: no cover - network path
        raise AlpacaError(f"Alpaca HTTP {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:  # pragma: no cover - network path
        raise AlpacaError(f"cannot reach Alpaca: {e.reason}") from e


def fetch_snapshots(symbols: list[str], feed: str = "iex", batch: int = 100) -> dict:
    """Latest snapshot (price + daily bar) for many symbols, batched. Used by the
    scanner to rank the whole market by liquidity."""
    key, secret = credentials()
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    out: dict = {}
    for i in range(0, len(symbols), batch):
        chunk = symbols[i : i + batch]
        data = _get(_SNAPSHOTS_URL, {"symbols": ",".join(chunk), "feed": feed}, headers)
        out.update(data if isinstance(data, dict) else {})
    return out


def fetch_bars_multi(
    symbols: list[str],
    start: str,
    end: str,
    timeframe: str = "5Min",
    feed: str = "iex",
    batch: int = 100,
) -> dict[str, Bars]:
    """Recent bars for many symbols at once (one request per batch, paginated)."""
    key, secret = credentials()
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    rows: dict[str, list] = {}
    for i in range(0, len(symbols), batch):
        chunk = symbols[i : i + batch]
        token = None
        while True:
            params = {
                "symbols": ",".join(chunk),
                "timeframe": timeframe,
                "start": start,
                "end": end,
                "feed": feed,
                "adjustment": "all",
                "limit": 10_000,
            }
            if token:
                params["page_token"] = token
            data = _get(_MULTIBARS_URL, params, headers)
            for sym, bar_list in (data.get("bars") or {}).items():
                rows.setdefault(sym, []).extend(bar_list)
            token = data.get("next_page_token")
            if not token:
                break
    out: dict[str, Bars] = {}
    for sym, bar_rows in rows.items():
        try:
            out[sym] = _bars_from_rows(sym, bar_rows)
        except AlpacaError:
            continue
    return out


def save_csv(bars: Bars, out_dir: str | Path) -> Path:
    """Write bars as a `keel trade`-compatible CSV (date,open,high,low,close,volume)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{bars.symbol}.csv"
    lines = ["date,open,high,low,close,volume"]
    for i in range(len(bars)):
        lines.append(
            f"{bars.ts[i]},{bars.open[i]:.6f},{bars.high[i]:.6f},"
            f"{bars.low[i]:.6f},{bars.close[i]:.6f},{int(bars.volume[i])}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
