from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from app.core.config import settings
from app.providers.mock import MockDiscovery
from app.research.engine import process_snapshot
from app.storage.db import init_db,recent_events
app=FastAPI(title=settings.app_name,version="0.3.0");provider=MockDiscovery()
@app.on_event("startup")
async def startup():await init_db()
@app.get("/health")
async def health():return {"ok":True,"version":"0.3.0","shadow_only":settings.shadow_only,"live_execution_enabled":False}
@app.get("/status")
async def status():
    e=await recent_events(500);return {"mode":"SHADOW","scanner":"READY","provider":provider.__class__.__name__,"live_execution_enabled":False,"cycle_seconds":settings.cycle_seconds,"snapshots_logged":sum(x["event_type"]=="SNAPSHOT" for x in e),"decisions_logged":sum(x["event_type"]=="DECISION" for x in e)}
@app.post("/run-once")
async def run_once():
    out=[]
    for s in await provider.discover():
        d=await process_snapshot(s);out.append({"token":s.model_dump(mode="json"),"decisions":[x.model_dump(mode="json") for x in d]})
    return {"count":len(out),"results":out}
@app.get("/events")
async def events(limit:int=50):return await recent_events(min(max(limit,1),500))
@app.get("/",response_class=HTMLResponse)
async def dashboard():return HTMLResponse(DASHBOARD)
DASHBOARD="""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="theme-color" content="#0b0d12"><title>Jev Desk</title><style>*{box-sizing:border-box}body{margin:0;background:#0b0d12;color:#f5f7fb;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.wrap{max-width:760px;margin:auto;padding:30px 18px}.top{display:flex;justify-content:space-between;align-items:center}.title{font-size:30px;font-weight:800}.pill{padding:8px 12px;border-radius:999px;background:#163d2b;color:#79f2ad;font-weight:700}.card{background:#151922;border:1px solid #252b38;border-radius:20px;padding:18px;margin:14px 0}.label{color:#8e98aa;font-size:13px;text-transform:uppercase}.big{font-size:28px;font-weight:800}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.metric{background:#11151d;border-radius:15px;padding:14px}.num{font-size:22px;font-weight:750}.safe{color:#79f2ad}.muted{color:#8e98aa}button{width:100%;border:0;border-radius:16px;padding:16px;font-size:17px;font-weight:750}</style></head><body><div class="wrap"><div class="top"><div class="title">Jev Desk</div><div class="pill">SHADOW ONLY</div></div><div class="card"><div class="label">Desk status</div><div class="big" id="scanner">Loading...</div><div class="muted" id="provider"></div></div><div class="grid"><div class="metric"><div class="label">Snapshots</div><div class="num" id="snapshots">0</div></div><div class="metric"><div class="label">Decisions</div><div class="num" id="decisions">0</div></div><div class="metric"><div class="label">Mode</div><div class="num safe">Shadow</div></div><div class="metric"><div class="label">Real trades</div><div class="num safe">OFF</div></div></div><div class="card"><div class="label">Smoke test</div><p class="muted">Runs one mock discovery cycle. It cannot place a real trade.</p><button id="run" onclick="runOnce()">Run shadow test</button><div id="result" class="muted"></div></div></div><script>async function refresh(){let s=await(await fetch("/status")).json();scanner.textContent=s.scanner;provider.textContent="Provider: "+s.provider;snapshots.textContent=s.snapshots_logged;decisions.textContent=s.decisions_logged}async function runOnce(){run.disabled=true;result.textContent="Running...";try{let d=await(await fetch("/run-once",{method:"POST"})).json();result.textContent="Completed "+d.count+" shadow snapshot(s). No real order was sent.";await refresh()}catch(e){result.textContent="Test failed: "+e}run.disabled=false}refresh();setInterval(refresh,10000)</script></body></html>"""
