import asyncio
import logging
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from app.core.config import settings
from app.providers.geckoterminal import GeckoTerminalDiscovery
from app.providers.dexscreener import DexScreenerProvider
from app.providers.savip_dossier import SavipDossierProvider
from app.providers.savip_chain import SavipChainProvider
from app.research.engine import process_snapshot
from app.research.scheduler import ShadowScheduler,ingest_discovery
from app.research.outcomes import OutcomeWorker
from app.research.active_trades import ActiveTradeWorker
from app.research.qualification_worker import QualificationWorker
from app.research.savip_dex import SavipDexWorker
from app.research.savip_trade_cut import exact_trade_cut
from app.research.savip_chain_worker import SavipChainWorker
from app.research.savip_jev_validation_worker import SavipJevValidationWorker
from app.research.savip_jev_worker import SavipJevWorker
from app.research.savip_pick_worker import SavipPickWorker
from app.research.savip_shadow_lifecycle import SavipShadowEntryWorker,SavipShadowRiskWorker
from app.providers.savip_risk_market import SavipRiskMarketProvider
from app.providers.typesafe_jev import TypeSafeJevProvider
from app.providers.savip_social import FreeExactXProvider
from app.research.savip_jev_candidate import latest_chain_pass
from app.research.savip_jev_evidence import build_evidence
from app.research.savip_jev_adapter import run_typed_jev
from app.research.savip_jev_questions import QUESTION_SETS,RULES
from app.storage.db import log_savip_jev,claim_savip_jev,complete_savip_jev_claim,recent_savip_jev_outcomes
from app.storage.db import init_db,recent_events,research_counts,due_outcome_jobs,outcome_quality,scoreable_snapshot_quality,qualification_health,qualification_decision_totals,shadow_position_summary,shadow_positions_detail,shadow_exit_summary,fast_entry_summary,fast_shadow_positions_detail,fast_entry_diagnostics,fast_entry_discovery_funnel,savip_candidate_pool,savip_discovery_accounting,savip_positions_detail,recent_savip_chain_decisions
from app.research.replay_dataset import load_clean_replay_samples,load_qualification_replay_samples
from app.research.replay_pipeline import run_replay_research
from app.research.replay_diagnostics import replay_diagnostics
from app.research.qualification import qualification_diagnostics

app=FastAPI(title=settings.app_name,version=settings.version)
helius_research_status={"status":"not_run","owner_coverage_complete":False,"chain_pass_allowed":False}
async def _helius_one_shot_research():
    global helius_research_status
    from app.research.solana_helius_cursor_research import collect_cursor_owner_research
    key=os.environ.get("HELIUS_API_KEY","")
    mint=os.environ.get("HELIUS_RESEARCH_MINT","6Mix12LiHrQFojaQEnfPUC65Qkwd6X4Y5Qg93oFbordr")
    if not key or not mint:
        helius_research_status={"status":"not_configured","owner_coverage_complete":False,"chain_pass_allowed":False}
        return
    try:
        result=await collect_cursor_owner_research(mint,api_key=key,max_pages=20,page_size=1000,timeout_seconds=10)
        allowed={"status","pages","token_accounts","unique_owners","accounts_total","slot_stable","first_slot","last_slot","reported_total_min","reported_total_max","reported_total_stable","holder_count","largest_owner_amount","top_10_owner_amount","owner_balance_digest","account_balance_digest"}
        helius_research_status={k:v for k,v in result.items() if k in allowed}
        helius_research_status.update(owner_coverage_complete=False,chain_pass_allowed=False)
        if result.get("status")=="cursor_exhausted_unverified":
            import httpx
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response=await client.post("https://mainnet.helius-rpc.com/",params={"api-key":key},
                        json={"jsonrpc":"2.0","id":1,"method":"getTokenSupply","params":[mint,{"commitment":"confirmed"}]})
                    response.raise_for_status()
                    body=response.json()
                supply_result=body.get("result") if isinstance(body,dict) else None
                supply_value=supply_result.get("value") if isinstance(supply_result,dict) else None
                amount=supply_value.get("amount") if isinstance(supply_value,dict) else None
                supply_slot=(supply_result.get("context") or {}).get("slot") if isinstance(supply_result,dict) else None
                if isinstance(amount,str) and amount.isdecimal() and type(supply_slot) is int:
                    helius_research_status["supply_amount"]=int(amount)
                    helius_research_status["supply_slot"]=supply_slot
                    helius_research_status["account_sum_equals_supply"]=int(amount)==result.get("accounts_total")
                    helius_research_status["supply_reconciliation_status"]=(
                        "sum_match_non_atomic_unverified" if helius_research_status["account_sum_equals_supply"]
                        else "sum_mismatch_unverified")
                else:
                    helius_research_status["supply_reconciliation_status"]="invalid_supply_response"
            except (httpx.HTTPError,ValueError,TypeError):
                helius_research_status["supply_reconciliation_status"]="supply_request_failed"
    except Exception:
        helius_research_status={"status":"research_exception","owner_coverage_complete":False,"chain_pass_allowed":False}
    logging.getLogger(__name__).info("helius_one_shot_research status=%s",helius_research_status["status"])

