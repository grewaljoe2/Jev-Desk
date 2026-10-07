"""Real TypeSafe/Jev provider matching Savip's System One architecture."""
import os
from app.research.savip_jev_questions import QUESTION_SETS,RULES

class TypeSafeJevProvider:
    def __init__(self,model="jev-latest"):
        self.model=model
        self.api_key=os.getenv("TYPESAFE_API_KEY")
    @property
    def configured(self):return bool(self.api_key)
    async def judge(self,evidence:dict,questions:dict|None=None,rules=RULES)->dict:
        if not self.api_key:raise RuntimeError("TYPESAFE_API_KEY_not_configured")
        # SDK is synchronous; isolate the network call from the async desk loop.
        import asyncio
        return await asyncio.to_thread(self._call,evidence,questions or QUESTION_SETS)
    def _call(self,evidence,question_sets):
        from typesafe import TypeSafe
        client=TypeSafe(api_key=self.api_key)
        q=_native_questions(question_sets)
        response=client.system_one(model=self.model,state=evidence,questions=q)
        return _flatten(response)

def _native_questions(question_sets):
    q={}
    for group,items in question_sets.items():
        for name,instruction in items.items():
            if name=="shape":
                q[name]={"type":"choice","instructions":instruction,"criteria":{"healthy":"healthy tradable shape","fading":"fading shape","one_buyer":"one-buyer dominated shape","unclear":"insufficient/ambiguous evidence"}}
            elif name=="sell_side_risk":
                q[name]={"type":"choice","instructions":instruction,"criteria":{"clean":"sell side looks normal","flagged":"sell-side evidence is flagged","suspicious":"sell-side evidence is suspicious","unclear":"insufficient/ambiguous evidence"}}
            elif name=="effort":
                q[name]={"type":"score","instructions":instruction,"criteria":{"0":"no meaningful effort visible","1":"minimum credible effort","2":"clear above-minimum effort","3":"strong sustained effort"}}
            else:
                q[name]={"type":"noul","instructions":instruction}
    return q

def _flatten(response):
    out={}
    for name,v in getattr(response,"nouls",{}).items():out[name]=float(getattr(v,"probability",v))
    for name,v in getattr(response,"choices",{}).items():out[name]=getattr(v,"choice",getattr(v,"value",v))
    for name,v in getattr(response,"scores",{}).items():out[name]=float(getattr(v,"score",getattr(v,"value",v)))
    return {"market":{k:out[k] for k in ("concentration_is_exit_risk","momentum_already_spent","liquidity_fits_ticket","shape","sell_side_risk")},
            "chain":{k:out[k] for k in ("dev_still_loaded","sellable_by_evidence","crowd_probability")},
            "social":{k:out[k] for k in ("account_is_the_project","recycled_account","audience_is_real","effort")}}
