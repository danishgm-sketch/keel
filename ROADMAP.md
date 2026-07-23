# Keel — Roadmap

Every phase ends in a **falsifiable gate**. If the gate is not met, we do not
advance — we do not "build ahead" into unproven capability. This is the rule
that keeps the 100x vision from becoming a cathedral around an empty vault.

No new infrastructure is built while a research bet is open (`RESEARCH_BETS.md`).
Infrastructure is pulled into existence by a validated need, never pushed ahead
of one.

---

## Phase 0 — Honest core ✅ (done)

Walk-forward engine, PIT universe, block-bootstrap null, Benjamini–Hochberg FDR,
fixed-fractional sizing from stop, per-fill costs, CLI with an honest default
verdict. 30 tests, CI green on Linux + Windows × 3.11/3.12.

**Gate met:** the harness demonstrably refuses look-ahead and flatters nothing.

---

## Phase 1 — Data foundation & the known-anomaly check

Build a real data layer and prove the harness can *detect an effect that is
known to exist* before it is ever pointed at novel ideas.

- Real ingestion (Alpaca equities + a crypto venue), Parquet/DuckDB store.
- Point-in-time corporate actions, split/dividend adjustment, delistings.
- Multi-asset `Bars` (roll-aware continuous futures; 24/7 crypto sessions).

**Gate:** reproduce cross-sectional equity momentum on a survivorship-free,
point-in-time universe with a bootstrap p-value that survives BH at realistic
costs. If a *known* anomaly won't show up cleanly, the harness is wrong and
nothing downstream is trustworthy.

---

## Phase 2 — Portfolio & risk-premia program

Move from one strategy/one position to a diversified book.

- Signal/factor framework (cross-sectional + time-series), composable.
- Portfolio construction: volatility targeting, risk parity, covariance
  shrinkage, fractional-Kelly caps, hard constraints.
- A diversified multi-asset trend + carry program as the first real candidate.

**Gate:** a full walk-forward of the *portfolio* (not a single strategy) shows
positive, out-of-sample, cost-and-slippage-net risk-adjusted return, with the
whole variant search accounted for under FDR.

---

## Phase 3 — Forward paper → small live

Cross the line to reality, slowly, behind the honest gate.

- Broker/exchange execution adapters behind one interface.
- Order-management layer, paper→live parity, fill reconciliation, realized-cost
  attribution.
- Real-time risk: drawdown limits, exposure caps, tested kill switch.

**Gate:** forward-paper tracks the backtest within tolerance, and paper-vs-live
fills track within tolerance, *before* real capital scales past a token size.
The live unlock remains an explicit, recorded human decision.

---

## Phase 4 — Scale, allocate, productize

- Multiple uncorrelated programs; capital allocated across them by their
  realized, out-of-sample track records.
- Monitoring, alerting, daily reconciliation, human-readable reporting.
- Optional: research platform, managed accounts, or a data/research product —
  the picks-and-shovels business.

**Gate:** a live, multi-program track record long enough to mean something,
with every decision auditable end to end.

---

## What we will *not* do

- Add capability a research bet has not pulled in.
- Treat a PROVISIONAL or single-sample result as an edge.
- Build a live path that can risk real money without passing every gate.
- Promise returns. Keel reports evidence; the market decides the rest.
