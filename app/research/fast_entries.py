import asyncio
from datetime import datetime,timezone
from app.core.models import Event
from app.strategy.filters import fast_fact_filter
from app.storage.db import due_fast_entry_jobs,complete_fast_entry_job,defer_fast_entry_job,open_fast_shadow_position,log_event

class FastEntryWorker:
    """Forward-only age-cohort experiment. 15m control remains untouched."""
    def __init__(self,provider,seconds=5):self.provider=provider;self.seconds=seconds;self.task=None
    async def loop(self):
        while True:
            try:
                jobs=await due_fast_entry_jobs(120)
                by_chain={}
                for j in jobs:by_chain.setdefault(j["chain"],[]).append(j)
                for chain,items in by_chain.items():
                    for offset in range(0,len(items),30):
                        batch=items[offset:offset+30]
                        try:
                            snaps=await self.provider.fetch_pools(chain,[j["pool_id"] for j in batch])
                            now=datetime.now(timezone.utc)
                            for j in batch:
                                snap=snaps.get(j["pool_id"])
                                if not snap:
                                    await defer_fast_entry_job(j["id"],1,"pool_not_available");continue
                                cohort=int(j["cohort_minutes"])
                                raw=dict(snap.raw or {});raw.update({"fast_entry_job_id":j["id"],"fast_cohort_minutes":cohort,"fast_due_at":j["due_at"],"fast_actual_at":now})
                                snap=snap.model_copy(update={"observed_at":now,"raw":raw})
                                event_id=await log_event(Event(event_type="FAST_ENTRY_SNAPSHOT",token_id=snap.token_id,arm=f"fast_{cohort}m",payload=snap.model_dump(mode="json")))
                                ok,reason=fast_fact_filter(snap,float(cohort))
                                await log_event(Event(event_type="FAST_ENTRY_DECISION",token_id=snap.token_id,arm=f"fast_{cohort}m",payload={"eligible":ok,"reason":reason,"cohort_minutes":cohort,"observed_age_minutes":snap.age_minutes,"baseline_event_id":event_id}))
                                if ok:await open_fast_shadow_position(snap,event_id,cohort)
                                await complete_fast_entry_job(j["id"])
                        except Exception as e:
                            for j in batch:await defer_fast_entry_job(j["id"],1,f"{type(e).__name__}: {str(e)[:120]}")
            except Exception as e:print("FAST_ENTRY_WORKER_ERROR",type(e).__name__,str(e)[:180],flush=True)
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task or self.task.done():self.task=asyncio.create_task(self.loop())
