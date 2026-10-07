"""Recurring typed Jev judgment worker for genuine CHAIN survivors. Shadow only."""
import asyncio
from app.research.savip_jev_candidate import unjudged_chain_passes
from app.research.savip_jev_evidence import build_evidence
from app.research.savip_jev_adapter import run_typed_jev
from app.research.savip_jev_questions import QUESTION_SETS,RULES
from app.storage.db import claim_savip_jev,complete_savip_jev_claim,log_savip_jev,open_savip_positions

class SavipJevWorker:
    def __init__(self,provider,seconds=900,cap=3,on_pass=None):
        self.provider=provider;self.seconds=seconds;self.cap=cap;self.on_pass=on_pass;self.task=None
        self.last_checked=0;self.last_passed=0;self.last_error=None
    async def run_cycle(self):
        self.last_checked=0;self.last_passed=0;self.last_error=None
        if await open_savip_positions():return
        if not self.provider.configured:return
        for row in await unjudged_chain_passes(self.cap):
            if not await claim_savip_jev(row["chain_event_id"],row["token_id"]):continue
            self.last_checked+=1
            evidence=build_evidence(row["payload_json"])
            result=await run_typed_jev(self.provider,evidence,QUESTION_SETS,RULES)
            await log_savip_jev(row["token_id"],result,evidence.model_dump(mode="json"))
            status="completed" if result.get("ok") else "failed"
            await complete_savip_jev_claim(row["chain_event_id"],status)
            if result.get("ok") and result.get("soft_pass"):
                self.last_passed+=1
                if self.on_pass:await self.on_pass()
            elif not result.get("ok"):self.last_error=result.get("reason","jev_provider_error")
    async def loop(self):
        while True:
            try:await self.run_cycle()
            except Exception as e:self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task:self.task=asyncio.create_task(self.loop())
