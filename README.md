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

## The high-turnover book (`keel trade`)

A multi-symbol engine that fires **many intraday and swing trades a day across a
watchlist** — not HFT (decisions are per-bar, fills at the *next* bar's open,
nothing sub-bar). Three lanes ship:

- `rsi2` — intraday short-term mean reversion (fires often; the workhorse)
- `orb`  — intraday opening-range breakout (one clean shot per symbol per day)
- `swing` — multi-day trend-pullback, held overnight

```bash
keel trade path/to/csv_dir --strategy rsi2   # one CSV per symbol in the dir
```

The engine throttles turnover with `--max-positions` and `--max-new-per-day`,
sizes every trade at 1% risk from its stop, force-flattens intraday positions at
the session close, and **charges realistic costs on every fill**. It then prints
the honest bootstrap verdict on the daily equity curve.

**Why the honesty matters here more than anywhere:** at 10+ trades a day, the
half-spread + slippage + fees you pay on every fill are the dominant term. A
setup that looks great gross is routinely *dead* net — so the report shows costs
paid against gross P&L, and the default verdict stays "not distinguishable from
luck" until the evidence, net of costs and out-of-sample, overturns it. The
included strategies are honest *hypotheses*, not proven edges. Finding the edge
is the research work in `RESEARCH_BETS.md`; this is the machine that tests it
without lying to you.

## Install and run

```bash
git clone <repo-url> keel && cd keel
pip install -e ".[dev]"
pytest
keel run   path/to/bars.csv      # single-symbol demo (CSV: date,o,h,l,c,volume)
keel trade path/to/csv_dir       # high-turnover multi-symbol book
```

## Layout

```text
src/keel/
  data.py        validated OHLCV bars, CSV loading
  universe.py    point-in-time membership
  indicators.py  causal EMA / RSI / ATR / session helpers
  strategy.py    strategy contract + SMA-cross demo (no edge claimed)
  strategies.py  intraday (rsi2, orb) + swing lanes for the book
  backtest.py    single-symbol walk-forward engine
  portfolio.py   multi-symbol, multi-position high-turnover engine
  risk.py        fixed-fractional sizing from stop
  costs.py       per-fill cost model
  stats.py       block bootstrap null, BH FDR, Sharpe
  cli.py         keel run / keel trade
```

## Rules of the project

1. Research before infrastructure: see `RESEARCH_BETS.md`. No new machinery
   while a bet is open.
2. Every strategy variant evaluated — including failures — goes into the
   p-value list handed to `benjamini_hochberg`.
3. Status lives in `RESEARCH_BETS.md` and nowhere else. No dated "current
   truth" snapshots in prose, no hand-pinned test counts.
4. Plain vocabulary. A backtest is a backtest.
