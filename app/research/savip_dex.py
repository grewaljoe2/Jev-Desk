import asyncio
from app.storage.db import log_savip_dex
from app.research.savip_targets import savip_dex_targets_72h

class SavipDexWorker:
    def __init__(self,provider,seconds=900,on_enriched=None):
        self.provider=provider;self.seconds=seconds;self.on_enriched=on_enriched;self.task=None;self.last_checked=0;self.last_enriched=0;self.last_error=None
    async def run_cycle(self):
        self.last_checked=0;self.last_enriched=0;self.last_error=None
        for row in await savip_dex_targets_72h(25):
            self.last_checked+=1
            try:
                facts=await self.provider.fetch_pair(row["chain"],row["pool_id"])
                if facts:
                    await log_savip_dex(row["token_id"],row["payload_json"],facts);self.last_enriched+=1
            except Exception as e:self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
        if self.on_enriched:await self.on_enriched()
    async def loop(self):
        while True:
            try:await self.run_cycle()
            except Exception as e:self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task:self.task=asyncio.create_task(self.loop())
