import asyncio
from datetime import datetime,timezone
from app.core.models import Event
from app.storage.db import due_outcome_group,complete_outcome_job,defer_outcome_job,qualification_pressure,fast_entry_pressure,expire_stale_outcome_jobs,mark_shadow_positions,active_shadow_targets
class OutcomeWorker:
    def __init__(self,provider,seconds=15):self.provider=provider;self.seconds=seconds;self.task=None
    async def loop(self):
        while True:
            try:
                # Historical research is spare-capacity work. Never let it outrank
                # fresh 1/3/5/10m or 15m entry observations.
                if (await qualification_pressure())["due_soon"] or (await fast_entry_pressure())["due_soon"]:
                    await asyncio.sleep(5);continue
                await expire_stale_outcome_jobs()
                # Open forward positions outrank background replay/outcome traffic.
                if await active_shadow_targets():
                    await asyncio.sleep(5);continue
                groups=await due_outcome_group(limit=120)
                by_chain={}
                for group in groups:
                    base=group[0]["payload_json"];chain=base.get("chain");pool_id=(base.get("raw") or {}).get("pool_id")
                    if chain and pool_id:by_chain.setdefault(chain,[]).append((pool_id,group))
                stop=False
                for chain,items in by_chain.items():
                    for offset in range(0,len(items),30):
                        if (await qualification_pressure())["due_soon"] or (await fast_entry_pressure())["due_soon"]:stop=True;break
                        batch=items[offset:offset+30]
                        try:
                            snaps=await self.provider.fetch_pools(chain,[p for p,_ in batch])
                            now=datetime.now(timezone.utc)
                            for pool_id,group in batch:
                                snap=snaps.get(pool_id)
                                if not snap:
                                    for job in group:await defer_outcome_job(job["id"],minutes=15,error="pool_not_available")
                                    continue
                                await mark_shadow_positions(group[0]["token_id"],snap.price_usd,now,group[0].get("baseline_event_id"))
                                for job in group:
                                    base=job["payload_json"];baseline=base.get("observed_at");actual=None
                                    if baseline:actual=(now-datetime.fromisoformat(str(baseline).replace("Z","+00:00"))).total_seconds()/60
                                    payload={"requested_horizon_minutes":job["horizon_minutes"],"actual_elapsed_minutes":actual,"scheduled_due_at":job["due_at"],"baseline_event_id":job["baseline_event_id"],"observed_at":now,"observation":snap.model_dump(mode="json")}
                                    await complete_outcome_job(job["id"],Event(event_type="OUTCOME",token_id=job["token_id"],payload=payload))
                        except Exception as e:
                            msg=str(e)[:300];print("OUTCOME_BATCH_RETRY",chain,type(e).__name__,msg,flush=True)
                            for _,group in batch:
                                for job in group:await defer_outcome_job(job["id"],minutes=1 if "429" in msg else 5,error=msg)
                            if "429" in msg:stop=True;break
                    if stop:break
            except Exception as e:print("OUTCOME_WORKER_ERROR",type(e).__name__,str(e)[:300],flush=True)
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task or self.task.done():self.task=asyncio.create_task(self.loop())
