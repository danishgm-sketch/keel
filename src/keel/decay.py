"""Signal decay monitor — auto-retire edges that stop working.

Every real edge decays; the honest system watches for it. Given a strategy's
rolling out-of-sample performance over time (e.g. per-fold Sharpe or return from
the edge ledger / repeated walk-forwards), this flags when the recent window has
deteriorated versus the earlier record, so a fading strategy is demoted instead
of trusted out of habit.
"""

from __future__ import annotations


def assess_decay(series: list[float], recent: int = 4, min_history: int = 8) -> dict:
    """`series` is oldest→newest performance (Sharpe or return per period).
    Retire when the recent window is negative AND clearly worse than before."""
    n = len(series)
    if n < min_history:
        return {"retire": False, "reason": "insufficient history", "n": n}
    recent = min(recent, n // 2)
    early = series[:-recent]
    late = series[-recent:]
    early_mean = sum(early) / len(early)
    late_mean = sum(late) / len(late)
    retire = late_mean < 0 and late_mean < early_mean - abs(early_mean) * 0.5
    return {
        "retire": bool(retire),
        "early_mean": round(early_mean, 4),
        "late_mean": round(late_mean, 4),
        "reason": "recent OOS turned negative and fell well below its earlier record"
        if retire
        else "holding up",
        "n": n,
    }
