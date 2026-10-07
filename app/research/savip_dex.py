import asyncio
import httpx
from app.storage.db import log_savip_dex
from app.research.savip_targets import savip_dex_targets_72h

class SavipDexWorker:
    def __init__(self,provider,seconds=900,on_enriched=None):
        self.provider=provider;self.seconds=seconds;self.on_enriched=on_enriched;self.task=None;self.last_checked=0;self.last_enriched=0;self.last_error=None;self.last_rate_limited=0;self.last_skipped_due_to_429=0
    async def run_cycle(self):
        self.last_checked=0;self.last_enriched=0;self.last_error=None;self.last_rate_limited=0;self.last_skipped_due_to_429=0
        targets=await savip_dex_targets_72h(25)
        for index,row in enumerate(targets):
            self.last_checked+=1
            try:
                facts=await self.provider.fetch_pair(row["chain"],row["pool_id"])
                if facts:
                    await log_savip_dex(row["token_id"],row["payload_json"],facts);self.last_enriched+=1
            except httpx.HTTPStatusError as e:
                self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
                if e.response.status_code==429:
                    self.last_rate_limited+=1
                    self.last_skipped_due_to_429=len(targets)-index-1
                    # Respect the provider limit: stop the batch, retry next cycle.
                    break
            except Exception as e:self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
            # Limit sustained requests on the public endpoint (~30/min maximum).
            await asyncio.sleep(3.0)
        if self.on_enriched:await self.on_enriched()
    async def loop(self):
        while True:
            try:await self.run_cycle()
            except Exception as e:self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task:self.task=asyncio.create_task(self.loop())
