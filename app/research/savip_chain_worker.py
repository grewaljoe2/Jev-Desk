"""Bounded Savip dossier/CHAIN worker. Shadow research only."""
import asyncio
import time
from datetime import datetime, timezone
from app.research.savip_trade_cut import exact_trade_cut
from app.storage.db import savip_candidate_pool,open_savip_positions
from app.research.savip_chain_cut import evaluate_chain
from app.core.config import settings

class SavipChainWorker:
    def __init__(self,dossier,sol_chain,seconds=60,cap=6,on_pass=None):
        self.dossier=dossier;self.sol_chain=sol_chain;self.seconds=seconds;self.cap=cap;self.on_pass=on_pass;self.task=None
        self.last_checked=0;self.last_passed=0;self.last_kills={};self.last_error=None;self._cycle_lock=asyncio.Lock();self._next_dossier_retry_at=0.0;self.cycle_started_at=None;self.cycle_finished_at=None;self.cycle_running=False;self.last_candidate_results=[];self._recent_tokens={}
    async def run_cycle(self):
        if self._cycle_lock.locked():return
        async with self._cycle_lock:
            await self._run_cycle_locked()
    async def _run_cycle_locked(self):
        self.last_checked=0;self.last_passed=0;self.last_kills={};self.last_error=None;self.last_candidate_results=[]
        self.cycle_started_at=datetime.now(timezone.utc).isoformat();self.cycle_running=True
        try:
            await self._evaluate_cycle()
        finally:
            self.cycle_running=False;self.cycle_finished_at=datetime.now(timezone.utc).isoformat()
    async def _evaluate_cycle(self):
        if await open_savip_positions():return
        funnel=await savip_candidate_pool(window_minutes=72*60)
        trade=await exact_trade_cut(funnel["free_cut_survivors"])
        if time.monotonic()<self._next_dossier_retry_at:
            self.last_error="dossier_provider_cooldown";return
        now=time.monotonic()
        self._recent_tokens={k:v for k,v in self._recent_tokens.items() if v>now}
        fresh=[row for row in trade["survivors"] if row["token_id"] not in self._recent_tokens]
        # Prioritize freshest qualified pools within the existing shared GT pacing budget.
        fresh.sort(key=lambda row: (float(row.get("age_minutes") or 1e12),row.get("token_id") or ""))
        for row in fresh[:self.cap]:
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
                    sf=await self.sol_chain.fetch("solana",address)
                    if sf:d["top_wallet_percent"]=sf.get("top_wallet_fraction")
                missing=[key for key in ("holder_count","top_wallet_percent","top_10_percent","is_honeypot","mint_authority","freeze_authority") if d.get(key) is None]
                d["missing_chain_fields"]=missing
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
                self.last_candidate_results.append({"token_id":row.get("token_id"),"outcome":"retry_pending" if "429" in str(e) else "error","reason":self.last_error})
                if "429" not in str(e):
                    self._recent_tokens[row["token_id"]]=time.monotonic()+120.0
                if "solana_rpc_rate_limited_429" in str(e) or "solana_rpc_cooldown_429" in str(e):
                    # Avoid exhausting a cooling Solana RPC; other chains remain eligible.
                    continue
                if "provider_rate_limited_429" in str(e):
                    # GeckoTerminal is shared with discovery; avoid repeated
                    # dossier requests while its global 429 cooldown runs.
                    self._next_dossier_retry_at=time.monotonic()+120.0
                    break
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
