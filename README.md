# Keel

An honest systematic-trading platform — research to live execution — where every
dollar of risk is earned by evidence. Successor to Bastion, built from its
audit: the discipline stays, the cathedral goes.

Today this repo is the honest research core (Phase 0). The full vision — where it
goes and the realistic money-making case — is in **[VISION.md](VISION.md)**; the
evidence-gated path is in **[ROADMAP.md](ROADMAP.md)**.

## What it is (today)

- **PIT-first data**: the tradeable universe carries dated membership
  (`universe.py`); there is no code path that backfills today's list into the
  past, so survivorship bias is structurally impossible rather than "stamped".
- **One walk-forward backtest loop** (`backtest.py`): strategies see only a
  physical slice of history, decisions fill at the next bar's open, resting
  stops fill at the stop or the gap open, costs are charged on every fill.
- **Statistics that can say no** (`stats.py`): stationary block bootstrap null
  (preserves volatility clustering — no IID-shuffle strawman) and
  Benjamini–Hochberg FDR control. Shipped in v0.1, not deferred.
- **Fixed-fractional risk from stop** (`risk.py`): default 1% with a hard 5%
  ceiling; notional capped at equity so a tight stop cannot create leverage.
  Invariants live in tests, not in grep bans.

The included SMA-cross strategy is a plumbing test. **It is not an edge and
none is claimed.** The CLI verdict says so out loud.

## Install and run

```bash
git clone <repo-url> keel && cd keel
pip install -e ".[dev]"
pytest
keel run path/to/bars.csv        # CSV: date,open,high,low,close,volume
```

## Layout

```text
src/keel/
  data.py       validated OHLCV bars, CSV loading
  universe.py   point-in-time membership
  strategy.py   strategy contract + example (no edge claimed)
  backtest.py   walk-forward engine
  risk.py       fixed-fractional sizing from stop
  costs.py      per-fill cost model
  stats.py      block bootstrap null, BH FDR, Sharpe
  cli.py        keel run
```

Eight modules. If a change would add a ninth, first ask whether it belongs in
one of these eight.

## Rules of the project

1. Research before infrastructure: see `RESEARCH_BETS.md`. No new machinery
   while a bet is open.
2. Every strategy variant evaluated — including failures — goes into the
   p-value list handed to `benjamini_hochberg`.
3. Status lives in `RESEARCH_BETS.md` and nowhere else. No dated "current
   truth" snapshots in prose, no hand-pinned test counts.
4. Plain vocabulary. A backtest is a backtest.
