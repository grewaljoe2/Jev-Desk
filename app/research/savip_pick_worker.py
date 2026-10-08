"""Savip cross-candidate PICK worker. Shadow only; no order transport."""
import asyncio
import os
from datetime import datetime,timezone
from app.storage.db import savip_single_eligibility_seen,log_savip_single_eligibility,claim_savip_single_eligibility,complete_savip_single_eligibility_claim
from app.research.savip_single_audit import build_single_audit
from app.storage.db import recent_savip_soft_survivors,log_savip_pick,open_savip_positions,savip_pick_fingerprint_seen
from app.research.savip_pick import PickResult

class SavipPickWorker:
    def __init__(self,provider,seconds=30,on_accept=None):
        self.provider=provider;self.seconds=seconds;self.on_accept=on_accept;self.task=None
        self.state="waiting";self.last_error=None
    async def run_cycle(self):
        if await open_savip_positions():
            self.state="position_held";return
        rows=await recent_savip_soft_survivors()
        fp=[r["id"] for r in rows]
        if fp and await savip_pick_fingerprint_seen(fp):
            self.state="already_picked";return
        if not rows:self.state="no_survivors";return
        # PICK compares multiple survivors; never call model or auto-accept one.
        if len(rows)==1:
            await self.run_single(rows[0]);return
        if not self.provider.configured:self.state="jev_not_configured";return
        candidates=[{"token_id":r["token_id"],"judgment":r["payload_json"].get("result",{}).get("judgment"),"evidence":r["payload_json"].get("evidence")} for r in rows]
        try:
            raw=await self.provider.pick(candidates)
            parsed=PickResult.model_validate(raw["pick"])
            accepted,reason=parsed.accepted()
            allowed_ids={r["token_id"] for r in rows}
            if parsed.winner and parsed.winner.token_id not in allowed_ids:
                accepted,reason=False,"winner_not_in_candidates"
            winner_id=parsed.winner.token_id if parsed.winner else None
            winner_row=next((r for r in rows if r["token_id"]==winner_id),None)
            payload={"token_id":winner_id,"accepted":accepted,"reason":reason,"pick":parsed.model_dump(mode="json"),"model":raw.get("model"),"usage":raw.get("usage"),"candidate_count":len(rows),"jev_fingerprint":",".join(str(x) for x in sorted(fp)),"evidence":winner_row["payload_json"].get("evidence") if winner_row else None}
            await log_savip_pick(payload);self.state="accepted" if accepted else "no_trade"
            if accepted and self.on_accept:await self.on_accept()
        except Exception as e:
            self.state="failed";self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
    async def run_single(self,row):
        """Standalone eligibility audit; does not convert a single survivor into a PICK winner."""
        event_id=row.get("id")
        created=row.get("created_at")
        if not isinstance(event_id,int) or event_id<=0 or not isinstance(created,datetime):
            self.state="single_invalid_source";return
        age=(datetime.now(timezone.utc)-created.astimezone(timezone.utc)).total_seconds()
        if age<0 or age>900:
            self.state="single_stale_source";return
        if await savip_single_eligibility_seen(event_id):
            self.state="single_already_judged";return
        payload=row.get("payload_json") or {}
        result=payload.get("result") or {}
        evidence=payload.get("evidence")
        if result.get("ok") is not True or result.get("soft_pass") is not True or not isinstance(result.get("judgment"),dict) or not isinstance(evidence,dict):
            self.state="single_invalid_evidence";return
        if os.getenv("SAVIP_SINGLE_ELIGIBILITY_ENABLED","false").lower() not in ("true","1","yes"):
            self.state="single_eligibility_disabled";return
        if not self.provider.configured:
            self.state="jev_not_configured";return
        if not await claim_savip_single_eligibility(event_id,row["token_id"]):
            self.state="single_already_claimed";return
        try:
            raw=await self.provider.judge_single_eligibility(row["token_id"],result["judgment"],evidence)
            audit=build_single_audit(row,raw["eligibility"],raw.get("model"),raw.get("usage"))
            stored=await log_savip_single_eligibility(audit)
            self.state=("single_eligible_audited" if audit["accepted"] else "single_rejected_audited") if stored else "single_already_judged"
            await complete_savip_single_eligibility_claim(event_id,"audited" if stored else "duplicate")
            # Standalone audit never fabricates a comparative PICK.
        except Exception as e:
            try:await complete_savip_single_eligibility_claim(event_id,"failed")
            except Exception:pass
            self.state="single_failed";self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
    async def loop(self):
        while True:
            try:await self.run_cycle()
            except Exception as e:self.state="failed";self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task:self.task=asyncio.create_task(self.loop())