provider=GeckoTerminalDiscovery()
dex_provider=DexScreenerProvider()
savip_dossier_provider=SavipDossierProvider(provider)
savip_chain_provider=SavipChainProvider()
typesafe_jev=TypeSafeJevProvider()
savip_x_provider=FreeExactXProvider()
savip_jev_validation_worker=SavipJevValidationWorker(typesafe_jev)
savip_pick_worker=SavipPickWorker(typesafe_jev)
savip_jev_worker=SavipJevWorker(typesafe_jev,on_pass=savip_pick_worker.run_cycle,x_provider=savip_x_provider)
savip_chain_worker=SavipChainWorker(savip_dossier_provider,savip_chain_provider,on_pass=savip_jev_worker.run_cycle)
savip_dex_worker=SavipDexWorker(dex_provider,on_enriched=savip_chain_worker.run_cycle)
savip_market_provider=SavipRiskMarketProvider()
savip_shadow_entry_worker=SavipShadowEntryWorker(savip_market_provider,seconds=30)
savip_pick_worker.on_accept=savip_shadow_entry_worker.run_cycle
savip_shadow_risk_worker=SavipShadowRiskWorker(savip_market_provider)
scheduler=ShadowScheduler(provider,30)
outcome_worker=OutcomeWorker(provider)
qualification_worker=QualificationWorker(provider)
active_trade_worker=ActiveTradeWorker(provider,seconds=15)

@app.on_event("startup")
async def startup():
    await init_db()
    scheduler.start()
    # Keep 5m pool qualification: its SNAPSHOT facts feed Savip FREE CUT.
    qualification_worker.start()
    # Pause legacy fast-entry, active-trade and outcome API polling.
    # Shared discovery and qualification remain active for Savip.
    savip_dex_worker.start()
    savip_chain_worker.start()
    # One-shot validation disabled: recurring Jev worker owns real CHAIN passes.
    savip_jev_worker.start()
    savip_pick_worker.start()
    savip_shadow_entry_worker.start()
    savip_shadow_risk_worker.start()
    asyncio.create_task(_helius_one_shot_research())

@app.get("/solana-research-status")
async def solana_research_status():
    return {"shadow_only":True,**helius_research_status}

@app.get("/health")
async def health():
    return {"ok":True,"version":settings.version,"shadow_only":True,"live_execution_enabled":False,"provider":provider.__class__.__name__,"provider_diagnostics":provider.last_diagnostics,"legacy_research":"PAUSED_SAVIP_PRIORITY"}

@app.get("/status")
async def status():
    r=await research_counts()
    return {"mode":"SHADOW","scanner":"RUNNING","legacy_research":"PAUSED_SAVIP_PRIORITY","provider":provider.__class__.__name__,"live_execution_enabled":False,"legacy_research":"PAUSED_SAVIP_PRIORITY","cycle_seconds":scheduler.seconds,"snapshots_logged":r["snapshots"],"decisions_logged":r["decisions"],"outcomes_logged":r["outcomes"],"outcomes_pending":r["pending"],"storage":r["storage"]}

@app.post("/run-once")
async def run_once():
    out=[]
    for s in await provider.discover():
        out.append(await ingest_discovery(s))
    return {"count":len(out),"provider_diagnostics":provider.last_diagnostics,"results":out,"message":"Candidates observed; qualification scheduled where age is available. No early strategy evaluation and no real order sent."}

@app.get("/events")
async def events(limit:int=50):return await recent_events(min(max(limit,1),500))

@app.get("/research-health")
async def research_health():
    r=await research_counts();q=await outcome_quality();sq=await scoreable_snapshot_quality();qh=await qualification_health();sp=await shadow_position_summary();se=await shadow_exit_summary()
    return {"ok":True,"storage":r["storage"],"snapshots":r["snapshots"],"decisions":r["decisions"],"outcomes":r["outcomes"],"pending":r["pending"],"due_now":r.get("due_now",0),"outcome_quality":q,"scoreable_snapshots":sq,"qualification_queue":qh,"shadow_positions":sp,"shadow_exit_arms":se,"active_trade_monitor":{"targets":active_trade_worker.last_targets,"marked_last_cycle":active_trade_worker.last_marked,"last_cycle_at":active_trade_worker.last_cycle_at,"last_error":active_trade_worker.last_error,"target_interval_seconds":active_trade_worker.seconds},"live_execution_enabled":False}

