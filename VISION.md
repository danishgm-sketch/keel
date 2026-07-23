# Keel — Vision

> A keel is the backbone of a ship: the part you never see, that keeps you
> upright and lets you sail *into* the wind instead of only downwind. That is
> what this project is to a trading operation.

## The one-line vision

**Keel is an honest, multi-asset systematic trading platform — from research to
live execution — where every dollar of risk is earned by evidence, not hope.**

Today Keel is a single-asset, backtest-only research kit (~1,000 lines). The
100x version is a full systematic-trading operation you could actually run real
capital through. The expansion is in *capability and reach*, never in the
willingness to fool ourselves. The default verdict stays "not distinguishable
from luck" until the evidence overturns it.

## Why "honest" is the moat, not the marketing

The trading world is not short of backtests that print money and then lose it
live. It is short of research infrastructure that is *engineered to refuse a
false edge*. Almost every retail and a majority of professional attempts fail
for the same three reasons Keel is specifically built against:

1. **Survivorship / look-ahead / point-in-time bugs** → Keel makes them
   structurally impossible (dated universe membership, history-slice views,
   next-open fills).
2. **Multiple-testing self-deception** → Keel ships Benjamini–Hochberg FDR and
   a stationary block-bootstrap null in v0.1, applied to *every* variant tried,
   including failures.
3. **No gate between "interesting" and "risk real money"** → Keel inherits a
   hard, evidence-plus-explicit-unlock gate before a single live order.

That discipline *is* the edge for a small operator. It is worth money before a
single alpha is found, because the largest realized "return" in this game is
the capital you did **not** lose to a strategy that was always noise.

## The five capability layers (the 100x)

Keel grows outward in layers. Each layer is only built when a validated need
pulls it into existence — no cathedral of empty modules (the mistake we buried
with Bastion).

### 1. Data — the foundation of everything
- **Multi-asset**: US + global equities, futures (continuous, roll-aware), FX,
  and crypto (24/7, accessible, less efficient — the natural first live venue
  for small capital). Options later.
- **Point-in-time everything**: corporate actions, index membership,
  fundamentals as-reported (not as-restated), delistings.
- **Multi-source with reconciliation** and a real local store
  (Parquet/DuckDB), replacing the toy CSV loader.

### 2. Alpha research — from one strategy to a signal factory
- A **signal/factor framework**: cross-sectional and time-series, composable
  and independently testable.
- **ML done correctly**: purged, embargoed walk-forward cross-validation
  (López de Prado), feature store, and — critically — the same FDR gate applied
  to model search so a grid search can't manufacture a phantom edge.
- A **research ledger**: every hypothesis, every variant, every p-value,
  recorded. The trial count that feeds the deflation penalty is the *true* one.

### 3. Portfolio construction — from one position to a book
- Volatility targeting, risk parity, mean-variance with covariance shrinkage,
  fractional-Kelly sizing, and hard constraints.
- A **factor risk model** so exposures are understood, not accidental.
- Correlation-aware allocation *across* strategies, so the book is more than the
  sum of its bets.

### 4. Execution & live trading — where discipline meets reality
- Broker/exchange adapters (Alpaca, Interactive Brokers, crypto venues) behind
  one interface.
- An **order-management layer** with paper→live parity, fill reconciliation, and
  cost attribution (did we actually pay what the model assumed?).
- The **honest live-gate**: real data → clean walk-forward → out-of-sample proof
  → forward-paper proof → paper-vs-live tracking within tolerance → explicit
  human unlock. No automatic path to real money exists until every gate is green.

### 5. Risk, ops & monitoring — staying alive
- Real-time drawdown controls, exposure limits, and a kill switch that is tested
  as rigorously as the sizing math.
- Monitoring, alerting, daily reconciliation, and reporting a human can read in
  sixty seconds.

## What Keel is *for* — real use cases

1. **A serious solo/small-team systematic operation.** Run a diversified,
   cost-aware, risk-targeted program on modest capital and compound it over
   years with institutional-grade discipline.
2. **A capital-preservation engine.** Even used only to *reject* bad ideas, Keel
   pays for itself by keeping you out of strategies that were noise.
3. **The research backbone of a future fund or managed accounts.** The audit
   trail (every bet, every p-value, every live-gate decision) is exactly what an
   allocator, an auditor, or a regulator asks for.
4. **A picks-and-shovels product.** The honest research harness itself is
   valuable to others — the platform can be the business even when the trades
   are modest.

## The honest money question

Read this part twice. The value of Keel is that it will not lie to you here, so
it should not start now.

**There is no button that prints money.** Consistently beating the market on a
risk-adjusted basis is one of the hardest things in finance; most who try —
retail *and* professional — do not. Anyone promising otherwise is selling
something. Keel's job is to make the honest version of this achievable, and to
tell you the truth about which tier you are actually in:

- **Tier 0 — Don't lose money to false edges.** Highest-certainty value.
  Realized as capital *preserved*. This is available on day one and it is real.
- **Tier 1 — Harvest known risk premia efficiently.** Trend-following/managed
  futures, cross-asset carry and momentum, the volatility risk premium, equity
  style factors. These are *documented and accessible without HFT
  infrastructure*. A well-run, diversified, vol-targeted program has
  historically aimed at a **Sharpe of roughly 0.5–1.0** — meaning at, say, 12%
  targeted volatility, **~6–15% annual returns in good regimes, with genuine
  15–25% drawdowns and multi-year flat stretches, and no guarantee of any of
  it.** This is a years-long compounding-and-discipline game, not a windfall.
- **Tier 2 — Genuine niche inefficiency (true alpha).** Rare, usually
  capacity-constrained, and most attempts to find it fail. Keel's FDR gate
  exists precisely so you know the difference between finding one and imagining
  one.
- **Tier 3 — Sell the infrastructure.** Sometimes the platform, the research
  service, or managed accounts are the more reliable business than the trades.

**Honest risk warning:** leverage, systematic option selling, and crypto can add
tail risk that wipes an account in a day. Small accounts also fight cost and
time drag that large ones don't. The realistic ambition is *a disciplined,
diversified systematic program that earns risk-adjusted returns over years and
could become the foundation of something larger* — not getting rich quickly.

## The principle that governs all of it

Ambition scales without limit. Honesty does not bend. Every capability above is
built only when evidence pulls it in, gated behind the falsifiable bets in
`RESEARCH_BETS.md`. Keel earns the right to risk each new dollar; it never
assumes it.
