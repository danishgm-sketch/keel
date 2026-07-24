# Keel

An honest systematic-trading platform — research to live execution — where every
dollar of risk is earned by evidence. Successor to Bastion, built from its
audit: the discipline stays, the cathedral goes.

Today this repo is the honest research core (Phase 0). The full vision — where it
goes and the realistic money-making case — is in **[VISION.md](VISION.md)**; the
evidence-gated path is in **[ROADMAP.md](ROADMAP.md)**.

**See the whole machine at a glance:** open **[`docs/system-map.html`](docs/system-map.html)**
in any browser — a self-contained, offline wireframe kept in step with the code.
The written companion is **[ARCHITECTURE.md](ARCHITECTURE.md)**.

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

## Autonomous paper trading — you watch, you don't operate

Open the app and the bot runs itself. There is nothing to click, nothing to
configure, nothing to launch — the UI is a **monitor, not a control panel**. Its
only button is **KILL & FLATTEN**, because you must always be able to stop a
running bot.

Each cycle it:

- **scans the whole tradable US market** from Alpaca and ranks it by liquidity,
  carrying the top candidates forward (the fixed watchlist is gone);
- lets the **meta-brain pick the best strategy per symbol, per moment** — it
  scores each proven play on that name's recent behaviour and routes the decision
  to whichever fits the current regime;
- sizes each entry at the guarded risk fraction from its stop, submits **paper**
  orders, enforces stops, and flattens intraday names near the close.

The monitor shows it live: armed/market state, equity, open positions, the bot's
decisions (with which strategy fired each one), how many names were scanned, and
the live candidate shortlist.

Deliberate safety lines, non-negotiable:

- **Paper only.** `keel.broker` targets the Alpaca paper endpoint and has no code
  path to live money. Going live is a future decision gated on real evidence, not
  a flag you can flip by accident.
- **Risk sizing is a constant**, never auto-tuned.
- **Kill switch** cancels every order and flattens every position, and can never
  itself raise an error.

Headless (no window): `keel trade-live --dir data`.

### It evolves — the disciplined way

`keel evolve` grows the playbook without fooling itself: it searches strategy
variants, evaluates each on a real train/test split, and promotes **only** those
that beat the bootstrap null in-sample after Benjamini–Hochberg correction *and*
again out-of-sample. Survivors are written to `roster.json`; the champion becomes
what the live bot runs. If nothing survives, there's no champion — and that's the
honest, correct outcome. It never rewrites risk management or tunes to noise.

### The qualitative limb (parallel to the quant engine)

Trades are driven by the quantitative engine — but a second, **parallel limb**
runs alongside it on the qualitative side: news, earnings, rumors, catalysts. It
reads recent headlines (`catalysts.py`, Alpaca news) for the current candidates
and produces a **veto list** the trader honours (`overlay.py`).

The boundary is deliberate and absolute: **the qualitative limb can only *veto*,
never *create*.** Entry signals come solely from the validated quantitative
playbook — "news alpha" can't be proven with the same rigor, so it is never
allowed to open a trade. What it *can* do is keep the bot out of the landmines a
chart can't see: an imminent earnings print, a halt, an M&A rumor, a regulatory
headline. It removes risk; it never manufactures a position. The monitor shows
which names it's standing aside from and why. Toggle with `qualitative` in config.

### The AI brain (a local open-source LLM, woven in)

Keel and an open-source LLM are one program. A local reasoning model — **Qwen3**
via Ollama is the 2026 pick — is fused into the loop two ways:

- **Proposer** (`advisor`): suggests candidate strategy variants inside a locked
  schema; every proposal still faces the bootstrap + FDR gate.
- **Brain** (`brain`): every cycle it reads the *whole* live state — account,
  positions, the decision journal, the edge ledger (is there a proven edge yet?),
  the regime, the candidate shortlist, the validated roster — and recommends a
  posture. The monitor shows its read live.

Its authority is deliberately bounded so intelligence never becomes recklessness:
it can set posture to **defensive** (which only ever *reduces* trades and
positions — never loosens risk), and it can favor/avoid only strategies already
in the validated playbook. It cannot invent an edge, size a position, or place an
order. A mind that can only make the system more careful and only choose among
what it has already proven.