@app.get("/replay-report")
async def replay_report():
    samples=await load_clean_replay_samples(500)
    report=run_replay_research(samples) if samples else {"calibration_count":0,"holdout_count":0,"calibration_leaderboard":[],"frozen_policy":None,"holdout":None}
    diag=replay_diagnostics(samples,report.get("frozen_policy")) if samples else None
    q=qualification_diagnostics(samples)
    ref=q.get("reference",{})
    scoreable=int(ref.get("eligible",0))+int(ref.get("rejected",0))
    return {"ok":True,"evidence":"forward_clean","sample_count":len(samples),"scoreable_sample_count":scoreable,"qualified_sample_count":int(ref.get("eligible",0)),"unscorable_sample_count":int(ref.get("unscorable",0)),"sufficient_for_strategy_conclusion":scoreable>=100,**report,"diagnostics":diag,"qualification":q,"live_execution_enabled":False}

@app.get("/qualification-data")
async def qualification_data():
    totals=await qualification_decision_totals()
    return {"ok":True,"sample_count":totals["sample_count"],"qualification":totals["qualification"],"live_execution_enabled":False}




@app.get("/savip-chain-visibility-audit")
async def savip_chain_visibility_endpoint(hours:int=72):
    from app.storage.db import savip_chain_visibility_audit
    result=await savip_chain_visibility_audit(hours)
    return {"ok":True,**result,"real_execution_enabled":False}


@app.get("/savip-operational-health")
async def savip_operational_health():
    """Read-only sanitized worker heartbeat, without token IDs or provider secrets."""
    from datetime import datetime, timezone
    chain = savip_chain_worker
    return {
        "ok": True,
        "shadow_only": True,
        "real_execution_enabled": False,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "chain": {
            "cycle_started_at": chain.cycle_started_at,
            "cycle_finished_at": chain.cycle_finished_at,
            "cycle_running": chain.cycle_running,
            "interval_seconds": chain.seconds,
            "checked_last_cycle": chain.last_checked,
            "passed_last_cycle": chain.last_passed,
            "eligibility": chain.last_eligibility,
            "kill_counts": chain.last_kills,
            "last_error": chain.last_error,
        },
        "jev": {
            "checked_last_cycle": savip_jev_worker.last_checked,
            "passed_last_cycle": savip_jev_worker.last_passed,
            "last_error": savip_jev_worker.last_error,
        },
    }

@app.get("/savip-pipeline-diagnostics")
async def savip_pipeline_diagnostics():
    """Small read-only status endpoint: actual worker states, persisted outcomes, and pending queue."""
    from app.research.savip_jev_candidate import unjudged_chain_passes
    from app.storage.db import recent_savip_jev_outcomes
    from app.storage.db import savip_chain_jev_claim_audit
    return {
        "ok": True,
        "shadow_only": True,        "chain_pass_claim_audit": await savip_chain_jev_claim_audit(100),

        "real_execution_enabled": False,
        "chain": {
            "checked_last_cycle": savip_chain_worker.last_checked,
            "passed_last_cycle": savip_chain_worker.last_passed,
            "last_error": savip_chain_worker.last_error,
            "last_results": savip_chain_worker.last_candidate_results[:8],
            "eligibility": savip_chain_worker.last_eligibility,
        },
        "jev": {
            "configured": typesafe_jev.configured,
            "checked_last_cycle": savip_jev_worker.last_checked,
            "passed_last_cycle": savip_jev_worker.last_passed,
            "last_error": savip_jev_worker.last_error,
            "pending_unclaimed_chain_passes": [
                {"token_id": row["token_id"], "chain_event_id": row["chain_event_id"], "created_at": row["created_at"]}
                for row in await unjudged_chain_passes(10)
            ],
            "recent_outcomes": await recent_savip_jev_outcomes(10),
        },
        "pick": {"state": savip_pick_worker.state, "last_error": savip_pick_worker.last_error},
        "shadow_entry": {"state": savip_shadow_entry_worker.state, "last_error": savip_shadow_entry_worker.last_error},
        "shadow_risk": {"state": savip_shadow_risk_worker.state, "last_error": savip_shadow_risk_worker.last_error},
        "shadow_positions": await savip_positions_detail(10),
    }

