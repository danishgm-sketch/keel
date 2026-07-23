"""Market scanner — turn the whole tradable universe into a shortlist.

The system has access to every active US equity. It cannot trade all of them at
once (nor should it), so each cycle the scanner ranks the market by liquidity and
hands the trader the top-N names worth considering right now. Liquidity first,
because an edge that only exists in names you can't fill is not an edge.

Pure functions over Alpaca snapshot dicts — no network here, so it is fully
testable.
"""

from __future__ import annotations


def snapshot_price_volume(snap: dict) -> tuple[float, float]:
    """Best-effort (price, daily share volume) from an Alpaca snapshot."""
    price = 0.0
    for key in ("latestTrade", "minuteBar", "dailyBar"):
        node = snap.get(key) or {}
        px = node.get("p") or node.get("c")
        if px:
            price = float(px)
            break
    daily = snap.get("dailyBar") or {}
    volume = float(daily.get("v") or 0)
    return price, volume


def rank_candidates(
    snapshots: dict,
    min_price: float = 3.0,
    max_price: float = 2000.0,
    min_dollar_volume: float = 5_000_000.0,
    top_n: int = 40,
) -> list[str]:
    """Filter by price band and dollar-volume floor, then rank by dollar volume
    (a robust liquidity proxy) and return the top N symbols."""
    scored: list[tuple[float, str]] = []
    for sym, snap in snapshots.items():
        price, volume = snapshot_price_volume(snap)
        if price < min_price or price > max_price or volume <= 0:
            continue
        dollar_volume = price * volume
        if dollar_volume < min_dollar_volume:
            continue
        scored.append((dollar_volume, sym))
    scored.sort(reverse=True)
    return [sym for _, sym in scored[:top_n]]
