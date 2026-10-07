"""Typed Jev adapter boundary. Shadow only; no execution."""
from typing import Protocol,Any
from pydantic import ValidationError
from app.research.savip_jev_schema import SavipJudgment,soft_gate

class JevProvider(Protocol):
    async def judge(self,evidence:dict,questions:dict,rules:tuple[str,...])->dict: ...

async def run_typed_jev(provider:JevProvider,evidence,questions,rules):
    if provider is None:return {"ok":False,"reason":"jev_not_configured"}
    try:
        raw=await provider.judge(evidence.model_dump(mode="json"),questions,rules)
        judgment=SavipJudgment.model_validate(raw)
    except ValidationError as e:
        return {"ok":False,"reason":"invalid_typed_judgment","errors":e.errors(include_input=False)}
    except Exception as e:
        return {"ok":False,"reason":"jev_provider_error","error":f"{type(e).__name__}: {str(e)[:160]}"}
    passed,reason=soft_gate(judgment)
    return {"ok":True,"judgment":judgment.model_dump(mode="json"),"soft_pass":passed,"soft_reason":reason}
