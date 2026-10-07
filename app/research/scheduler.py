import asyncio
from datetime import datetime,timezone,timedelta
from app.core.models import Event
from app.storage.db import log_event,schedule_qualification

async def ingest_discovery(snapshot):
    """Record discovery evidence and schedule, but never evaluate before >=15m."""
    await log_event(Event(event_type="DISCOVERY",token_id=snapshot.token_id,payload=snapshot.model_dump(mode="json")))
    pool_id=(snapshot.raw or {}).get("pool_id")
    scheduled=False
    if snapshot.age_minutes is not None and pool_id:
        remaining=max(0.0,15.0-snapshot.age_minutes)
        await schedule_qualification(snapshot.token_id,snapshot.chain,pool_id,datetime.now(timezone.utc)+timedelta(minutes=remaining))
        scheduled=True
    return {"token_id":snapshot.token_id,"age_minutes":snapshot.age_minutes,"scheduled":scheduled}

class ShadowScheduler:
    def __init__(self,provider,seconds=900):
        self.provider=provider;self.seconds=seconds;self.task=None
    async def loop(self):
        while True:
            started=asyncio.get_running_loop().time()
            try:
                for snapshot in await self.provider.discover():
                    await ingest_discovery(snapshot)
            finally:
                elapsed=asyncio.get_running_loop().time()-started
                await asyncio.sleep(max(1,self.seconds-elapsed))
    def start(self):
        if not self.task:self.task=asyncio.create_task(self.loop())
