"""Qualitative feed — real news/catalysts per symbol from Alpaca.

This is the raw material for the qualitative limb: recent headlines the chart
cannot see (earnings, halts, M&A rumors, regulatory news, guidance). Data only —
stdlib HTTP, credentials from the environment, never logged.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

_NEWS_URL = "https://data.alpaca.markets/v1beta1/news"


class NewsError(RuntimeError):
    pass


def _headlines_from_payload(payload: dict) -> dict[str, list[str]]:
    """Pure: map Alpaca news items to {symbol: [headlines]} (newest first)."""
    out: dict[str, list[str]] = {}
    for item in payload.get("news", []) or []:
        headline = (item.get("headline") or "").strip()
        if not headline:
            continue
        for sym in item.get("symbols", []) or []:
            out.setdefault(sym, []).append(headline)
    return out


def news_digest(headlines: dict[str, list[str]], per_symbol: int = 3) -> dict[str, str]:
    """Compact the latest few headlines per symbol into one string."""
    return {sym: " | ".join(heads[:per_symbol]) for sym, heads in headlines.items() if heads}


def fetch_news(symbols: list[str], limit: int = 50) -> dict[str, list[str]]:
    """Recent headlines for the given symbols (single request, newest first)."""
    key = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise NewsError("ALPACA_API_KEY / ALPACA_SECRET_KEY not set")
    if not symbols:
        return {}
    params = {"symbols": ",".join(symbols), "limit": limit, "sort": "desc"}
    url = _NEWS_URL + "?" + urllib.parse.urlencode(params)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 https only
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:  # pragma: no cover - network path
        raise NewsError(f"Alpaca news HTTP {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:  # pragma: no cover - network path
        raise NewsError(f"cannot reach Alpaca news: {e.reason}") from e
    return _headlines_from_payload(payload)
