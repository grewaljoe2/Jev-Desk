"""Internal one-shot TypeSafe/Jev contract validation. Shadow only."""
import asyncio
from app.research.savip_jev_candidate import latest_chain_pass
from app.research.savip_jev_evidence import build_evidence
from app.research.savip_jev_adapter import run_typed_jev
from app.research.savip_jev_questions import QUESTION_SETS,RULES
from app.storage.db import claim_first_savip_jev_validation,complete_first_savip_jev_validation,log_savip_jev

class SavipJevValidationWorker:
    def __init__(self,provider,seconds=60):
        self.provider=provider;self.seconds=seconds;self.task=None
        self.state="waiting";self.token_id=None;self.last_error=None
    async def run_cycle(self):
        if self.state in ("completed","failed","already_claimed"):return
        if not self.provider.configured:self.state="jev_not_configured";return
        row=await latest_chain_pass()
        if not row:self.state="waiting_for_chain_survivor";return
        claimed=await claim_first_savip_jev_validation(row["chain_event_id"],row["token_id"])
        if not claimed:self.state="already_claimed";return
        self.token_id=row["token_id"];self.state="validating"
        evidence=build_evidence(row["payload_json"])
        result=await run_typed_jev(self.provider,evidence,QUESTION_SETS,RULES)
        await log_savip_jev(row["token_id"],result,evidence.model_dump(mode="json"))
        self.state="completed" if result.get("ok") else "failed"
        if not result.get("ok"):self.last_error=result.get("reason","jev_validation_failed")
        await complete_first_savip_jev_validation(self.state)
    async def loop(self):
        while True:
            try:await self.run_cycle()
            except Exception as e:
                self.state="failed";self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task:self.task=asyncio.create_task(self.loop())