@app.get("/savip-jev-outcomes")
async def savip_jev_outcomes():
    from app.storage.db import recent_savip_jev_outcomes
    return {"ok":True,"outcomes":await recent_savip_jev_outcomes(20),"checked_last_cycle":savip_jev_worker.last_checked,"passed_last_cycle":savip_jev_worker.last_passed,"last_error":savip_jev_worker.last_error,"live_execution_enabled":False}

@app.get("/savip-shadow-data")
async def savip_shadow_data():
    funnel=await savip_candidate_pool(window_minutes=15)
    survivors=funnel["free_cut_survivors"]
    trade=await exact_trade_cut(survivors)
    chain_funnel={}
    for candidate in funnel["free_cut_survivors"]:
        network=candidate.get("chain") or "unknown"
        chain_funnel[network]=chain_funnel.get(network,0)+1
    chain_rejections={}
    for result in savip_chain_worker.last_candidate_results:
        network=(result.get("token_id") or "").partition(":")[0] or "unknown"
        key=(result.get("outcome") or "unknown")+":"+(result.get("reason") or "unknown")
        bucket=chain_rejections.setdefault(network,{})
        bucket[key]=bucket.get(key,0)+1
    trade_by_chain={}
    for candidate in trade["survivors"]:
        network=candidate.get("chain") or "unknown"
        trade_by_chain[network]=trade_by_chain.get(network,0)+1
    return {"ok":True,"mode":"savip_trade_cut_shadow_v1","minimum_age_minutes":0,"maximum_age_minutes":15,"minimum_liquidity_usd":10000,"free_cut_by_chain":chain_funnel,"trade_cut_by_chain":trade_by_chain,"chain_results_by_network":chain_rejections,"momentum_m5_status":"observation_only_no_new_gate","candidate_source":"fresh_discovery","scanned":funnel["scanned"],"scan_sample_limit":1000,"scan_metric_definition":"most_recent_1000_unique_discovered_tokens_in_15m","free_cut_survivor_count":len(survivors),"wait_too_young_count":len(funnel["wait_too_young"]),"kills":funnel["kills"],"missing_fields":funnel.get("missing_fields",{}),"free_cut_survivors":survivors[:25],"trade_cut_survivor_count":len(trade["survivors"]),"trade_cut_kills":trade["kills"],"trade_cut_missing_fields":trade["missing_fields"],"trade_cut_survivors":trade["survivors"][:25],"dossier_cap_per_cycle":savip_chain_worker.cap,"trade_cut_enabled":True,"dossier_enabled":True,"chain_cut_enabled":True,"chain_cut":{"checked_last_cycle":savip_chain_worker.last_checked,"passed_last_cycle":savip_chain_worker.last_passed,"kills":savip_chain_worker.last_kills,"last_error":savip_chain_worker.last_error,"eligibility":savip_chain_worker.last_eligibility,"cycle_running":savip_chain_worker.cycle_running,"cycle_started_at":savip_chain_worker.cycle_started_at,"cycle_finished_at":savip_chain_worker.cycle_finished_at,"candidate_results":savip_chain_worker.last_candidate_results,"recent_persisted_decisions":await recent_savip_chain_decisions(50),"cooldown_remaining_seconds_by_token":{token:round(max(0,until-__import__("time").monotonic())) for token,until in savip_chain_worker._recent_tokens.items() if until>__import__("time").monotonic()}},"savip_trades":await savip_positions_detail(25),"entry_state":savip_shadow_entry_worker.state,"risk_state":savip_shadow_risk_worker.state,"jev_enabled":typesafe_jev.configured,"jev_state":{"checked_last_cycle":savip_jev_worker.last_checked,"passed_last_cycle":savip_jev_worker.last_passed,"last_error":savip_jev_worker.last_error},"jev_recent_outcomes":await recent_savip_jev_outcomes(10),"pick_enabled":True,"pick_state":"armed_waiting","dex_enrichment":{"checked_last_cycle":savip_dex_worker.last_checked,"enriched_last_cycle":savip_dex_worker.last_enriched,"last_error":savip_dex_worker.last_error},"real_execution_enabled":False}

@app.get("/savip-pool-coverage-research")
async def savip_pool_coverage_research():
    """Bounded, read-only observed pool evidence; not a completeness claim."""
    from app.research.savip_pool_coverage import summarize_pool_coverage
    observed=list(provider._research_history.values()) if hasattr(provider,"_research_history") else []
    summary=summarize_pool_coverage(observed)
    return {"ok":True,"shadow_only":True,"live_execution_enabled":False,
            "coverage_scope":"sampled_page_one_trending_and_new_pools_not_dex_complete",
            "observation_limit":500,"observed_pools":summary["observed_pools"],
            "unique_tokens":summary["unique_tokens"],"dex_counts":summary["dex_counts"],
            "tokens":summary["tokens"][:100]}

