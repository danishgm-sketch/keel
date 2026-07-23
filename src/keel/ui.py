"""Keel local dashboard — a zero-dependency web UI over the engine.

    keel ui --dir data/            # then open http://127.0.0.1:8787

Design choices (I picked these deliberately):
- **Local web app, not desktop GUI or hosted page.** You run it on your own
  machine next to your data and your .env; nothing leaves the box. Stdlib
  http.server means no Flask/Node/Electron to install — it just runs on Windows.
- **Self-contained page.** HTML/CSS/JS inline, the equity curve drawn as SVG in
  vanilla JS. No CDN, no build step, works offline.
- **The verdict is the headline.** The UI leads with the honest bootstrap
  verdict and the cost drag, because at high turnover those are the story.

The payload builder is factored out (`backtest_payload`) so it is unit-tested
without binding a socket.
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
    """Run the book and return everything the dashboard renders. Pure (no I/O
    beyond reading the CSVs)."""
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
    recent = [
        {
            "symbol": t.symbol,
            "lane": t.lane,
            "reason": t.reason,
            "entry_ts": str(t.entry_ts),
            "exit_ts": str(t.exit_ts),
            "entry": round(t.entry_price, 4),
            "exit": round(t.exit_price, 4),
            "shares": t.shares,
            "pnl": round(t.pnl, 2),
            "costs": round(t.costs, 2),
        }
        for t in result.trades[-300:][::-1]
    ]
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
        "recent_trades": recent,
    }


def _state(data_dir: Path) -> dict:
    csvs = sorted(p.stem for p in Path(data_dir).glob("*.csv"))
    return {"dir": str(data_dir), "symbols": csvs, "strategies": sorted(STRATEGIES)}


def make_handler(default_dir: Path):
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
            elif self.path.startswith("/api/state"):
                self._send(_state(default_dir))
            else:
                self._send({"error": "not found"}, code=404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length) or b"{}")
            if self.path.startswith("/api/backtest"):
                data_dir = Path(req.get("dir") or default_dir)
                try:
                    self._send(backtest_payload(data_dir, req.get("strategy", "rsi2"), req))
                except Exception as e:  # surface errors to the UI, don't crash
                    self._send({"error": str(e)}, code=400)
            elif self.path.startswith("/api/fetch"):
                self._send(self._fetch(req, default_dir))
            else:
                self._send({"error": "not found"}, code=404)

        def _fetch(self, req, data_dir):
            from keel.alpaca import fetch_bars, save_csv

            symbols = [s.strip().upper() for s in req.get("symbols", []) if s.strip()]
            if not symbols:
                return {"error": "no symbols given"}
            try:
                saved = []
                for sym in symbols:
                    bars = fetch_bars(
                        sym,
                        req["start"],
                        req["end"],
                        timeframe=req.get("timeframe", "1Min"),
                        feed=req.get("feed", "iex"),
                    )
                    save_csv(bars, data_dir)
                    saved.append(f"{sym} ({len(bars)} bars)")
                return {"ok": True, "saved": saved, "state": _state(data_dir)}
            except Exception as e:
                return {"error": str(e)}

    return Handler


def run_ui(data_dir: str | Path = "data", port: int = 8787, open_browser: bool = True) -> None:
    from keel.env import load_env

    load_env()
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(data_dir))
    url = f"http://127.0.0.1:{port}"
    print(f"Keel dashboard on {url}  (data dir: {data_dir})  —  Ctrl+C to stop")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
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
header{display:flex;align-items:baseline;gap:12px;padding:14px 20px;border-bottom:1px solid var(--edge)}
header b{font-size:18px;letter-spacing:.5px}header span{color:var(--dim)}
.wrap{display:grid;grid-template-columns:280px 1fr;gap:0;min-height:calc(100vh - 52px)}
aside{border-right:1px solid var(--edge);padding:18px;background:var(--panel)}
main{padding:20px;overflow:auto}
label{display:block;color:var(--dim);margin:12px 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:.4px}
select,input{width:100%;background:#0d1117;border:1px solid var(--edge);color:var(--fg);padding:7px 9px;border-radius:6px}
button{width:100%;margin-top:16px;background:var(--acc);color:#0d1117;border:0;padding:10px;border-radius:6px;font-weight:600;cursor:pointer}
button.sec{background:transparent;color:var(--acc);border:1px solid var(--acc);margin-top:8px}
.row{display:flex;gap:8px}.row>div{flex:1}
.verdict{padding:14px 18px;border-radius:8px;margin-bottom:18px;font-weight:600;border:1px solid}
.v-bad{background:#1c1410;border-color:#5a3a1a;color:#f0b072}.v-good{background:#0f1e14;border-color:#1f5a30;color:#6fdd8b}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:20px}
.card{background:var(--panel);border:1px solid var(--edge);border-radius:8px;padding:14px}
.card .k{color:var(--dim);font-size:12px;text-transform:uppercase;letter-spacing:.4px}.card .v{font-size:22px;font-weight:700;margin-top:4px}
.pos{color:var(--grn)}.neg{color:var(--red)}
.panel{background:var(--panel);border:1px solid var(--edge);border-radius:8px;padding:16px;margin-bottom:20px}
.panel h3{margin:0 0 12px;font-size:13px;color:var(--dim);text-transform:uppercase;letter-spacing:.5px}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:right;padding:6px 8px;border-bottom:1px solid var(--edge)}
th:first-child,td:first-child{text-align:left}th{color:var(--dim);font-weight:500}
.muted{color:var(--dim)}.note{color:var(--dim);font-size:12px;margin-top:10px}
</style></head><body>
<header><b>KEEL</b><span>honest high-turnover book — local dashboard</span></header>
<div class="wrap">
<aside>
  <label>Data folder</label><input id="dir" placeholder="(launch dir)">
  <label>Strategy</label><select id="strategy"></select>
  <div class="row"><div><label>Max positions</label><input id="max_positions" type="number" value="10"></div>
  <div><label>Max new / day</label><input id="max_new_per_day" type="number" value="20"></div></div>
  <div class="row"><div><label>Spread (per side)</label><input id="spread" type="number" step="0.0001" value="0.0005"></div>
  <div><label>Per share</label><input id="per_share" type="number" step="0.0001" value="0.0002"></div></div>
  <label>Risk / trade</label><input id="risk" type="number" step="0.001" value="0.01">
  <button onclick="runBacktest()">Run book</button>
  <hr style="border-color:var(--edge);margin:20px 0">
  <label>Fetch from Alpaca</label>
  <input id="symbols" placeholder="AAPL, MSFT, TSLA">
  <div class="row"><div><label>Start</label><input id="start" value="2024-01-01"></div>
  <div><label>End</label><input id="end" value="2024-03-01"></div></div>
  <label>Timeframe</label><select id="timeframe"><option>1Min</option><option>5Min</option><option>15Min</option><option>1Hour</option><option>1Day</option></select>
  <button class="sec" onclick="fetchData()">Fetch bars</button>
  <div class="note" id="fetchmsg"></div>
  <div class="note" id="symlist"></div>
</aside>
<main id="main"><p class="muted">Pick a strategy and click <b>Run book</b>. Or fetch real bars from Alpaca first (needs your .env).</p></main>
</div>
<script>
const $=id=>document.getElementById(id);
async function loadState(){const s=await (await fetch('/api/state')).json();
  const sel=$('strategy');sel.innerHTML=s.strategies.map(x=>`<option>${x}</option>`).join('');
  $('symlist').textContent=s.symbols.length?`${s.symbols.length} symbols: ${s.symbols.slice(0,12).join(', ')}${s.symbols.length>12?'…':''}`:'no data yet';}
function opts(){return{dir:$('dir').value||null,strategy:$('strategy').value,
  max_positions:+$('max_positions').value,max_new_per_day:+$('max_new_per_day').value,
  spread:+$('spread').value,per_share:+$('per_share').value,risk:+$('risk').value};}
async function runBacktest(){$('main').innerHTML='<p class="muted">running…</p>';
  const r=await (await fetch('/api/backtest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(opts())})).json();
  if(r.error){$('main').innerHTML=`<div class="verdict v-bad">${r.error}</div>`;return;}render(r);}
async function fetchData(){$('fetchmsg').textContent='fetching…';
  const body={symbols:$('symbols').value.split(','),start:$('start').value,end:$('end').value,timeframe:$('timeframe').value,dir:$('dir').value||null};
  const r=await (await fetch('/api/fetch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
  if(r.error){$('fetchmsg').innerHTML=`<span class="neg">${r.error}</span>`;return;}
  $('fetchmsg').innerHTML=`<span class="pos">saved: ${r.saved.join(', ')}</span>`;loadState();}
function pct(x){return (x*100).toFixed(2)+'%';}
function sign(x){return x>=0?'pos':'neg';}
function render(r){
  const good=r.beats_luck;
  const verdict=good
    ?`<div class="verdict v-good">Beats the block-bootstrap null on THIS sample (p=${r.pvalue}). One p-value is not an edge — confirm out-of-sample &amp; net of costs before risking a cent.</div>`
    :`<div class="verdict v-bad">NOT distinguishable from luck (p=${r.pvalue}). At ${r.trades_per_day} trades/day, costs are the enemy — don't tune to beat noise.</div>`;
  const cards=[['Net return',pct(r.total_return),sign(r.total_return)],['Sharpe',r.sharpe,sign(r.sharpe)],
    ['Trades',r.trades,''],['Per day',r.trades_per_day,''],['Win rate',pct(r.win_rate),''],
    ['Costs paid',r.costs_paid.toLocaleString(),'neg'],['Gross P&L',r.gross_pnl.toLocaleString(),sign(r.gross_pnl)],
    ['Symbols',r.symbols,'']].map(([k,v,c])=>`<div class="card"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`).join('');
  $('main').innerHTML=verdict+`<div class="cards">${cards}</div>`
    +`<div class="panel"><h3>Equity curve (net of costs)</h3>${equitySVG(r.equity.values)}</div>`
    +`<div class="panel"><h3>Recent trades (last ${r.recent_trades.length})</h3>${tradeTable(r.recent_trades)}</div>`;
}
function equitySVG(v){if(!v||v.length<2)return '<p class="muted">not enough sessions</p>';
  const W=900,H=240,p=30,lo=Math.min(...v),hi=Math.max(...v),rng=(hi-lo)||1;
  const x=i=>p+i*(W-2*p)/(v.length-1),y=val=>H-p-(val-lo)/rng*(H-2*p);
  const pts=v.map((val,i)=>`${x(i).toFixed(1)},${y(val).toFixed(1)}`).join(' ');
  const up=v[v.length-1]>=v[0],col=up?'#3fb950':'#f85149';
  const base=y(v[0]);
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" preserveAspectRatio="none">
    <line x1="${p}" y1="${base}" x2="${W-p}" y2="${base}" stroke="#8b949e" stroke-dasharray="4 4" opacity=".5"/>
    <polyline fill="none" stroke="${col}" stroke-width="2" points="${pts}"/>
    <text x="${p}" y="16" fill="#8b949e" font-size="11">${hi.toLocaleString()}</text>
    <text x="${p}" y="${H-6}" fill="#8b949e" font-size="11">${lo.toLocaleString()}</text></svg>`;}
function tradeTable(t){if(!t.length)return '<p class="muted">no trades</p>';
  const rows=t.slice(0,60).map(x=>`<tr><td>${x.symbol}</td><td class="muted">${x.lane}</td><td class="muted">${x.reason}</td>
    <td>${x.entry}</td><td>${x.exit}</td><td>${x.shares}</td><td class="${x.pnl>=0?'pos':'neg'}">${x.pnl}</td></tr>`).join('');
  return `<table><thead><tr><th>Symbol</th><th>Lane</th><th>Exit</th><th>Entry</th><th>Exit px</th><th>Shares</th><th>P&L</th></tr></thead><tbody>${rows}</tbody></table>`;}
loadState();
</script></body></html>"""
