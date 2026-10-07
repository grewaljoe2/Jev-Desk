import asyncio
from app.core.models import Event
from app.storage.db import due_outcome_jobs,complete_outcome_job,defer_outcome_job
class OutcomeWorker:
    def __init__(self,provider,seconds=60):self.provider=provider;self.seconds=seconds;self.task=None
    async def loop(self):
        while True:
            try:
                for job in await due_outcome_jobs():
                    try:
                        base=job["payload_json"];chain=base.get("chain");pool_id=(base.get("raw") or {}).get("pool_id")
                        snap=await self.provider.fetch_pool(chain,pool_id)
                        if not snap:await defer_outcome_job(job["id"]);continue
                        payload={"requested_horizon_minutes":job["horizon_minutes"],"due_at":job["due_at"],"observation":snap.model_dump(mode="json")}
                        await complete_outcome_job(job["id"],Event(event_type="OUTCOME",token_id=job["token_id"],payload=payload))
                    except Exception:await defer_outcome_job(job["id"])
            except Exception:pass
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task:self.task=asyncio.create_task(self.loop())