@app.get("/savip-discovery-accounting")
async def savip_discovery_accounting_data():
    return {"ok":True,"discovery":await savip_discovery_accounting(),"shadow_only":True,"live_execution_enabled":False}

@app.get("/savip-prechain-network-funnel")
async def savip_prechain_network_funnel_endpoint(hours:int=72):
    from app.storage.db import savip_prechain_network_funnel
    return {"ok":True,**(await savip_prechain_network_funnel(hours)),"real_execution_enabled":False}

@app.on_event("startup")
async def log_sanitized_chain_audit_once():
    """Emit aggregate, read-only CHAIN audit through the existing Render log integration."""
    async def emit():
        await asyncio.sleep(15)
        try:
            from collections import Counter
            from app.storage.db import savip_chain_rejection_audit
            audit=await savip_chain_rejection_audit(24)
            if not audit.get("available"):
                logging.getLogger("uvicorn.error").warning("SAVIP_CHAIN_AUDIT unavailable")
                return
            for row in audit.get("chain_decisions",[])[:60]:
                logging.getLogger("uvicorn.error").info(
                    "SAVIP_CHAIN_AUDIT network=%s reason=%s passed=%s unique=%s decisions=%s",
                    str(row.get("network","unknown"))[:24],
                    str(row.get("reason","unknown"))[:80],
                    str(row.get("passed","unknown"))[:8],
                    int(row.get("unique_tokens") or 0),
                    int(row.get("decisions") or 0),
                )
        except Exception as exc:
            logging.getLogger("uvicorn.error").warning("SAVIP_CHAIN_AUDIT_ERROR type=%s",type(exc).__name__)
    asyncio.create_task(emit())


@app.get("/savip-chain-rejection-audit")
async def savip_chain_rejection_audit_endpoint(hours:int=72):
    from app.storage.db import savip_chain_rejection_audit
    return {"ok":True,**(await savip_chain_rejection_audit(hours)),"real_execution_enabled":False}

@app.get("/savip-jev-ready")
async def savip_jev_ready():
    from app.research.savip_jev_candidate import unjudged_chain_passes
    from app.storage.db import open_savip_positions
    pending=await unjudged_chain_passes(1)
    held=await open_savip_positions()
    row=pending[0] if pending else None
    ready=bool(typesafe_jev.configured and row and not held)
    return {"ok":True,"jev_configured":typesafe_jev.configured,"chain_pass_candidate":ready,"token_id":row["token_id"] if ready else None,"chain_event_id":row["chain_event_id"] if ready else None,"state":"fresh_chain_pass_available" if ready else ("jev_not_configured" if not typesafe_jev.configured else "blocked_by_open_position" if held else "waiting_for_unjudged_chain_survivor"),"paid_call_made":False,"real_execution_enabled":False}

@app.post("/savip-jev-validate-once")
async def savip_jev_validate_once():
    return {"ok":False,"reason":"paid_validation_not_public","internal_state":savip_jev_validation_worker.state,"real_execution_enabled":False}

@app.get("/shadow-trades")
async def shadow_trades():
    rows=await shadow_positions_detail(100)
    policies=await shadow_exit_summary()
    return {"ok":True,"trades":rows,"policy_summary":policies,"live_execution_enabled":False}

@app.get("/",response_class=HTMLResponse)
async def dashboard():return HTMLResponse(DASHBOARD)

