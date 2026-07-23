from __future__ import annotations

import numpy as np

from keel.stats import benjamini_hochberg, bootstrap_pvalue, sharpe, stationary_bootstrap_indices


def test_sharpe_zero_on_degenerate_input():
    assert sharpe(np.array([])) == 0.0
    assert sharpe(np.array([0.01])) == 0.0
    assert sharpe(np.full(50, 0.01)) == 0.0  # zero variance


def test_bootstrap_refuses_tiny_samples():
    assert bootstrap_pvalue(np.array([0.05] * 10)) == 1.0


def test_bootstrap_pvalue_high_for_noise():
    rng = np.random.default_rng(1)
    noise = rng.normal(0.0, 0.01, 500)
    assert bootstrap_pvalue(noise, n_iter=300) > 0.05


def test_bootstrap_pvalue_low_for_strong_drift():
    rng = np.random.default_rng(2)
    drifty = rng.normal(0.004, 0.005, 500)
    assert bootstrap_pvalue(drifty, n_iter=300) < 0.05


def test_bootstrap_pvalue_never_zero():
    assert bootstrap_pvalue(np.full(100, 0.01) + 1e-6, n_iter=100) > 0.0


def test_bootstrap_indices_cover_length():
    rng = np.random.default_rng(3)
    idx = stationary_bootstrap_indices(257, 20.0, rng)
    assert len(idx) == 257
    assert idx.min() >= 0 and idx.max() < 257


def test_bh_no_discoveries_on_uniform_noise():
    rng = np.random.default_rng(4)
    p = rng.uniform(0.2, 1.0, 100)
    assert benjamini_hochberg(p, q=0.05).sum() == 0


def test_bh_finds_real_signal_among_noise():
    rng = np.random.default_rng(5)
    p = np.concatenate([[1e-6, 1e-5], rng.uniform(0.2, 1.0, 98)])
    mask = benjamini_hochberg(p, q=0.05)
    assert mask[0] and mask[1]
    assert mask.sum() == 2


def test_bh_empty_input():
    assert benjamini_hochberg([]).sum() == 0
