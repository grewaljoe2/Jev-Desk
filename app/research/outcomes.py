import asyncio
from datetime import datetime,timezone
from app.core.models import Event
from app.storage.db import due_outcome_group,complete_outcome_job,defer_outcome_job
class OutcomeWorker:
    def __init__(self,provider,seconds=60):self.provider=provider;self.seconds=seconds;self.task=None
    async def loop(self):
        while True:
            try:
                for group in await due_outcome_group(limit=4):
                    job=group[0]
                    try:
                        base=job["payload_json"];chain=base.get("chain");pool_id=(base.get("raw") or {}).get("pool_id")
                        snap=await self.provider.fetch_pool(chain,pool_id)
                        if not snap:
                            for due_job in group:await defer_outcome_job(due_job["id"],error="pool_not_available")
                            continue
                        now=datetime.now(timezone.utc);baseline=base.get("observed_at")
                        actual=None
                        if baseline:
                            actual=(now-datetime.fromisoformat(str(baseline).replace("Z","+00:00"))).total_seconds()/60
                        for due_job in group:
                            due_base=due_job["payload_json"];due_baseline=due_base.get("observed_at");due_actual=None
                            if due_baseline:due_actual=(now-datetime.fromisoformat(str(due_baseline).replace("Z","+00:00"))).total_seconds()/60
                            payload={"requested_horizon_minutes":due_job["horizon_minutes"],"actual_elapsed_minutes":due_actual,"scheduled_due_at":due_job["due_at"],"baseline_event_id":due_job["baseline_event_id"],"observed_at":now,"observation":snap.model_dump(mode="json")}
                            await complete_outcome_job(due_job["id"],Event(event_type="OUTCOME",token_id=due_job["token_id"],payload=payload))
                        await asyncio.sleep(3)
                    except Exception as e:
                        msg=str(e)[:300]
                        print("OUTCOME_RETRY",job["id"],job["token_id"],type(e).__name__,msg,flush=True)
                        for due_job in group:await defer_outcome_job(due_job["id"],minutes=15 if "429" in msg else 5,error=msg)
                        if "429" in msg:
                            await asyncio.sleep(60)
                            break
            except Exception as e:
                print("OUTCOME_WORKER_ERROR",type(e).__name__,str(e)[:300],flush=True)
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task or self.task.done():self.task=asyncio.create_task(self.loop())
