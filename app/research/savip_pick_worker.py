"""Savip cross-candidate PICK worker. Shadow only; no order transport."""
import asyncio
from app.storage.db import recent_savip_soft_survivors,log_savip_pick
from app.research.savip_pick import PickResult,single_survivor

class SavipPickWorker:
    def __init__(self,provider,seconds=900):
        self.provider=provider;self.seconds=seconds;self.task=None
        self.state="waiting";self.last_error=None
    async def run_cycle(self):
        rows=await recent_savip_soft_survivors()
        if not rows:self.state="no_survivors";return
        if len(rows)==1:
            p=single_survivor(rows[0]["token_id"]);p["accepted"]=True;p["token_id"]=rows[0]["token_id"]
            await log_savip_pick(p);self.state="single_survivor";return
        if not self.provider.configured:self.state="jev_not_configured";return
        candidates=[{"token_id":r["token_id"],"judgment":r["payload_json"].get("result",{}).get("judgment"),"evidence":r["payload_json"].get("evidence")} for r in rows]
        try:
            raw=await self.provider.pick(candidates)
            parsed=PickResult.model_validate(raw["pick"])
            accepted,reason=parsed.accepted()
            payload={"token_id":parsed.winner.token_id if parsed.winner else None,"accepted":accepted,"reason":reason,"pick":parsed.model_dump(mode="json"),"model":raw.get("model"),"usage":raw.get("usage"),"candidate_count":len(rows)}
            await log_savip_pick(payload);self.state="accepted" if accepted else "no_trade"
        except Exception as e:
            self.state="failed";self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
    async def loop(self):
        while True:
            try:await self.run_cycle()
            except Exception as e:self.state="failed";self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task:self.task=asyncio.create_task(self.loop())
