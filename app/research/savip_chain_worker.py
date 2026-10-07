"""Bounded Savip dossier/CHAIN worker. Shadow research only."""
import asyncio
from app.research.savip_trade_cut import exact_trade_cut
from app.storage.db import savip_candidate_pool,open_savip_positions
from app.research.savip_chain_cut import evaluate_chain
from app.core.config import settings

class SavipChainWorker:
    def __init__(self,dossier,sol_chain,seconds=900,cap=3,on_pass=None):
        self.dossier=dossier;self.sol_chain=sol_chain;self.seconds=seconds;self.cap=cap;self.on_pass=on_pass;self.task=None
        self.last_checked=0;self.last_passed=0;self.last_kills={};self.last_error=None;self._cycle_lock=asyncio.Lock()
    async def run_cycle(self):
        if self._cycle_lock.locked():return
        async with self._cycle_lock:
            await self._run_cycle_locked()
    async def _run_cycle_locked(self):
        self.last_checked=0;self.last_passed=0;self.last_kills={};self.last_error=None
        if await open_savip_positions():return
        funnel=await savip_candidate_pool(window_minutes=72*60)
        trade=await exact_trade_cut(funnel["free_cut_survivors"])
        for row in trade["survivors"][:self.cap]:
            self.last_checked+=1
            try:
                d=await self.dossier.fetch(row["chain"],row["address"])
                if not d: raise RuntimeError("missing_dossier")
                d={**row,**d}
                if row["chain"]=="solana":
                    sf=await self.sol_chain.fetch("solana",row["address"])
                    if sf:d["top_wallet_percent"]=sf.get("top_wallet_fraction")
                ok,reason=evaluate_chain(d)
                await self._persist(row["token_id"],d,ok,reason)
                if ok:
                    self.last_passed+=1
                    if self.on_pass:await self.on_pass()
                else:self.last_kills[reason]=self.last_kills.get(reason,0)+1
            except Exception as e:
                self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
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
