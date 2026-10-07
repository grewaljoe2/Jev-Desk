from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from app.core.config import settings
from app.providers.geckoterminal import GeckoTerminalDiscovery
from app.research.engine import process_snapshot
from app.research.scheduler import ShadowScheduler
from app.research.outcomes import OutcomeWorker
from app.storage.db import init_db,recent_events,research_counts,due_outcome_jobs,outcome_quality,scoreable_snapshot_quality
from app.research.replay_dataset import load_clean_replay_samples
from app.research.replay_pipeline import run_replay_research
from app.research.replay_diagnostics import replay_diagnostics
from app.research.qualification import qualification_diagnostics

app=FastAPI(title=settings.app_name,version=settings.version)
provider=GeckoTerminalDiscovery()
scheduler=ShadowScheduler(provider,settings.cycle_seconds)
outcome_worker=OutcomeWorker(provider)

@app.on_event("startup")
async def startup():
    await init_db()
    scheduler.start()
    outcome_worker.start()

@app.get("/health")
async def health():
    return {"ok":True,"version":settings.version,"shadow_only":True,"live_execution_enabled":False,"provider":provider.__class__.__name__,"provider_diagnostics":provider.last_diagnostics}

@app.get("/status")
async def status():
    r=await research_counts()
    return {"mode":"SHADOW","scanner":"RUNNING","provider":provider.__class__.__name__,"live_execution_enabled":False,"cycle_seconds":settings.cycle_seconds,"snapshots_logged":r["snapshots"],"decisions_logged":r["decisions"],"outcomes_logged":r["outcomes"],"outcomes_pending":r["pending"],"storage":r["storage"]}

@app.post("/run-once")
async def run_once():
    out=[]
    for s in await provider.discover():
        d=await process_snapshot(s);out.append({"token":s.model_dump(mode="json"),"decisions":[x.model_dump(mode="json") for x in d]})
    return {"count":len(out),"provider_diagnostics":provider.last_diagnostics,"results":out}

@app.get("/events")
async def events(limit:int=50):return await recent_events(min(max(limit,1),500))

@app.get("/research-health")
async def research_health():
    r=await research_counts();q=await outcome_quality();sq=await scoreable_snapshot_quality()
    return {"ok":True,"storage":r["storage"],"snapshots":r["snapshots"],"decisions":r["decisions"],"outcomes":r["outcomes"],"pending":r["pending"],"due_now":r.get("due_now",0),"outcome_quality":q,"scoreable_snapshots":sq,"live_execution_enabled":False}

@app.get("/replay-report")
async def replay_report():
    samples=await load_clean_replay_samples(500)
    report=run_replay_research(samples) if samples else {"calibration_count":0,"holdout_count":0,"calibration_leaderboard":[],"frozen_policy":None,"holdout":None}
    diag=replay_diagnostics(samples,report.get("frozen_policy")) if samples else None
    q=qualification_diagnostics(samples)\n    ref=q.get("reference",{})\n    scoreable=int(ref.get("eligible",0))+int(ref.get("rejected",0))\n    return {"ok":True,"evidence":"forward_clean","sample_count":len(samples),"scoreable_sample_count":scoreable,"qualified_sample_count":int(ref.get("eligible",0)),"unscorable_sample_count":int(ref.get("unscorable",0)),"sufficient_for_strategy_conclusion":scoreable>=100,**report,"diagnostics":diag,"qualification":q,"live_execution_enabled":False}

@app.get("/",response_class=HTMLResponse)
async def dashboard():return HTMLResponse(DASHBOARD)

