# Directions — where Keel is heading

Five lenses, one spine. The ideas below are ambitious on purpose, but every one
is sequenced *behind* the same gate: nothing risks money until the walk-forward
verdict goes green on real data. This file records the strategy and marks what
has shipped.

## The lenses
- **Renaissance** — many weak, uncorrelated signals combined and traded as a
  large book of tiny bets; ruthless costs; constant decay monitoring.
- **Apple / Jobs** — the product is the truth, made simple and felt. The defining
  feature is that it *refuses to trade noise*. Lead with the refusal.
- **Microsoft** — durability and platform: make the honesty-gate reusable, make
  the machine boringly reliable.
- **Morgan Stanley** — portfolio-level risk governance, stress tests, capital
  allocation, the reporting language real capital speaks.

## The stack (status)

| # | Initiative | Lens | Status |
|---|---|---|---|
| 1 | **Signals, not strategies** — continuous signal scores + a validated ensemble combiner | RenTech | **shipped** (`signals.py`, `ensemble.py`; the ensemble is gated like any strategy) |
| 2 | **Cross-sectional book** — rank by conviction, equal-risk many small bets | RenTech / MS | **shipped** (`allocator.py`) |
| 3 | **Signal decay monitor** — auto-retire fading edges | RenTech | **shipped** (`decay.py`) |
| 4 | **Portfolio risk budget + stress tests** | Morgan Stanley | **shipped** (`riskbudget.py`, `stress.py`) |
| 5 | **The Keel Briefing** — three honest questions | Apple | **shipped** (`briefing.py`, `keel briefing`) |
| 6 | **Reliability plumbing** — server-side stops first | Microsoft | **started** (`broker.submit_bracket`; reconnect/telemetry next) |
| A | **Self-writing strategy** (safe: bounded ensemble specs, no code exec) | AI frontier | **shipped as first version** (`synthesize.py`) |
| B | **"Certified Honest"** — the gate as a service | Apple / MS | **shipped** (`certify.py`, `keel certify`) |

## What is deliberately NOT done yet
- The live trader still runs the meta-policy; wiring the ensemble + allocator as
  the *live* book (not just the gated candidate) is the next integration.
- Reliability: reconnect/crash-recovery, idempotent orders, and structured
  telemetry remain (server-side stops are in).
- The self-writing limb proposes *ensemble specs*, not arbitrary code — executing
  model-written code stays out of scope until sandboxing is real.

## The rule that orders all of it
Build outward only as evidence pulls it in. None of this matters until
`keel walkforward` / `keel certify ensemble` goes green on real Alpaca bars. The
genius was never the ideas — it was refusing to deploy one until the evidence was
overwhelming.
