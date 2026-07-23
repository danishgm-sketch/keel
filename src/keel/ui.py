"""Keel local dashboard — a zero-dependency monitor over the autonomous bot.

This is a **monitor, not a control panel**. The system runs itself: it scans the
whole market, the meta-brain picks the best play per name per moment, and it
trades your Alpaca paper account on its own. The page just reflects that in real
time. The only control is the KILL switch — you must always be able to stop a
running bot; you never need to *operate* it.

Stdlib http.server, self-contained offline HTML/JS. The backtest payload builder
is kept (and unit-tested) for internal/CLI use, but nothing in the page invokes
it — there is nothing here for you to run.
"""

from __future__ import annotations

import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from keel.costs import CostModel
from keel.portfolio import load_dir, run_portfolio
from keel.stats import bootstrap_pvalue, sharpe
from keel.strategies import OpeningRangeBreakout, Rsi2Reversion, SwingPullback

STRATEGIES = {"rsi2": Rsi2Reversion, "orb": OpeningRangeBreakout, "swing": SwingPullback}


def backtest_payload(data_dir: str | Path, strategy: str, options: dict) -> dict:
    """Run the book and return a metrics dict. Kept for CLI/tests; the monitor
    page does not call it."""
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}")
    data = load_dir(data_dir)
    if not data:
        return {"error": f"no CSVs in {data_dir}"}
    result = run_portfolio(
        data,
        STRATEGIES[strategy],
        starting_equity=float(options.get("equity", 100_000.0)),
        risk_fraction=float(options.get("risk", 0.01)),
        max_positions=int(options.get("max_positions", 10)),
        max_new_per_day=int(options.get("max_new_per_day", 20)),
        costs=CostModel(
            proportional=float(options.get("spread", 0.0005)),
            per_share=float(options.get("per_share", 0.0002)),
        ),
    )
    rets = result.returns
    pval = bootstrap_pvalue(rets) if len(rets) >= 20 else 1.0
    gross = sum(t.pnl + t.costs for t in result.trades)
    per_day: dict[str, int] = {}
    for t in result.trades:
        d = str(t.entry_ts.astype("datetime64[D]"))
        per_day[d] = per_day.get(d, 0) + 1
    return {
        "strategy": strategy,
        "symbols": len(data),
        "sessions": len(result.daily_dates),
        "trades": len(result.trades),
        "trades_per_day": round(result.trades_per_day, 2),
        "win_rate": round(result.win_rate, 4),
        "total_return": round(result.total_return, 4),
        "sharpe": round(sharpe(rets), 2),
        "pvalue": round(pval, 4),
        "beats_luck": bool(pval < 0.05),
        "costs_paid": round(result.total_costs, 2),
        "gross_pnl": round(gross, 2),
        "equity": {
            "dates": [str(d) for d in result.daily_dates],
            "values": [round(v, 2) for v in result.daily_equity.tolist()],
        },
        "per_day": {"dates": list(per_day), "counts": list(per_day.values())},
        "recent_trades": [],
    }