DASHBOARD="""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="theme-color" content="#090b10"><title>Jev Desk</title><style>*{box-sizing:border-box}body{margin:0;background:#090b10;color:#f5f7fb;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.wrap{max-width:760px;margin:auto;padding:calc(18px + env(safe-area-inset-top)) 18px calc(90px + env(safe-area-inset-bottom))}.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.brand{font-size:28px;font-weight:850;letter-spacing:-.8px}.pill{padding:7px 11px;border-radius:999px;background:#123b29;color:#73efaa;font-size:12px;font-weight:800}.hero,.card{background:#141820;border:1px solid #252b37;border-radius:22px;padding:19px;margin:14px 0}.eyebrow{color:#8f99ab;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.7px}.heroRow{display:flex;justify-content:space-between;gap:12px;align-items:end}.big{font-size:30px;font-weight:850;margin-top:4px}.safe{color:#73efaa}.muted{color:#8f99ab}.grid{display:grid;grid-template-columns:1fr 1fr;gap:11px;margin-top:12px}.metric{background:#10141b;border-radius:16px;padding:14px;min-height:88px}.label{color:#8f99ab;font-size:12px;text-transform:uppercase}.num{font-size:22px;font-weight:800;margin-top:5px}.sectionTitle{font-size:18px;font-weight:800}.row{display:flex;justify-content:space-between;align-items:center;padding:13px 0;border-bottom:1px solid #242a35}.row:last-child{border:0}.value{font-weight:750;text-align:right}.note{font-size:13px;line-height:1.45}.nav{position:fixed;left:50%;bottom:0;transform:translateX(-50%);width:min(760px,100%);display:grid;grid-template-columns:repeat(4,1fr);background:rgba(15,18,25,.96);border-top:1px solid #252b37;padding:9px 8px calc(9px + env(safe-area-inset-bottom));backdrop-filter:blur(16px)}.nav button{background:none;border:0;color:#7f899b;font-size:12px;font-weight:700;padding:7px}.nav button.active{color:#73efaa}.page{display:none}.page.active{display:block}.action{width:100%;border:0;border-radius:15px;padding:15px;font-size:16px;font-weight:800;margin-top:12px}h3{margin:0}.bad{color:#ff7d88}</style></head><body><div class="wrap"><div class="top"><div class="brand">Jev Desk</div><div class="pill">SHADOW ONLY</div></div>
<div id="home" class="page active"><div class="hero"><div class="eyebrow">Desk status</div><div class="heroRow"><div><div class="big" id="scanner">Loading…</div><div class="muted note" id="provider"></div></div><div class="safe value">REAL OFF</div></div></div><div class="card"><div class="sectionTitle">Shadow desk</div><div class="grid"><div class="metric"><div class="label">Qualified</div><div class="num" id="qualified">0</div></div><div class="metric"><div class="label">Clean evidence</div><div class="num" id="cleanout">0</div></div><div class="metric"><div class="label">Open trades</div><div class="num">0</div></div><div class="metric"><div class="label">Shadow P&L</div><div class="num">—</div></div></div><div class="note muted" id="homeNote">Collecting evidence before simulated trades.</div></div><div class="card"><div class="sectionTitle">Current activity</div><div class="row"><span class="muted">Scanner</span><span class="value safe">Running</span></div><div class="row"><span class="muted">Market candidates</span><span class="value" id="snapshots">0</span></div><div class="row"><span class="muted">Pending outcome checks</span><span class="value" id="pending">0</span></div><div class="row"><span class="muted">Complete cohorts</span><span class="value" id="cohorts">0</span></div></div></div>
<div id="trades" class="page"><div class="card"><div class="sectionTitle">Trades</div><p class="muted">No shadow trades yet. Candidates will appear here only after they genuinely qualify. Real execution remains disabled.</p></div></div>
<div id="research" class="page"><div class="card"><div class="sectionTitle">Research</div><div class="grid"><div class="metric"><div class="label">Snapshots</div><div class="num" id="rsnap">0</div></div><div class="metric"><div class="label">Decisions</div><div class="num" id="decisions">0</div></div><div class="metric"><div class="label">Outcomes</div><div class="num" id="outcomes">0</div></div><div class="metric"><div class="label">Due now</div><div class="num" id="due">0</div></div></div></div><div class="card"><div class="sectionTitle">Qualification</div><div class="row"><span class="muted">Reference</span><span class="value" id="qref">—</span></div><div class="row"><span class="muted">Python only</span><span class="value" id="qpy">—</span></div><div class="row"><span class="muted">Jev + Python</span><span class="value" id="qjev">—</span></div><div class="row"><span class="muted">Snapshots with age</span><span class="value" id="withage">0</span></div><p class="muted note" id="reasons">Loading reasons…</p></div><div class="card"><div class="sectionTitle">Replay evidence</div><div class="row"><span class="muted">Samples</span><span class="value" id="rsamples">0</span></div><div class="row"><span class="muted">Strategy status</span><span class="value" id="rpolicy">—</span></div><p class="muted note" id="revidence">Research only.</p></div></div>
<div id="settings" class="page"><div class="card"><div class="sectionTitle">Safety & settings</div><div class="row"><span class="muted">Mode</span><span class="value safe">Shadow</span></div><div class="row"><span class="muted">Real trades</span><span class="value safe">OFF</span></div><div class="row"><span class="muted">Storage</span><span class="value" id="storage">—</span></div><button class="action" id="run" onclick="runOnce()">Run research scan</button><p class="muted note" id="result">Public market discovery only. No wallet or order capability.</p></div></div></div>
<div class="nav"><button class="active" onclick="tab('home',this)">Home</button><button onclick="tab('trades',this)">Trades</button><button onclick="tab('research',this)">Research</button><button onclick="tab('settings',this)">Settings</button></div>
<script>function tab(id,b){document.querySelectorAll('.page').forEach(x=>x.classList.remove('active'));document.getElementById(id).classList.add('active');document.querySelectorAll('.nav button').forEach(x=>x.classList.remove('active'));b.classList.add('active')}function qs(v){return 'Q '+(v?.eligible||0)+' · U '+(v?.unscorable||0)+' · R '+(v?.rejected||0)}async function refresh(){let s=await(await fetch('/status')).json();scanner.textContent=s.scanner;provider.textContent=s.provider+' · every '+Math.round(s.cycle_seconds/60)+' min';snapshots.textContent=s.snapshots_logged;rsnap.textContent=s.snapshots_logged;decisions.textContent=s.decisions_logged;outcomes.textContent=s.outcomes_logged;pending.textContent=s.outcomes_pending;let h=await(await fetch('/research-health')).json();due.textContent=h.due_now;storage.textContent=h.storage;cleanout.textContent=(h.outcome_quality||{}).clean_done||0;cohorts.textContent=(h.outcome_quality||{}).clean_complete_cohorts||0;withage.textContent=(h.scoreable_snapshots||{}).with_age||0;try{let r=await(await fetch('/replay-report')).json(),q=r.qualification||{},ref=q.reference||{};qualified.textContent=ref.eligible||0;qref.textContent=qs(ref);qpy.textContent=qs(q.python_only);qjev.textContent=qs(q.jev_python);rsamples.textContent=r.sample_count||0;scoreable.textContent=r.scoreable_sample_count||0;rpolicy.textContent=(ref.eligible||0)>0?(r.frozen_policy||'CALIBRATING'):'NO QUALIFIED SAMPLE';revidence.textContent=r.sufficient_for_strategy_conclusion?'Evidence gate reached; validation remains sealed.':'Research only · evidence gate not reached.';let rr=ref.reasons||{};reasons.textContent='Top reasons · '+(Object.entries(rr).sort((a,b)=>b[1]-a[1]).map(([k,v])=>k+' '+v).join(' · ')||'none');homeNote.textContent=(ref.eligible||0)>0?'Qualified evidence exists; shadow-trade layer is next.':'Collecting scoreable evidence before simulated trades.'}catch(e){revidence.textContent='Replay report unavailable.'}}async function runOnce(){run.disabled=true;result.textContent='Scanning…';try{let d=await(await fetch('/run-once',{method:'POST'})).json();result.textContent='Observed '+d.count+' candidates. No real order sent.';await refresh()}catch(e){result.textContent='Scan failed.'}run.disabled=false}refresh();setInterval(refresh,10000)</script></body></html>"""