```bash
keel llm recommend      # picks a Qwen3 model for your RAM + the pull command
ollama pull qwen3       # run it locally: private, free
keel llm status         # which provider is active (local-first)
keel brain              # one AI reasoning pass over the current system state
keel evolve --use-llm   # LLM proposes variants; the gate still decides
```

### The training protocol — the brain's only subject is Keel

The brain's entire context is a **constitution** (`knowledge.py`): who it is
(Keel-Brain), what Keel is, the whole playbook, and the honesty spine it can
never break. It is injected on every call, so the model reasons about nothing but
improving Keel. On top of that sits a real, outcome-driven training loop
(`training.py`), run with **`keel train`**:

1. **Remember** — every decision (state it saw + what it recommended) is logged.
2. **Grade** — each past call is scored by what actually happened next (did equity
   rise when it said *normal*, or fall when it said *defensive*?). Measured
   outcomes are the training signal — never vibes.
3. **Distill** — the graded record becomes `brain_lessons.md`, folded back into
   the constitution, so it reasons with what it has learned. Self-improvement,
   no GPU.
4. **Export** — positively-graded pairs become a chat fine-tune dataset, and an
   Ollama `Modelfile` bakes the Keel-only constitution into a custom model:

```bash
keel train                       # grade, learn lessons, export dataset + Modelfile
ollama create keel-brain -f data/Modelfile.keel-brain
set KEEL_OLLAMA_MODEL=keel-brain # now the bot runs your trained Keel-only model
```

The training can only sharpen the brain's *judgement*. It cannot touch risk
sizing or invent a strategy — the honesty spine holds through training too.

Local Ollama is preferred (private, free); Claude (`ANTHROPIC_API_KEY`) and
Gemini (`GEMINI_API_KEY`/`GOOGLE_API_KEY`) are automatic fallbacks. The bot trades
safely with no model connected — you just lose the AI read.

## Just open it (desktop app)

No terminal needed after the first launch:

- **Windows** — double-click **`Keel.bat`**. The first run installs Keel (a
  minute), then a native Keel window opens. Want an icon? Double-click
  **`Create Desktop Shortcut.vbs`** once and you'll get a **Keel** icon on your
  Desktop — click it any time to open the app (no console window).
- **macOS** — double-click **`Keel.command`**.

The app opens in its own window (via pywebview, installed by `.[desktop]`). If
that package isn't present it falls back to your default browser, so it always
works. Under the hood it's the same dashboard as `keel ui`.

## Real data (Alpaca) & the dashboard

Bring your own Alpaca keys — copy `.env.example` to `.env` and fill it in. **`.env`
is gitignored and must never be committed;** the example is the only key-related
file that belongs in the repo.

```bash
cp .env.example .env             # then paste your ALPACA_API_KEY / ALPACA_SECRET_KEY
keel fetch AAPL MSFT TSLA --start 2024-01-01 --end 2024-03-01 --timeframe 1Min
keel ui --dir data               # local dashboard at http://127.0.0.1:8787
```

The dashboard is a zero-dependency local web app (stdlib `http.server`, inline
HTML/JS, offline, nothing leaves your machine). Pick a strategy, tune costs and
turnover throttles, and it runs the book and leads with the **honest verdict** and
the cost drag — the two things that decide a high-turnover system's fate. You can
also fetch fresh Alpaca bars straight from the sidebar.

## Install and run

```bash
git clone <repo-url> keel && cd keel
pip install -e ".[dev]"
pytest
keel run   path/to/bars.csv      # single-symbol demo (CSV: date,o,h,l,c,volume)
keel trade path/to/csv_dir       # high-turnover multi-symbol book (terminal)
keel fetch AAPL --start 2024-01-01 --end 2024-03-01   # real bars from Alpaca
keel ui                          # the local dashboard
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
  alpaca.py      real bars from Alpaca (data only, no orders)
  env.py         tiny .env loader (secrets stay on your machine)
  ui.py          local dashboard (stdlib http.server, offline)
  cli.py         keel run / trade / fetch / ui
```

## Rules of the project

1. Research before infrastructure: see `RESEARCH_BETS.md`. No new machinery
   while a bet is open.
2. Every strategy variant evaluated — including failures — goes into the
   p-value list handed to `benjamini_hochberg`.
3. Status lives in `RESEARCH_BETS.md` and nowhere else. No dated "current
   truth" snapshots in prose, no hand-pinned test counts.
4. Plain vocabulary. A backtest is a backtest.