def make_handler(default_dir: Path, service=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, obj, code=200, ctype="application/json"):
            body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/index"):
                self._send(PAGE.encode(), ctype="text/html; charset=utf-8")
            elif self.path.startswith("/api/live/status"):
                self._send(service.status() if service else {"enabled": False})
            else:
                self._send({"error": "not found"}, code=404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            _ = self.rfile.read(length)
            if self.path.startswith("/api/live/kill"):
                self._send(service.kill() if service else {"enabled": False})
            elif self.path.startswith("/api/live/arm"):
                self._send(service.arm() if service else {"enabled": False})
            elif self.path.startswith("/api/live/disarm"):
                self._send(service.disarm() if service else {"enabled": False})
            else:
                self._send({"error": "not found"}, code=404)

    return Handler


def run_ui(
    data_dir: str | Path = "data",
    port: int = 8787,
    open_browser: bool = True,
    service=None,
) -> None:
    from keel.env import load_env

    load_env()
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(data_dir, service))
    url = f"http://127.0.0.1:{port}"
    print(f"Keel monitor on {url}  —  Ctrl+C to stop")
    if open_browser:
        import contextlib

        with contextlib.suppress(Exception):
            webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
        server.shutdown()


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Keel</title><style>
:root{--bg:#0d1117;--panel:#161b22;--edge:#272e38;--fg:#e6edf3;--dim:#8b949e;--grn:#3fb950;--red:#f85149;--acc:#58a6ff}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--fg)}
header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 22px;border-bottom:1px solid var(--edge);position:sticky;top:0;background:var(--bg);z-index:2}
header .brand{display:flex;align-items:baseline;gap:12px}header b{font-size:19px;letter-spacing:1px}header .sub{color:var(--dim);font-size:13px}
main{padding:22px;max-width:1200px;margin:0 auto}
.pill{display:inline-block;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600;margin-right:8px}
.pill.on{background:#0f1e14;color:var(--grn);border:1px solid #1f5a30}
.pill.off{background:#1c1410;color:#f0b072;border:1px solid #5a3a1a}
.pill.dim{background:#161b22;color:var(--dim);border:1px solid var(--edge)}
.kill{background:var(--red);color:#fff;border:0;padding:9px 16px;border-radius:6px;font-weight:700;cursor:pointer;letter-spacing:.3px}
.statusrow{margin:6px 0 20px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:22px}
.card{background:var(--panel);border:1px solid var(--edge);border-radius:8px;padding:14px}
.card .k{color:var(--dim);font-size:12px;text-transform:uppercase;letter-spacing:.4px}.card .v{font-size:24px;font-weight:700;margin-top:4px}
.pos{color:var(--grn)}.neg{color:var(--red)}
.panel{background:var(--panel);border:1px solid var(--edge);border-radius:8px;padding:16px;margin-bottom:20px}
.panel h3{margin:0 0 12px;font-size:12px;color:var(--dim);text-transform:uppercase;letter-spacing:.5px}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:right;padding:7px 8px;border-bottom:1px solid var(--edge)}
th:first-child,td:first-child{text-align:left}th{color:var(--dim);font-weight:500}
.muted{color:var(--dim)}.note{color:var(--dim);font-size:12px;margin-top:10px}
.chips{display:flex;flex-wrap:wrap;gap:6px}.chip{background:#0d1117;border:1px solid var(--edge);border-radius:5px;padding:3px 8px;font-size:12px;color:var(--dim)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}@media(max-width:760px){.grid2{grid-template-columns:1fr}}
</style></head><body>
<header>
  <div class="brand"><b>KEEL</b><span class="sub">autonomous paper trader — live monitor</span></div>
  <button class="kill" onclick="if(confirm('Stop the bot and flatten all positions?'))kill()">KILL &amp; FLATTEN</button>
</header>
<main id="main"><p class="muted">connecting…</p></main>
<script>
async function kill(){await fetch('/api/live/kill',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});poll();}
function pct(x){return (x*100).toFixed(2)+'%';}
async function poll(){let r;try{r=await (await fetch('/api/live/status')).json();}catch(e){return;}
  const m=document.getElementById('main');
  if(!r.enabled){m.innerHTML=`<div class="panel"><span class="pill dim">BOT OFFLINE</span>
    <div class="note">${r.broker_error||'The bot is not running. Launch Keel with your .env present.'}</div></div>`;return;}
  const last=r.last||{};const acct=r.account||{};const pos=r.positions||[];const jt=r.journal_today||[];
  const cand=r.candidates||[];const cfg=r.config||{};
  const armed=last.armed;const mo=last.market_open;
  const armPill=armed?'<span class="pill on">ARMED</span>':'<span class="pill off">DISARMED</span>';
  const mkt=mo===true?'<span class="pill on">MARKET OPEN</span>':mo===false?'<span class="pill dim">MARKET CLOSED</span>':'<span class="pill dim">—</span>';
  const posRows=pos.length?pos.map(p=>`<tr><td>${p.symbol}</td><td>${p.qty}</td><td>${(+p.avg_entry_price).toFixed(2)}</td><td class="${(+p.unrealized_pl)>=0?'pos':'neg'}">${(+p.unrealized_pl).toFixed(2)}</td></tr>`).join(''):'<tr><td colspan=4 class="muted">flat — no open positions</td></tr>';
  const jrows=jt.slice(-14).reverse().map(e=>`<tr><td>${(e.ts||'').slice(11,19)}</td><td>${e.kind}</td><td>${e.symbol||''}</td><td class="muted">${e.via||e.reason||e.note||''}</td></tr>`).join('')||'<tr><td colspan=4 class="muted">no activity yet today</td></tr>';
  const chips=cand.slice(0,60).map(s=>`<span class="chip">${s}</span>`).join('')||'<span class="muted">scanning…</span>';
  m.innerHTML=`
   <div class="statusrow">${armPill}${mkt}
     <span class="pill dim">${r.mode||'whole-market'}</span>
     <span class="pill dim">strategy: ${cfg.strategy||'auto'}</span></div>
   <div class="cards">
     <div class="card"><div class="k">Equity</div><div class="v">${acct.equity?(+acct.equity).toLocaleString():'—'}</div></div>
     <div class="card"><div class="k">Buying power</div><div class="v">${acct.buying_power?(+acct.buying_power).toLocaleString():'—'}</div></div>
     <div class="card"><div class="k">Open positions</div><div class="v">${pos.length}</div></div>
     <div class="card"><div class="k">Trades today</div><div class="v">${last.trades_today??0}</div></div>
     <div class="card"><div class="k">Market scanned</div><div class="v">${(r.universe_size||0).toLocaleString()}</div></div>
     <div class="card"><div class="k">Candidates now</div><div class="v">${cand.length}</div></div>
   </div>
   <div class="grid2">
     <div class="panel"><h3>Open positions</h3><table><thead><tr><th>Sym</th><th>Qty</th><th>Entry</th><th>uP&L</th></tr></thead><tbody>${posRows}</tbody></table></div>
     <div class="panel"><h3>Today's activity (the bot's decisions)</h3><table><thead><tr><th>Time</th><th>Event</th><th>Sym</th><th>Via / why</th></tr></thead><tbody>${jrows}</tbody></table></div>
   </div>
   <div class="panel"><h3>Live candidates — the whole market narrowed to what's tradeable now</h3><div class="chips">${chips}</div></div>
   ${last.note?`<div class="note">${last.note}</div>`:''}`;
}
poll();setInterval(poll,4000);
</script></body></html>"""
