import asyncio
from app.research.engine import process_snapshot

class ShadowScheduler:
    def __init__(self,provider,seconds=900):
        self.provider=provider;self.seconds=seconds;self.task=None
    async def loop(self):
        while True:
            started=asyncio.get_running_loop().time()
            try:
                for snapshot in await self.provider.discover():
                    await process_snapshot(snapshot)
            finally:
                elapsed=asyncio.get_running_loop().time()-started
                await asyncio.sleep(max(1,self.seconds-elapsed))
    def start(self):
        if not self.task:self.task=asyncio.create_task(self.loop())
