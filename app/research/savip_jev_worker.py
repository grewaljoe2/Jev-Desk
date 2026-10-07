"""Recurring typed Jev judgment worker for genuine CHAIN survivors. Shadow only."""
import asyncio
from app.research.savip_jev_candidate import unjudged_chain_passes
from app.research.savip_jev_evidence import build_evidence
from app.research.savip_jev_adapter import run_typed_jev
from app.research.savip_jev_questions import QUESTION_SETS,RULES
from app.storage.db import claim_savip_jev,complete_savip_jev_claim,log_savip_jev,open_savip_positions

class SavipJevWorker:
    def __init__(self,provider,seconds=900,cap=3,on_pass=None,x_provider=None):
        self.provider=provider;self.seconds=seconds;self.cap=cap;self.on_pass=on_pass;self.x_provider=x_provider;self.task=None
        self.last_checked=0;self.last_passed=0;self.last_error=None
    async def run_cycle(self):
        self.last_checked=0;self.last_passed=0;self.last_error=None
        if await open_savip_positions():return
        if not self.provider.configured:
            self.last_error="jev_not_configured";return
        for row in await unjudged_chain_passes(self.cap):
            if not await claim_savip_jev(row["chain_event_id"],row["token_id"]):continue
            self.last_checked+=1
            payload=row["payload_json"]
            x_observation=None
            x_handle=payload.get("x_handle")
            if x_handle:
                if self.x_provider is None or not getattr(self.x_provider,"configured",False):
                    await complete_savip_jev_claim(row["chain_event_id"],"completed")
                    self.last_error="exact_x_reader_not_configured";continue
                x_observation=await self.x_provider.observe_exact(x_handle)
                # A public-reader outage/unavailable account is missing SOCIAL evidence,
                # not a fabricated pass or hard reject. The entry stage applies Savip's
                # published 0.60 missing-X size factor when x_observation remains absent.
                if x_observation is None:
                    self.last_error="exact_x_observation_unavailable_reduced_size"
            evidence=build_evidence(payload,x_observation=x_observation)
            result=await run_typed_jev(self.provider,evidence,QUESTION_SETS,RULES)
            await log_savip_jev(row["token_id"],result,evidence.model_dump(mode="json"))
            # Do not repeatedly spend paid Jev calls on the same failed dossier.
            status="completed"
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