DASHBOARD="""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="theme-color" content="#090b10"><title>Jev Desk</title><style>*{box-sizing:border-box}body{margin:0;background:#090b10;color:#f5f7fb;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.wrap{max-width:760px;margin:auto;padding:calc(18px + env(safe-area-inset-top)) 18px calc(90px + env(safe-area-inset-bottom))}.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.brand{font-size:28px;font-weight:850;letter-spacing:-.8px}.pill{padding:7px 11px;border-radius:999px;background:#123b29;color:#73efaa;font-size:12px;font-weight:800}.hero,.card{background:#141820;border:1px solid #252b37;border-radius:22px;padding:19px;margin:14px 0}.eyebrow{color:#8f99ab;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.7px}.heroRow{display:flex;justify-content:space-between;gap:12px;align-items:end}.big{font-size:30px;font-weight:850;margin-top:4px}.safe{color:#73efaa}.muted{color:#8f99ab}.grid{display:grid;grid-template-columns:1fr 1fr;gap:11px;margin-top:12px}.metric{background:#10141b;border-radius:16px;padding:14px;min-height:88px}.label{color:#8f99ab;font-size:12px;text-transform:uppercase}.num{font-size:22px;font-weight:800;margin-top:5px}.sectionTitle{font-size:18px;font-weight:800}.row{display:flex;justify-content:space-between;align-items:center;padding:13px 0;border-bottom:1px solid #242a35}.row:last-child{border:0}.value{font-weight:750;text-align:right}.note{font-size:13px;line-height:1.45}.nav{position:fixed;left:50%;bottom:0;transform:translateX(-50%);width:min(760px,100%);display:grid;grid-template-columns:repeat(6,1fr);background:rgba(15,18,25,.96);border-top:1px solid #252b37;padding:9px 8px calc(9px + env(safe-area-inset-bottom));backdrop-filter:blur(16px)}.nav button{background:none;border:0;color:#7f899b;font-size:12px;font-weight:700;padding:7px}.nav button.active{color:#73efaa}.page{display:none}.page.active{display:block}.action{width:100%;border:0;border-radius:15px;padding:15px;font-size:16px;font-weight:800;margin-top:12px}h3{margin:0}.bad{color:#ff7d88}.liveStage{overflow:hidden}.livePulse{font-size:11px;color:#62e9a6;letter-spacing:.08em;float:right;animation:pulseGlow 2s ease-in-out infinite}.agentFlow{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:18px 0}.agent{min-width:0;display:flex;flex-direction:column;align-items:center;gap:6px;padding:14px 4px;background:#101824;border:1px solid #273446;border-radius:18px;transition:background .35s,border-color .35s,transform .35s}.agentIcon{font-size:25px;color:#7d9bb0}.agent b{font-size:12px}.agent small{font-size:12px;color:#a6b4c6}.agent.active{background:#14332d;border-color:#4fce9d;transform:translateY(-2px)}.agent.active .agentIcon{color:#65f0b3;animation:pulseGlow 1.8s infinite}@keyframes pulseGlow{50%{opacity:.5;filter:brightness(1.4)}}@media(prefers-reduced-motion:reduce){.agent,.agentIcon,.livePulse{animation:none!important;transition:none!important}}</style></head><body><div class="wrap"><div class="top"><div class="brand">Jev Desk</div><div class="pill">SHADOW ONLY</div></div>
<div id="savip" class="page active"><div class="card"><div class="sectionTitle">Early Launch Research · 0–15m</div><p class="muted note">ACTIVE TARGET · 0–15m discovery and 5m trade-activity gates; CHAIN verification remains mandatory.</p><div class="row"><span class="muted">Age window</span><span class="value">0–15 min</span></div><div class="row"><span class="muted">Liquidity minimum</span><span class="value">$10,000</span></div><div class="row"><span class="muted">Market cap minimum</span><span class="value">$30,000</span></div><div class="row"><span class="muted">5m volume minimum</span><span class="value">$3,000</span></div><div class="row"><span class="muted">5m transactions minimum</span><span class="value">20</span></div><div class="row"><span class="muted">5m buys / sells minimum</span><span class="value">10 / 2</span></div><div class="row"><span class="muted">Holders</span><span class="value">Observe growth</span></div><p class="muted note">Early-launch settings are experimental and have not been validated for profitability. Mint/freeze authority, wallet concentration, sellability and independent CHAIN proof remain mandatory before any shadow trade.</p></div><div class="card liveStage"><div class="sectionTitle">Savip Live Desk <span class="livePulse">● EVENT-DRIVEN</span></div><p class="muted note">Animated pipeline reflects observed backend counts. No synthetic trades or simulated decisions.</p><div class="agentFlow" aria-label="Savip pipeline activity"><div class="agent" id="agentDiscovery"><span class="agentIcon">◈</span><b>Discover</b><small id="agentDiscoverCount">—</small></div><div class="agent" id="agentFree"><span class="agentIcon">◇</span><b>FREE</b><small id="agentFreeCount">—</small></div><div class="agent" id="agentTrade"><span class="agentIcon">⇄</span><b>TRADE</b><small id="agentTradeCount">—</small></div><div class="agent" id="agentChain"><span class="agentIcon">⬡</span><b>CHAIN</b><small id="agentChainCount">—</small></div><div class="agent" id="agentJev"><span class="agentIcon">✦</span><b>Jev</b><small id="agentJevCount">—</small></div><div class="agent" id="agentPick"><span class="agentIcon">◎</span><b>PICK</b><small id="agentPickCount">—</small></div></div><p class="muted note" id="agentStatus" aria-live="polite">Waiting for live Savip telemetry.</p></div><div class="card"><div class="sectionTitle">Savip Funnel · 15m</div><p class="muted note">SHADOW ONLY · 0–15m launch eligibility · real trading OFF.</p><div class="grid"><div class="metric"><div class="label">Scanned</div><div class="num" id="svscan">0</div></div><div class="metric"><div class="label">Free cut</div><div class="num" id="svfree">0</div></div><div class="metric"><div class="label">Too young</div><div class="num" id="svwait">0</div></div><div class="metric"><div class="label">Dossier cap</div><div class="num" id="svcap">3</div></div></div></div><div class="card"><div class="sectionTitle">Pipeline</div><div class="row"><span class="muted">FREE CUT</span><span class="value safe">LIVE</span></div><div class="row"><span class="muted">TRADE CUT</span><span class="value safe" id="svtrade">LIVE</span></div><div class="row"><span class="muted">CHAIN / dossier</span><span class="value muted" id="svdossier">OFF</span></div><div class="row"><span class="muted">Jev judgments</span><span class="value muted" id="svjev">OFF</span></div><div class="row"><span class="muted">PICK</span><span class="value muted" id="svpick">OFF</span></div><div class="row"><span class="muted">Real execution</span><span class="value safe">OFF</span></div></div><div class="card"><div class="sectionTitle">Savip shadow trades</div><div id="svtrades"><p class="muted">No Savip shadow trades yet.</p></div></div><div class="card"><div class="sectionTitle">Pipeline journal</div><p class="muted note">Persisted events · newest first. FREE CUT is a rolling cohort, not an active queue.</p><div class="note muted" id="svqueue">Loading pipeline eligibility...</div><div id="svjournal" aria-live="polite"><p class="muted">Loading journal...</p></div></div><div class="card"><div class="sectionTitle">FREE CUT evidence</div><p class="muted note" id="svkills">Loading rejection reasons...</p><div id="svsurvivors"><p class="muted">Loading survivors...</p></div></div></div>
<div id="settings" class="page"><div class="card"><div class="sectionTitle">Safety & settings</div><div class="row"><span class="muted">Mode</span><span class="value safe">Shadow</span></div><div class="row"><span class="muted">Real trades</span><span class="value safe">OFF</span></div><div class="row"><span class="muted">Storage</span><span class="value" id="storage">—</span></div><button class="action" id="run" onclick="runOnce()">Run research scan</button><p class="muted note" id="result">Public market discovery only. No wallet or order capability.</p></div></div></div>
<div class="nav"><button class="active" onclick="tab('savip',this)">Savip</button><button onclick="tab('settings',this)">Settings</button></div>
<script>
function tab(id,b){document.querySelectorAll('.page').forEach(x=>x.classList.remove('active'));document.getElementById(id).classList.add('active');document.querySelectorAll('.nav button').forEach(x=>x.classList.remove('active'));b.classList.add('active')}
function qs(v){return 'Q '+(v?.eligible||0)+' · U '+(v?.unscorable||0)+' · R '+(v?.rejected||0)}
async function refresh(){
 try{
  const r=await fetch('/savip-shadow-data',{cache:'no-store'});
  if(!r.ok)throw new Error('Savip unavailable');
  renderSavipMetrics(await r.json());
 }catch(e){const el=document.getElementById('agentStatus');if(el)el.textContent='Savip metrics unavailable · last observed values retained';}
}
function renderSavipMetrics(s){
 const put=(id,value)=>{const el=document.getElementById(id);if(el)el.textContent=String(value??'—')};
 put('svscan',s.scanned);put('svfree',s.free_cut_survivor_count);put('svwait',s.wait_too_young_count);put('svcap',s.dossier_cap_per_cycle);
 put('svtrade',s.trade_cut_enabled?'ON':'OFF');put('svdossier',s.dossier_enabled?'ON':'OFF');put('svjev',s.jev_enabled?'ON · waiting':'OFF · not configured');put('svpick',s.pick_enabled?'ON · waiting':'OFF');
 const kills=s.kills||{},missing=s.missing_fields||{};
 put('svkills','FREE CUT rejected: '+(Object.entries(kills).map(([k,v])=>k+' '+v).join(' · ')||'none')+' · Missing: '+(Object.entries(missing).map(([k,v])=>k+' '+v).join(' · ')||'none'));
 const survivors=document.getElementById('svsurvivors');
 if(survivors){survivors.replaceChildren();const list=s.free_cut_survivors||[];if(!list.length)survivors.textContent='No qualifying tokens in current 15m cohort.';else for(const item of list){const row=document.createElement('div');row.className='row';const id=String(item.token_id||'');row.textContent=id.split(':')[0].toUpperCase()+' · '+id.split(':').pop().slice(0,7)+'… · $'+Math.round(Number(item.liquidity_usd||0)).toLocaleString()+' liquidity';survivors.append(row)}}
 const trades=document.getElementById('svtrades');if(trades){trades.replaceChildren();const list=s.savip_trades||[];if(!list.length)trades.textContent='No Savip shadow trades yet.';else for(const t of list){const row=document.createElement('div');row.className='row';row.textContent=String(t.token_id||'shadow position')+' · '+String(t.status||'unknown');trades.append(row)}}
 updateSavipAgents(s);
}
function updateSavipAgents(s){
 const eligibility=(s.chain_cut||{}).eligibility||{};
 const values=[s.scanned,s.free_cut_survivor_count,s.trade_cut_survivor_count,(s.chain_cut||{}).checked_last_cycle,(s.jev_state||{}).checked_last_cycle,0];
 const ids=['Discovery','Free','Trade','Chain','Jev','Pick'];
 ids.forEach((name,i)=>{const el=document.getElementById('agent'+name),counter=document.getElementById('agent'+name+'Count');if(counter)counter.textContent=values[i]===null||values[i]===undefined?'—':String(values[i]);if(el)el.classList.toggle('active',Number(values[i])>0)});
 const st=document.getElementById('agentStatus');if(st)st.textContent=values[1]===0?'No FREE CUT survivors in current launch cohort.':values[2]===0?'FREE CUT candidates observed; awaiting 5m trade verification.':'Trade candidates observed; CHAIN and Jev must independently verify before shadow entry.';
}
async function refreshSavipJournal(){
 const journal=document.getElementById('svjournal'),queue=document.getElementById('svqueue');
 try{
  const [er,sr]=await Promise.all([fetch('/events?limit=500',{cache:'no-store'}),fetch('/savip-shadow-data',{cache:'no-store'})]);
  if(!er.ok||!sr.ok)throw new Error('journal unavailable');
  const events=await er.json(),state=await sr.json(),elig=(state.chain_cut||{}).eligibility||{};renderSavipMetrics(state);
  queue.textContent='FREE (15m): '+(state.free_cut_survivor_count||0)+' · TRADE: '+(elig.trade_survivors??'—')+' · Fresh CHAIN: '+(elig.fresh_candidates??'—')+' · 24h checked: '+(elig.persisted_recent_skips??'—')+' · Selected: '+(elig.selected_for_checks??'—');
  journal.replaceChildren();
  const rows=(Array.isArray(events)?events:[]).filter(e=>e&&(/^(DISCOVERY|SAVIP_|JEV_|PICK|SHADOW)/.test(String(e.event_type||'')))).slice(0,60);
  if(!rows.length){journal.textContent='No pipeline events in recent history.';return}
  for(const e of rows){
   let p=e.payload_json||{};if(typeof p==='string'){try{p=JSON.parse(p)}catch(_){p={}}}if(!p||typeof p!=='object'||Array.isArray(p))p={};const line=document.createElement('div');line.style.cssText='padding:11px 0;border-bottom:1px solid #252b37';
   const heading=document.createElement('div');heading.style.fontWeight='750';
   const id=String(e.token_id||p.token_id||'').split(':').pop();
   heading.textContent=String(e.event_type||'EVENT')+' · '+(id?id.slice(0,6)+'…'+id.slice(-5):'system');
   const detail=document.createElement('div');detail.className='muted note';
   const ev=(p.evidence&&typeof p.evidence==='object'&&!Array.isArray(p.evidence))?p.evidence:{},reason=p.reason||p.chain_reason||p.status||p.outcome||ev.status||'';
   detail.textContent=String(e.created_at||'')+' · '+String(reason).slice(0,180)+(Array.isArray(ev.mismatched_fields)?' · mismatch: '+ev.mismatched_fields.map(String).join(', '):'');
   line.append(heading,detail);journal.append(line);
  }
 }catch(err){queue.textContent='Pipeline eligibility unavailable';journal.textContent='Journal unavailable; safety gates unchanged.'}
}
async function runOnce(){run.disabled=true;result.textContent='Scanning…';try{let d=await(await fetch('/run-once',{method:'POST'})).json();result.textContent='Observed '+d.count+' candidates. No real order sent.';await refresh()}catch(e){result.textContent='Scan failed.'}run.disabled=false}
refresh();refreshSavipJournal();setInterval(refresh,10000);setInterval(refreshSavipJournal,30000)
</script></body></html>"""
