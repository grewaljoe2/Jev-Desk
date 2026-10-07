import asyncio
from datetime import datetime,timezone
from app.storage.db import active_shadow_targets,mark_shadow_positions,qualification_pressure

class ActiveTradeWorker:
    """High-priority shadow position monitor.

    Uses batched pool reads and actual observed prices. It never invents a stop/TP fill.
    Qualification jobs retain first priority; active positions outrank background outcomes.
    """
    def __init__(self,provider,seconds=15,max_defer_seconds=30):
        self.provider=provider;self.seconds=seconds;self.max_defer_seconds=max_defer_seconds;self.task=None
        self.last_cycle_at=None;self.last_targets=0;self.last_marked=0;self.last_error=None
        self._deferred_since=None
    async def loop(self):
        while True:
            try:
                pressure=await qualification_pressure()
                now=datetime.now(timezone.utc)
                if pressure["due"]:
                    if self._deferred_since is None:self._deferred_since=now
                    deferred=(now-self._deferred_since).total_seconds()
                    if deferred<self.max_defer_seconds:
                        await asyncio.sleep(3);continue
                self._deferred_since=None
                targets=await active_shadow_targets()
                self.last_targets=len(targets);marked=0
                by_chain={}
                for t in targets:
                    if t.get("chain") and t.get("pool_id"):
                        by_chain.setdefault(t["chain"],[]).append(t)
                for chain,items in by_chain.items():
                    for offset in range(0,len(items),30):
                        if (await qualification_pressure())["due"]:break
                        batch=items[offset:offset+30]
                        snaps=await self.provider.fetch_pools(chain,[x["pool_id"] for x in batch])
                        now=datetime.now(timezone.utc)
                        for t in batch:
                            snap=snaps.get(t["pool_id"])
                            if snap and snap.price_usd and snap.price_usd>0:
                                await mark_shadow_positions(t["token_id"],snap.price_usd,now,t["baseline_event_id"])
                                marked+=1
                self.last_marked=marked;self.last_cycle_at=datetime.now(timezone.utc);self.last_error=None
            except Exception as e:
                self.last_error=f"{type(e).__name__}: {str(e)[:180]}"
                print("ACTIVE_TRADE_WORKER_ERROR",self.last_error,flush=True)
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task or self.task.done():self.task=asyncio.create_task(self.loop())
