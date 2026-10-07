import asyncio
from datetime import datetime,timezone,timedelta
from app.research.engine import process_snapshot
from app.storage.db import due_qualification_jobs,complete_qualification_job,defer_qualification_job

class QualificationWorker:
    """Entry-critical worker. Due qualification checks run independently of outcome backlog."""
    def __init__(self,provider,seconds=10):self.provider=provider;self.seconds=seconds;self.task=None
    async def loop(self):
        while True:
            try:
                for job in await due_qualification_jobs(limit=8):
                    try:
                        snap=await self.provider.fetch_pool(job["chain"],job["pool_id"])
                        if not snap:
                            await defer_qualification_job(job["id"],2,"pool_not_available");continue
                        # Never pretend an early observation is the >=15m entry snapshot.
                        if snap.age_minutes is None:
                            await defer_qualification_job(job["id"],2,"age_unavailable");continue
                        if snap.age_minutes < 15:
                            wait=max(1,int(15-snap.age_minutes)+1)
                            await defer_qualification_job(job["id"],wait,"waiting_for_min_age");continue
                        snap.raw["qualification_job_id"]=job["id"]
                        snap.raw["qualification_due_at"]=job["due_at"].isoformat() if hasattr(job["due_at"],"isoformat") else str(job["due_at"])
                        snap.raw["qualification_actual_at"]=datetime.now(timezone.utc).isoformat()
                        snap.raw["qualification_lateness_seconds"]=max(0.0,(datetime.now(timezone.utc)-job["due_at"]).total_seconds())
                        await process_snapshot(snap)
                        await complete_qualification_job(job["id"])
                    except Exception as e:
                        msg=str(e)[:300]
                        print("QUALIFICATION_RETRY",job["id"],job["token_id"],type(e).__name__,msg,flush=True)
                        await defer_qualification_job(job["id"],2 if "429" not in msg else 1,msg)
                        if "429" in msg:break
            except Exception as e:print("QUALIFICATION_WORKER_ERROR",type(e).__name__,str(e)[:300],flush=True)
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task or self.task.done():self.task=asyncio.create_task(self.loop())
