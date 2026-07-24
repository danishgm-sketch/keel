# Keel — Complete Project Documentation

*An honest, autonomous, AI-assisted trading machine. Version 0.3.0 · paper-only · 135 tests · [github.com/danishgm-sketch/keel](https://github.com/danishgm-sketch/keel)*

---

## 1. What Keel is (in one breath)

Keel is a self-running trading system that scans the entire US equity market, picks a **statistically proven** strategy for each symbol at each moment, sizes every trade at a fixed 1% risk, and executes on an Alpaca **paper** account — on its own, while you watch. It has a local AI brain that reasons over the whole system, a qualitative news-veto limb, an evolution loop that grows its playbook only with validated additions, and a training protocol whose only subject is Keel itself.

Its defining trait is not cleverness — it is **honesty**. The entire system is engineered around one rule: *the only thing allowed to risk money is a strategy proven out-of-sample.* Everything "smart" (the AI, the meta-brain, the news limb, the self-writing loop) can only choose among already-proven things, or make the system **more careful**. It will tell you, most of the time, that it has found no edge yet — and that is a feature, not a failure.

---

## 2. Origin & philosophy

Keel is the successor to **Bastion**, a 25,000-line predecessor that was audited and discarded. Bastion's failure was instructive: it had elaborate process controls, "sacred constants," self-evolution, and grand ambition — but **zero proven edge**, and was on track to confidently lose money. The lesson that shaped Keel:

> Trading systems rarely fail from lack of cleverness. They fail because they **fool themselves into betting on noise.**

So Keel inverts Bastion. Where Bastion built a cathedral around an empty vault, Keel is small, numpy-only, and disciplined. The ambition scales without limit; the honesty never bends. Every capability is pulled into existence by validated need — never pushed ahead of evidence.

**The governing rule, applied to every change:** *Does it let the machine risk money on something unproven?* If yes, it's wrong — however clever. If no, improve away.

---

## 3. The complete data-to-order pipeline

```text
Alpaca data (bars, snapshots, news)
   -> Scanner ranks the whole market by liquidity -> top candidates + recent bars
   -> Meta-brain / signal ensemble picks the best PROVEN policy per symbol, per moment
   -> Entry signal?  -- no --> back to scan
        | yes
   -> Qualitative limb: news/earnings veto?  -- vetoed --> stand aside
        | clear
   -> Risk sizing: 1% of equity from the stop (a constant)
   -> Portfolio risk budget: exposure & drawdown limits?  -- breach --> skip
        | ok
   -> Broker: Alpaca PAPER order + server-side stop (live money disabled in code)
   -> Journal: every decision, append-only
   -> Walk-forward gate: is there edge, out-of-sample?
   -> Edge ledger: the truth over time
        |- promote proven only --> back to the meta-brain
        |- AI brain reads all state -- tighten risk only --> risk sizing
```

The two feedback arrows are **safety-bounded**: evolution can only *add proven* strategies; the AI can only *tighten* risk. Nothing on a feedback path can loosen a limit or invent an edge.

---

## 4. The two limbs (quantitative + qualitative)

Trades are driven by numbers **and** read against the news — but the two limbs have deliberately unequal authority:

- **Quantitative limb — the only source of entries.** A proven strategy or ensemble fires a signal; it is sized 1% from its stop. This is the *only* thing that can open a trade, because it's the only thing the gate can validate.
- **Qualitative limb — parallel, veto-only.** Reads real headlines (earnings, halts, M&A rumors, regulatory news) and can *only remove* a name from consideration. "News alpha" can't be validated the same way, so it is never allowed to open a position — its job is to dodge the landmines a chart can't see.

This mirrors how disciplined systematic+discretionary desks actually run: the quant finds candidates, the overlay vetoes the ones about to blow up.

---

## 5. The honesty gate (the spine)

No idea reaches live selection on a good-looking backtest. It must pass, in order:

1. **In-sample bootstrap** — a stationary block-bootstrap null (preserves volatility clustering; not an IID-shuffle strawman).
2. **Benjamini–Hochberg FDR** — across *every* variant tried, so a grid search can't manufacture a phantom winner.
3. **Out-of-sample confirmation** — it must beat luck on held-out data too.
4. **Walk-forward across many folds** — the *adaptive process* (pick-champion-then-trade-forward) is judged, not a single variant.
5. **Edge ledger** — every verdict recorded over time, so "it's getting better" becomes a number you can watch.

If nothing survives → no champion → the system stays defensive. That is the correct default, and `keel doctor` will tell you so in one line.

---

## 6. Complete module reference (`src/keel/`)

**Data & indicators**
- `data.py` — Immutable, validated OHLCV `Bars`. Rejects non-ascending timestamps, non-positive prices, high<low at construction. `upto(i)` returns history through bar *i* — the **only** view a strategy ever sees, making look-ahead structurally impossible. `tail(k)` for fast recent-window scoring.
- `universe.py` — Point-in-time membership (`Membership(symbol, start, end)`). No code path backfills today's list into the past, so survivorship bias is impossible, not "stamped."
- `indicators.py` — Causal EMA, RSI (Wilder), ATR (Wilder), session-date helpers. Every value at bar *i* uses only bars <= *i*.

**The playbook**
- `strategy.py` — The `Strategy` contract (`warmup`, `lane`, `session_flat`, `on_bar -> Enter/Hold/Exit/None`), `Position`, and the SMA-cross demo (explicitly *not* an edge).
- `strategies.py` — Three real strategies: `rsi2` (intraday mean reversion), `orb` (opening-range breakout), `swing` (multi-day trend pullback).
- `signals.py` — **The RenTech pivot.** Five weak, causal signals scored 0–1: `rsi2`, `momentum`, `breakout`, `pullback`, `lowvol`. No single one is meant to be an edge.
- `ensemble.py` — Blends signals with weights into one conviction. `EnsembleStrategy` adapts conviction into enter/hold/exit, so an ensemble runs through the **same** gate as any strategy — the combiner is what gets validated.
- `meta.py` — The **meta-brain**: per symbol, scores each strategy/ensemble on its recent behaviour and routes the decision to the best fit. Re-selects as the regime shifts; never mid-trade.

**Engines & stats**
- `backtest.py` — Single-symbol walk-forward engine: next-open fills, gap-aware stops, costs on every fill, no look-ahead by construction and by test.
- `portfolio.py` — Multi-symbol engine (the live logic in backtest form): many trades/day, turnover throttles (`max_positions`, `max_new_per_day`), no leverage, intraday session-flatten.
- `risk.py` — Fixed-fractional sizing from the stop (default 1%, hard 5% ceiling, notional capped at equity). A **constant**; nothing may change it.
- `costs.py` — Realistic per-fill cost model (spread + slippage + per-share fees). High turnover makes costs the enemy; this keeps backtests honest.
- `stats.py` — The judge: `bootstrap_pvalue` (stationary block bootstrap, add-one estimator so p is never 0), `benjamini_hochberg`, `sharpe`.

**Evolution & validation**
- `roster.py` — **Evolution.** Searches a variant space (incl. the ensemble), validates each with a train/test split + FDR + OOS, writes `roster.json` with the champion and survivors. `active_meta_factory` seeds the live meta-brain with validated survivors.
- `walkforward.py` — The gate. Anchored, expanding-history, non-overlapping walk-forward; judges the concatenated OOS curve; writes `edge_ledger.jsonl`.
- `certify.py` — **The gate as a service.** `keel certify <target>` runs any built-in strategy or the ensemble through the full validation and returns an honest "certified / not certified."

**Portfolio ops & risk governance (the Morgan Stanley lens)**
- `allocator.py` — Cross-sectional book: rank candidates by conviction, give each an equal (or conviction-tilted) slice of the risk budget — many small bets.
- `decay.py` — Signal decay monitor: auto-retire an edge whose recent OOS turns negative and falls off its earlier record.
- `riskbudget.py` — Hard pre-trade limits: gross-exposure cap, position cap, daily drawdown budget that forces a defensive posture.
- `stress.py` — Scenario stress test, **honest about gap risk**: a shock that gaps through the stop is charged in full, not comfortingly capped at the stop.

**The market interface**
- `scanner.py` — Ranks the whole tradable universe by dollar-volume liquidity into a top-N shortlist (pure).
- `catalysts.py` — Real per-symbol headlines from Alpaca's news API (data only).
- `overlay.py` — The qualitative limb: reads candidate news, produces a veto avoid-list (bounded to candidates, veto-only, fails safe to no-veto).

**The AI brain & its training (the unique layer)**
- `llm.py` — Provider abstraction, **local-first**: Ollama (Qwen3 recommended, RAM-sized), then Claude (`ANTHROPIC_API_KEY`), then Gemini. Stdlib HTTP, no SDK dependency.
- `brain.py` — Reads the whole live state and recommends a **risk posture**. Hard-bounded: `defensive` only ever *reduces* trades/positions; favor/avoid restricted to validated strategies; invalid output fails safe to defensive.
- `knowledge.py` — The brain's **constitution**: its identity, what Keel is, the playbook, and the honesty spine — injected on every call so its entire context is Keel and only Keel.
- `training.py` — The training protocol: **remember** every decision -> **grade** by measured outcome (did equity move the right way?) -> **distill** lessons back into the constitution -> **export** a fine-tune dataset + an Ollama Modelfile (`keel-brain`). Learns to be *right*, not confident.
- `synthesize.py` — Safe self-writing: the LLM proposes bounded **ensemble specs** (weights + thresholds), never code; parsed, clamped, fed to the gate.
- `advisor.py` — The LLM proposes strategy *parameter variants* within a locked schema; still gated.

**Execution & orchestration**
- `broker.py` — Alpaca **paper** client. No code path to the live endpoint (constructing a non-paper URL raises). `submit_bracket` places **server-side** protective stops so a dropped connection can't leave a naked position. `list_assets` + `tradable_symbols` for the universe.
- `trader.py` — The live loop body: scan -> decide -> size -> order -> manage stops -> session-flatten, with `arm`/`disarm`/`kill`, throttles, and a qualitative-limb blocklist.
- `service.py` — The always-on orchestrator: schedules the market scan, the brain cycle, the overlay, and each `tick`. Applies the AI's posture (tighten-only) from base limits. Degrades gracefully with no keys/network.
- `config.py` — Runtime config (`keel_config.json`): universe mode, timeframe, throttles, risk fraction (clamped), scan cadence, qualitative toggle, autostart. Nothing here can push risk wild.
- `journal.py` — Append-only JSONL of every live decision — the irreplaceable record and the raw material for training.

**Surfaces**
- `ui.py` — The **watch-only monitor** (zero-dependency stdlib web app): armed/market state, equity, positions, the bot's decisions, the AI read, the qualitative veto list, scanned-market count, live candidates. The **only** control is KILL & FLATTEN.
- `app.py` — Desktop app: opens a native pywebview window (falls back to browser), auto-starts the bot.
- `doctor.py` — `keel doctor`: one-command honest state (data, survivors, champion, OOS edge verdict, brain memory, and with `--network` broker + LLM).
- `briefing.py` — `keel briefing`: three honest questions — is there edge, what did it do, what's it worried about.
- `cli.py` / `__main__.py` — Command dispatch (`python -m keel ...`).

---

## 7. Command-line reference

| Command | What it does |
|---|---|
| `keel doctor [--network]` | The machine's honest state in one view. |
| `keel briefing` | The three-question morning briefing. |
| `keel fetch SYMS --start --end --timeframe` | Download real bars from Alpaca to CSVs. |
| `keel trade <dir> --strategy` | Run the high-turnover book over CSVs (research). |
| `keel evolve [--use-llm]` | Search + validate variants; promote survivors. |
| `keel walkforward [--train --test]` | The out-of-sample gate; writes the edge ledger. |
| `keel certify <rsi2\|orb\|swing\|ensemble>` | Run a target through the honesty gate. |
| `keel stress` | Stress-test the current book (honest gap risk). |
| `keel brain` | One AI reasoning pass over the system state. |
| `keel train` | Grade past AI calls, learn lessons, export a Keel-only model. |
| `keel llm status\|recommend\|test` | LLM provider status / model recommendation. |
| `keel trade-live` | Run the automated paper bot headless. |
| `keel ui` / `keel app` | The monitor / the desktop app. |

**Desktop:** double-click `Keel.bat` (Windows) or `Keel.command` (macOS); `Create Desktop Shortcut.vbs` drops a launcher icon.

---

## 8. Safety model (non-negotiable, enforced in code)

1. **Paper only.** `broker.py` targets the Alpaca paper endpoint; there is no live endpoint and no flag to reach one. Going live is a future, evidence-gated human decision.
2. **Risk is a constant.** 1%-from-stop sizing in `risk.py` cannot be changed by the AI, the meta-brain, evolution, or config.
3. **The AI can only tighten.** Defensive posture reduces activity; there is no path that raises risk.
4. **The qualitative limb can only veto.** It can remove a name from entry, never create one.
5. **Self-writing proposes specs, not code.** No model-written code executes.
6. **Kill switch.** Cancels all orders and flattens all positions, and can never itself raise an error.
7. **Server-side stops.** A protective stop rests at the broker, surviving a dropped connection.
8. **Secrets stay local.** Keys load from a gitignored `.env`, are sent only to Alpaca over HTTPS, never logged or committed.
9. **Keel Intelligence is closed-domain and shadow-only.** `keel.intelligence` reasons about one world — Keel — from a validated `KeelState`; missing safety facts are recorded as degraded, never assumed healthy. Its outputs are bounded, reduction-only proposals under an expiring authority grant, validated fail-closed. In shadow mode (the default) the applied action is always the deterministic baseline; deployed inference cannot raise a posture, loosen a limit, place an order, or modify its own weights. A general LLM is admitted only as a recorded shadow challenger. See `KEEL_V1_MILESTONE_1.md` (shipped) and `KEEL_V1_BUILD_PACKAGE.md` (full v1 programme).

---

## 9. Data & runtime artifacts (all gitignored)

`data/*.csv` (bars) · `keel_config.json` · `keel.db` (SQLite durable truth: states, decisions, episodes, incidents, order intents) · `journal.jsonl` (tamper-evident, hash-chained decisions) · `roster.json` (champion/survivors) · `edge_ledger.jsonl` (verdicts over time) · `brain_memory.jsonl` (AI decisions) · `brain_lessons.md` (graded lessons) · `brain_finetune.jsonl` + `Modelfile.keel-brain` (from `keel train`). Recomputable caches can be wiped; the journal and edge ledger are the irreplaceable record.

---

## 10. Engineering standards

- **Dependencies:** numpy only (core). Optional: `[dev]` (pytest, ruff), `[desktop]` (pywebview, psutil). Everything else — HTTP, UI, LLM providers — is stdlib.
- **Tests:** 135, covering data invariants, no-look-ahead (a probe proves the engine never sees the future), risk invariants, the gate's statistics, the two limbs, the brain's bounds, the training loop, and every ops module.
- **CI:** GitHub Actions, `{ubuntu, windows} x {py3.11, 3.12}`, ruff lint + format + pytest. Green.
- **Docs kept in lockstep with code:** `README.md`, `ARCHITECTURE.md`, `docs/system-map.html` (openable offline wireframe), `docs/system-map.mmd` (diagram source, also renders a FigJam), `docs/DIRECTIONS.md` (strategy + status), `VISION.md`, `ROADMAP.md`, `THE_KEEL_PROGRAM.md`.

---

## 11. Roadmap & honest status

**Shipped (v0.3.0):** the honest research core; the high-turnover book; real Alpaca data + universe scanning; per-moment meta-selection; the walk-forward gate + edge ledger; the qualitative veto limb; the Keel-only AI brain + training protocol; signal ensembles (validated combiner); cross-sectional allocator; decay monitor; portfolio risk budget + stress tests; the Keel Briefing; gate-as-a-service; safe self-writing; server-side stops; the monitor UI + desktop app + doctor.

**Deliberately next (honest gaps):**
1. Wire the ensemble + allocator as the **live book** (currently the live trader runs the meta-policy; the ensemble is a gated candidate).
2. Reliability beyond server-side stops: reconnect/crash recovery, idempotent orders, telemetry.
3. Cloud always-on deployment.
4. The live-money ladder — only per-book that earns it, behind every gate.

**The one thing that unlocks all of it:** none of this earns money until `keel certify ensemble` (or `keel walkforward`) goes green on **real Alpaca bars, across many folds**. The genius was never the ideas — it was refusing to deploy one until the evidence was overwhelming.

---

## 12. Quick start (on your machine)

```bash
cd C:\Trading\keel   # or wherever you cloned it
git pull
pip install -e ".[desktop]"
copy .env.example .env          # paste your Alpaca paper keys
keel fetch AAPL MSFT NVDA AMD TSLA --start 2023-01-01 --end 2024-12-31 --timeframe 5Min
keel evolve                     # build the roster from real bars
keel certify ensemble           # the honest verdict — the number that matters
keel doctor                     # one-line state
```

Then double-click `Keel.bat` to open the app; with `.env` present it connects to your Alpaca paper account and, during market hours, trades on its own while you watch. Expect the first verdict to say **no proven edge yet** — that's the system refusing to bet on noise, which is exactly why it's worth trusting when it eventually says otherwise.

---

*Keel · honest autonomous trading machine · paper-only · every dollar of risk earned by evidence.*
