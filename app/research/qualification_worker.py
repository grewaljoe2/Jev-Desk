import asyncio
from datetime import datetime,timezone,timedelta
from app.core.models import Event
from app.storage.db import log_event
from app.storage.db import due_qualification_jobs,complete_qualification_job,defer_qualification_job

class QualificationWorker:
    """Entry-critical worker. Batch due checks by network to protect the 5m observation window."""
    def __init__(self,provider,seconds=5):self.provider=provider;self.seconds=seconds;self.task=None
    async def _handle(self,job,snap):
        if not snap:
            await defer_qualification_job(job["id"],2,"pool_not_available");return
        if snap.age_minutes is None:
            await defer_qualification_job(job["id"],2,"age_unavailable");return
        if snap.age_minutes < 5:
            wait=max(1,int(5-snap.age_minutes)+1);await defer_qualification_job(job["id"],wait,"waiting_for_min_age");return
        # Freeze the entry observation time after the >=5m guard. Provider construction time
        # can precede lock/pacing waits; qualification evidence must use the actual check time.
        snap.observed_at=datetime.now(timezone.utc)
        created=(snap.raw or {}).get("pool_created_at")
        if created:
            try:
                born=datetime.fromisoformat(str(created).replace("Z","+00:00"))
                snap.age_minutes=max(0.0,(snap.observed_at-born).total_seconds()/60.0)
            except Exception:pass
        if snap.age_minutes is None or snap.age_minutes < 15:
            await defer_qualification_job(job["id"],1,"post_fetch_age_invariant");return
        now=datetime.now(timezone.utc)
        snap.raw["qualification_job_id"]=job["id"]
        snap.raw["qualification_due_at"]=job["due_at"].isoformat() if hasattr(job["due_at"],"isoformat") else str(job["due_at"])
        snap.raw["qualification_actual_at"]=now.isoformat()
        snap.raw["qualification_lateness_seconds"]=max(0.0,(now-job["due_at"]).total_seconds())
        # Savip-exclusive mode: retain 5m SNAPSHOT evidence, but do not
        # generate legacy decisions, shadow entries, or outcome schedules.
        await log_event(Event(event_type="SNAPSHOT",token_id=snap.token_id,payload=snap.model_dump(mode="json")))
        await complete_qualification_job(job["id"])
    async def loop(self):
        while True:
            try:
                jobs=await due_qualification_jobs(limit=30)
                self.provider.set_entry_pressure(bool(jobs))
                groups={}
                for job in jobs:groups.setdefault(job["chain"],[]).append(job)
                for chain,chain_jobs in groups.items():
                    for offset in range(0,len(chain_jobs),30):
                        batch=chain_jobs[offset:offset+30]
                        try:
                            snaps=await self.provider.fetch_pools(chain,[j["pool_id"] for j in batch])
                            for job in batch:await self._handle(job,snaps.get(job["pool_id"]))
                        except Exception as e:
                            msg=str(e)[:300];print("QUALIFICATION_BATCH_RETRY",chain,type(e).__name__,msg,flush=True)
                            for job in batch:await defer_qualification_job(job["id"],1 if "429" in msg else 2,msg)
                            if "429" in msg:break
            except Exception as e:print("QUALIFICATION_WORKER_ERROR",type(e).__name__,str(e)[:300],flush=True)
            finally:self.provider.set_entry_pressure(False)
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task or self.task.done():self.task=asyncio.create_task(self.loop())
