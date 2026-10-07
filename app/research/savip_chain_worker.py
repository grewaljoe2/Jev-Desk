"""Bounded Savip dossier/CHAIN worker. Shadow research only."""
import asyncio
from app.research.savip_trade_cut import exact_trade_cut
from app.storage.db import savip_candidate_pool
from app.research.savip_chain_cut import evaluate_chain

class SavipChainWorker:
    def __init__(self,dossier,sol_chain,seconds=900,cap=3):
        self.dossier=dossier;self.sol_chain=sol_chain;self.seconds=seconds;self.cap=cap;self.task=None
        self.last_checked=0;self.last_passed=0;self.last_kills={};self.last_error=None
    async def run_cycle(self):
        self.last_checked=0;self.last_passed=0;self.last_kills={};self.last_error=None
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
                if ok:self.last_passed+=1
                else:self.last_kills[reason]=self.last_kills.get(reason,0)+1
            except Exception as e:
                self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
    async def loop(self):
        while True:
            try:await self.run_cycle()
            except Exception as e:self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task:self.task=asyncio.create_task(self.loop())
