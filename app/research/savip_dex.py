import asyncio
import httpx
from app.storage.db import log_savip_dex
from app.research.savip_targets import savip_dex_targets_72h

class SavipDexWorker:
    def __init__(self,provider,seconds=180,on_enriched=None):
        self.provider=provider;self.seconds=seconds;self.on_enriched=on_enriched;self.task=None;self.last_checked=0;self.last_enriched=0;self.last_error=None;self.last_rate_limited=0;self.last_skipped_due_to_429=0
    async def run_cycle(self):
        self.last_checked=0;self.last_enriched=0;self.last_error=None;self.last_rate_limited=0;self.last_skipped_due_to_429=0
        targets=await savip_dex_targets_72h(25)
        # Group exact pool addresses by network. One batch request can replace
        # up to 20 individual public API calls without cross-pair substitution.
        groups={}
        for row in targets:
            groups.setdefault(row["chain"],[]).append(row)
        remaining=len(targets)
        rate_limited=False
        for chain,rows in groups.items():
            for start in range(0,len(rows),20):
                batch=rows[start:start+20]
                self.last_checked+=len(batch)
                remaining-=len(batch)
                try:
                    facts_list=await self.provider.fetch_pairs(chain,[row["pool_id"] for row in batch])
                    if len(facts_list)!=len(batch):raise RuntimeError("dex_batch_count_mismatch")
                    for row,facts in zip(batch,facts_list):
                        if facts:
                            await log_savip_dex(row["token_id"],row["payload_json"],facts)
                            self.last_enriched+=1
                except httpx.HTTPStatusError as e:
                    self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
                    if e.response.status_code==429:
                        self.last_rate_limited+=1
                        self.last_skipped_due_to_429=remaining
                        rate_limited=True
                        break
                except RuntimeError as e:
                    self.last_error=str(e)[:160]
                    if str(e)=="dex_cooldown":
                        self.last_skipped_due_to_429=remaining
                        rate_limited=True
                        break
                except Exception as e:
                    self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
                await asyncio.sleep(3.0)
            if rate_limited:break
        if self.on_enriched:await self.on_enriched()
    async def loop(self):
        while True:
            try:await self.run_cycle()
            except Exception as e:self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task:self.task=asyncio.create_task(self.loop())
