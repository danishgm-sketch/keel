# The Keel Program

The full-scope ambition, sequenced so it pays off instead of blowing up.

The vector of this project has always been the same: *more autonomous, bigger,
self-improving, always-on, toward money.* That vector is right. The only change
this document makes is where it points **first** — at proof — because every layer
we build is worth exactly nothing until we know there is an edge underneath it.

## The one gate everything hangs on

```
keel walkforward --dir data
```

This is the single number that matters. It runs the *adaptive* system — pick a
champion on the past, trade it forward out-of-sample, roll, repeat — and judges
the concatenated out-of-sample curve against a block-bootstrap null. It writes
every verdict to `edge_ledger.jsonl` so the answer is tracked as data grows.

Nothing below this line ships to real money until this line is green and stays
green across many folds. That is not caution slowing the ambition down — it is
the thing that makes the ambition **bankable**. A grand always-on cloud system
with no proven edge is just a faster way to lose money.

## The arc (each stage gated by the stage before)

### Stage 1 — Find one edge (where we are)
Accumulate real Alpaca bars, run `evolve` and `walkforward` daily, watch the edge
ledger. Success = a walk-forward OOS verdict that beats luck across ≥10 folds, net
of costs. Most ideas die here. That is the system working.

### Stage 2 — Make it a portfolio of edges
One edge is fragile. Turn each *validated* strategy into a "book", and allocate
capital across books by their realized out-of-sample track record (risk parity /
fractional Kelly). Uncorrelated books are the only real free lunch. Every book
must pass Stage 1 on its own before it gets a dollar.

### Stage 3 — The always-on frontier: crypto + 24/7
The natural home for an always-on bot is a market that never closes and is less
efficient. Crypto (funding-rate harvest, basis) is the first venue where "runs by
itself around the clock" is literally true — and where a small operator's edge is
most plausible. Same engine, same gates, new data adapter.

### Stage 4 — Cloud, always-on
Lift the exact same service off the laptop onto a small always-on box. Nothing
about the code changes — `LiveService` already runs headless. What changes is
ops: monitoring, alerting, restart-safety, daily reconciliation, a heartbeat you
can check from your phone. Server-side (bracket) stops so a dropped connection
never leaves a naked position.

### Stage 5 — The live-money ladder
Only now, and only per-book that has earned it:
```
walk-forward green across many folds
  -> forward-paper tracks the backtest within tolerance
  -> paper-vs-live fills track within tolerance at token size
  -> a recorded human decision unlocks live for THAT book
  -> scale by realized out-of-sample performance, never by hope
```
Live stays disabled in code until each rung is met. The ladder is the product.

### Stage 6 — Compounding intelligence (the honest "evolves by itself")
The LLM keeps proposing variants; the walk-forward keeps judging them; the edge
ledger keeps the score. The playbook grows only by *validated* addition. Risk
sizing never mutates. This is a system that genuinely gets better over time —
because it can prove each improvement, not because it convinced itself.

## What we will never do
- Ship a feature a validated need didn't pull in.
- Let the LLM, or any search, change risk management or promote itself.
- Put real money behind an edge that only exists in-sample.
- Call a busy backtest an edge. The walk-forward curve is the only truth.

Ambition without limit. Discipline without exception. That is how this becomes a
system that makes money instead of one that only looks like it should.
