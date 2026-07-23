"""Statistics that can say "no".

- Stationary block bootstrap (Politis & Romano 1994): the null preserves the
  volatility clustering and short-range dependence of real returns, unlike an
  IID shuffle, which faces a strategy with an unrealistically easy opponent.
- Benjamini–Hochberg FDR control for testing many strategies at once. It ships
  in v0.1 because multiple-testing control that is "deferred" is absent.
"""

from __future__ import annotations

import numpy as np


def sharpe(returns: np.ndarray, periods_per_year: int = 252) -> float:
    r = np.asarray(returns, dtype=float)
    if len(r) < 2 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1) * np.sqrt(periods_per_year))


def stationary_bootstrap_indices(n: int, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    """Index sequence for one stationary-bootstrap resample of length n:
    geometric block lengths (mean `mean_block`), wrap-around starts."""
    if n <= 0:
        return np.empty(0, dtype=int)
    p = 1.0 / max(mean_block, 1.0)
    idx = np.empty(n, dtype=int)
    pos = 0
    while pos < n:
        start = rng.integers(0, n)
        length = min(rng.geometric(p), n - pos)
        idx[pos : pos + length] = (start + np.arange(length)) % n
        pos += length
    return idx


def bootstrap_pvalue(
    returns: np.ndarray,
    n_iter: int = 1000,
    mean_block: float = 20.0,
    seed: int = 0,
) -> float:
    """One-sided p-value for H0: mean return <= 0, against a stationary block
    bootstrap of the demeaned return series. Small p = the observed mean is
    unlikely to be luck of this series' own dependence structure.

    Uses the add-one estimator (Davison & Hinkley), so p is never exactly 0 —
    no result can look infinitely significant.
    """
    r = np.asarray(returns, dtype=float)
    if len(r) < 20:
        return 1.0  # too little data to say anything; refuse to flatter
    observed = r.mean()
    centered = r - observed
    rng = np.random.default_rng(seed)
    hits = sum(
        centered[stationary_bootstrap_indices(len(r), mean_block, rng)].mean() >= observed
        for _ in range(n_iter)
    )
    return (hits + 1) / (n_iter + 1)


def benjamini_hochberg(pvalues: list[float] | np.ndarray, q: float = 0.05) -> np.ndarray:
    """Boolean mask of discoveries controlling the false-discovery rate at q.
    Every strategy variant you evaluated goes in the list — including the ones
    that failed. Leaving failures out is how self-deception gets back in."""
    p = np.asarray(pvalues, dtype=float)
    m = len(p)
    if m == 0:
        return np.zeros(0, dtype=bool)
    order = np.argsort(p)
    thresholds = q * (np.arange(1, m + 1) / m)
    below = p[order] <= thresholds
    cutoff = np.max(np.nonzero(below)[0]) if below.any() else -1
    mask = np.zeros(m, dtype=bool)
    if cutoff >= 0:
        mask[order[: cutoff + 1]] = True
    return mask
