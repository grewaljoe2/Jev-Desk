"""Bounded Savip dossier/CHAIN worker. Shadow research only."""
import asyncio
import time
from datetime import datetime, timezone
from app.research.savip_trade_cut import exact_trade_cut
from app.storage.db import savip_candidate_pool,open_savip_positions, savip_recent_chain_tokens
from app.research.savip_chain_cut import evaluate_chain, known_chain_kill
from app.research.solana_account_lower_bound import classify_account_lower_bound
from app.core.config import settings

class SavipChainWorker:
    def __init__(self,dossier,sol_chain,seconds=60,cap=6,on_pass=None):
        self.dossier=dossier;self.sol_chain=sol_chain;self.seconds=seconds;self.cap=cap;self.on_pass=on_pass;self.task=None
        self.last_checked=0;self.last_passed=0;self.last_kills={};self.last_error=None;self._cycle_lock=asyncio.Lock();self._next_dossier_retry_at=0.0;self.cycle_started_at=None;self.cycle_finished_at=None;self.cycle_running=False;self.last_candidate_results=[];self.last_eligibility={};self._recent_tokens={}
    async def run_cycle(self):
        if self._cycle_lock.locked():return
        async with self._cycle_lock:
            await self._run_cycle_locked()
    async def _run_cycle_locked(self):
        self.last_checked=0;self.last_passed=0;self.last_kills={};self.last_error=None;self.last_candidate_results=[];self.last_eligibility={}
        self.cycle_started_at=datetime.now(timezone.utc).isoformat();self.cycle_running=True
        try:
            await self._evaluate_cycle()
        finally:
            self.cycle_running=False;self.cycle_finished_at=datetime.now(timezone.utc).isoformat()
    async def _evaluate_cycle(self):
        if await open_savip_positions():
            self.last_eligibility={"blocked_by_open_position":True}
            return
        # Match the audited 72h cohort; provider calls remain capped by self.cap.
        funnel=await savip_candidate_pool(window_minutes=72*60,limit=10000)
        trade=await exact_trade_cut(funnel["free_cut_survivors"])
        if time.monotonic()<self._next_dossier_retry_at:
            self.last_eligibility={"trade_survivors":len(trade["survivors"]),"dossier_cooldown":True}
            self.last_error="dossier_provider_cooldown";return
        now=time.monotonic()
        self._recent_tokens={k:v for k,v in self._recent_tokens.items() if v>now}
        persisted_recent=await savip_recent_chain_tokens(hours=24)
        fresh=[row for row in trade["survivors"] if row["token_id"] not in self._recent_tokens and row["token_id"] not in persisted_recent]
        self.last_eligibility={"free_survivors":len(funnel["free_cut_survivors"]),
            "trade_survivors":len(trade["survivors"]),
            "persisted_recent_skips":sum(row["token_id"] in persisted_recent for row in trade["survivors"]),
            "in_memory_cooldown_skips":sum(row["token_id"] not in persisted_recent and row["token_id"] in self._recent_tokens for row in trade["survivors"]),
            "fresh_candidates":len(fresh)}
        # Prioritize freshest qualified pools within the existing shared GT pacing budget.
        fresh.sort(key=lambda row: (float(row.get("age_minutes") or 1e12),row.get("token_id") or ""))
        eligible=[row for row in fresh if row.get("chain")!="solana" or not self.sol_chain.cooling_down()]
        # Favor checks that do not depend on the constrained public Solana RPC.
        # Retain youngest-first priority within each network group.
        eligible.sort(key=lambda row: (row.get("chain")=="solana", float(row.get("age_minutes") or 1e12), row.get("token_id") or ""))
        self.last_eligibility["solana_rpc_cooldown_skips"]=len(fresh)-len(eligible)
        self.last_eligibility["selected_for_checks"]=min(len(eligible),self.cap)
        for row in eligible[:self.cap]:
            if row.get("chain")=="solana" and self.sol_chain.cooling_down():
                continue
            self.last_checked+=1
            try:
                # Token IDs are canonical chain:address; the FREE/TRADE SQL projection
                # does not guarantee a standalone address key.
                token_id=row.get("token_id") or ""
                address=row.get("address") or token_id.partition(":")[2]
                if not address or not row.get("chain"):
                    raise RuntimeError("missing_chain_address")
                d=await self.dossier.fetch(row["chain"],address)
                if not d: raise RuntimeError("missing_dossier")
                d={**row,**d}
                if row["chain"]=="solana":
                    early_reason=known_chain_kill(d)
                    if early_reason:
                        await self._persist(row["token_id"],d,False,early_reason)
                        self.last_kills[early_reason]=self.last_kills.get(early_reason,0)+1
                        self.last_candidate_results.append({"token_id":row["token_id"],"outcome":"kill","reason":early_reason,"wallet_rpc_skipped":True})
                        self._recent_tokens[row["token_id"]]=time.monotonic()+900.0
                        continue
                    d["solana_wallet_rpc_status"]="pending"
                    try:
                        sf=await self.sol_chain.fetch("solana",address)
                        if sf:
                            lower=sf.get("largest_token_account_fraction")
                            if classify_account_lower_bound(lower)=="reject":
                                d["solana_largest_account_fraction"]=lower
                                d["solana_wallet_rpc_status"]="account_lower_bound_reject"
                                await self._persist(row["token_id"],d,False,"top_wallet_lower_bound")
                                self.last_kills["top_wallet_lower_bound"]=self.last_kills.get("top_wallet_lower_bound",0)+1
                                self.last_candidate_results.append({"token_id":row["token_id"],"outcome":"kill","reason":"top_wallet_lower_bound"})
                                self._recent_tokens[row["token_id"]]=time.monotonic()+900.0
                                continue
                            verified=await self.sol_chain.fetch_independent_owner_evidence(address)
                            if verified.get("owner_coverage_complete") is True:
                                d["top_wallet_percent"]=verified["top_wallet_fraction"]
                                d["holder_count"]=verified["holder_count"]
                                d["top_10_percent"]=verified["top_10_percent"]
                                d["solana_wallet_rpc_status"]="ok"
                                d["solana_owner_evidence_source"]=verified.get("source")
                            else:
                                d["top_wallet_percent"]=None
                                d["solana_wallet_rpc_status"]="unverified_owner_coverage"
                                d["solana_owner_evidence_status"]=verified.get("status")
                                d["solana_owner_primary_status"]=verified.get("primary_status")
                                d["solana_owner_secondary_status"]=verified.get("secondary_status")
                                d["solana_owner_failed_provider"]=verified.get("failed_provider")
                                # Helius can supply bounded candidate diagnostics when public
                                # providers cannot attest a complete wallet map. Its
                                # multi-slot cursor scan is NEVER accepted as a CHAIN pass.
                                helius=await self.sol_chain.fetch_helius_owner_evidence(address)
                                d["solana_helius_evidence_status"]=helius.get("status")
                                d["solana_helius_token_accounts"]=helius.get("token_accounts")
                                d["solana_helius_slot_stable"]=helius.get("slot_stable")
                                # Single-candidate atomic proof probe only when explicitly
                                # enabled; never changes CHAIN approval or shadow execution.
                                if settings.solana_atomic_canary_enabled and not getattr(self,"_atomic_canary_used",False):
                                    self._atomic_canary_used=True
                                    atomic=await self.sol_chain.fetch_atomic_owner_research(address)
                                    d["solana_atomic_owner_status"]=atomic.get("status")
                                    d["solana_atomic_owner_holder_count"]=atomic.get("holder_count")
                                    d["solana_atomic_owner_primary_slot"]=atomic.get("primary_snapshot_slot")
                                    d["solana_atomic_owner_secondary_slot"]=atomic.get("secondary_snapshot_slot")
                    except RuntimeError as rpc_error:
                        if "solana_rpc_" not in str(rpc_error):raise
                        # The GT dossier is still valid; do not claim the wallet check passed.
                        d["top_wallet_percent"]=None
                        rpc_reason=str(rpc_error)
                        d["solana_wallet_rpc_status"]="unavailable_rate_limited" if "429" in rpc_reason else "unavailable_rpc_error"
                        d["solana_wallet_rpc_error"]=rpc_reason
                missing=[key for key in ("holder_count","top_wallet_percent","top_10_percent","is_honeypot","mint_authority","freeze_authority") if d.get(key) is None]
                d["missing_chain_fields"]=missing
                if d.get("solana_wallet_rpc_status")=="unavailable_rate_limited":
                    raise RuntimeError("solana_wallet_check_pending_429: "+d.get("solana_wallet_rpc_error","unknown"))
                if d.get("solana_wallet_rpc_status")=="unavailable_rpc_error":
                    raise RuntimeError("solana_wallet_check_pending_unverified: "+d.get("solana_wallet_rpc_error","unknown"))
                if row["chain"]=="solana" and d.get("solana_wallet_rpc_status")!="ok":
                    evidence_status=str(d.get("solana_owner_evidence_status") or d.get("solana_wallet_rpc_status") or "unknown")
                    provider_status=d.get("solana_owner_primary_status") if d.get("solana_owner_failed_provider")=="primary" else d.get("solana_owner_secondary_status")
                    if provider_status:evidence_status+=" / "+str(d.get("solana_owner_failed_provider"))+":"+str(provider_status)
                    raise RuntimeError("solana_wallet_check_pending_unverified: "+evidence_status[:80])
                ok,reason=evaluate_chain(d)
                await self._persist(row["token_id"],d,ok,reason)
                self.last_candidate_results.append({"token_id":row["token_id"],"outcome":"pass" if ok else "kill","reason":reason,"missing_chain_fields":missing,"top_10_percent":d.get("top_10_percent"),"holder_count":d.get("holder_count"),"top_wallet_percent":d.get("top_wallet_percent"),"top_10_limit_percent":60.0,"dossier_source":d.get("source")})
                self._recent_tokens[row["token_id"]]=time.monotonic()+900.0
                if ok:
                    self.last_passed+=1
                    if self.on_pass:await self.on_pass()
                else:self.last_kills[reason]=self.last_kills.get(reason,0)+1
            except Exception as e:
                self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
                await self._record_attempt(row.get("token_id"),self.last_error)
                self.last_candidate_results.append({"token_id":row.get("token_id"),"outcome":"retry_pending" if "429" in str(e) or "pending_unverified" in str(e) else "error","reason":self.last_error})
                # Provider capability/coverage failures cannot be fixed by a two-minute retry.
                # Avoid hammering public RPCs with the same token while preserving
                # fail-closed status and allowing new candidates to be evaluated.
                reason_text=str(e)
                infrastructure=("rate_limited","http_error","rpc_error","response_too_large",
                                "timeout","transport_error","invalid_rpc_response",
                                "snapshot_slot_mismatch","mint_accounts_slot_mismatch",
                                "cross_provider_slot_mismatch","stale_supply_snapshot",
                                "independent_confirmation_unavailable")
                cooldown=3600.0 if any(x in reason_text for x in infrastructure) else (300.0 if "429" in reason_text else 120.0)
                self._recent_tokens[row["token_id"]]=time.monotonic()+cooldown
                if "solana_rpc_rate_limited_429" in str(e) or "solana_rpc_cooldown_429" in str(e):
                    # Avoid exhausting a cooling Solana RPC; other chains remain eligible.
                    continue
                if "provider_rate_limited_429" in str(e):
                    # GeckoTerminal is shared with discovery; avoid repeated
                    # dossier requests while its global 429 cooldown runs.
                    self._next_dossier_retry_at=time.monotonic()+120.0
                    break
    async def _record_attempt(self,token_id,reason):
        if not settings.database_url or not token_id:return
        try:
            import psycopg,json
            async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
                await db.execute("INSERT INTO events(event_type,token_id,arm,payload_json,created_at) VALUES(%s,%s,%s,%s::jsonb,CURRENT_TIMESTAMP)",("SAVIP_CHAIN_ATTEMPT",token_id,"savip_reference",json.dumps({"reason":reason[:200]})))
                await db.commit()
        except Exception:
            pass

    async def _persist(self,token_id,d,ok,reason):
        if not settings.database_url:return
        import psycopg,json
        async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
            await db.execute("INSERT INTO events(event_type,token_id,arm,payload_json,created_at) VALUES(%s,%s,%s,%s::jsonb,CURRENT_TIMESTAMP)",("SAVIP_CHAIN",token_id,"savip_reference",json.dumps({**d,"chain_pass":ok,"chain_reason":reason},default=str)))
            await db.commit()
    async def loop(self):
        while True:
            try:await self.run_cycle()
            except Exception as e:self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task:self.task=asyncio.create_task(self.loop())
