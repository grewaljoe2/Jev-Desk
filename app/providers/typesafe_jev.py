"""TypeSafe/Jev System One provider. Raw documented HTTP contract; shadow only."""
import os,httpx
from app.research.savip_jev_questions import QUESTION_SETS

class TypeSafeJevProvider:
    URL="https://api.typesafe.ai/v1/systemone"
    def __init__(self,model="jev-latest"):
        self.model=model;self.api_key=os.getenv("TYPESAFE_API_KEY")
    @property
    def configured(self):return bool(self.api_key)
    async def judge(self,evidence:dict,questions:dict|None=None,rules=())->dict:
        if not self.api_key:raise RuntimeError("TYPESAFE_API_KEY_not_configured")
        body={"model":self.model,"state":evidence,"questions":_native_questions(questions or QUESTION_SETS)}
        async with httpx.AsyncClient(timeout=20) as client:
            r=await client.post(self.URL,headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json"},json=body)
        if r.status_code in (401,403):raise RuntimeError("typesafe_auth_failed")
        if r.status_code==429:raise RuntimeError("typesafe_rate_limited")
        if r.status_code==529:raise RuntimeError("typesafe_overloaded")
        if r.status_code>=400:raise RuntimeError(f"typesafe_http_{r.status_code}")
        return _flatten(r.json())

def _native_questions(groups):
    q={}
    for _,items in groups.items():
        for name,instruction in items.items():
            if name=="shape":q[name]={"type":"choice","instructions":instruction,"criteria":{"healthy":"healthy tradable shape","fading":"fading shape","one_buyer":"one-buyer dominated shape","unclear":"insufficient or ambiguous evidence"}}
            elif name=="sell_side_risk":q[name]={"type":"choice","instructions":instruction,"criteria":{"clean":"normal sell-side evidence","flagged":"sell-side evidence is flagged","suspicious":"sell-side evidence is suspicious","unclear":"insufficient or ambiguous evidence"}}
            elif name=="effort":q[name]={"type":"score","instructions":instruction,"criteria":["no meaningful effort visible","minimum credible effort","clear above-minimum effort","strong sustained effort"]}
            else:q[name]={"type":"noul","instructions":instruction}
    return q

def _flatten(data):
    answers=data.get("answers") or {}
    def val(name,kind):
        a=answers.get(name) or {}
        if kind=="noul":return float(a["noul"])
        if kind=="choice":return a["choice"]
        return float(a["score"])
    judgment={
      "market":{"concentration_is_exit_risk":val("concentration_is_exit_risk","noul"),"momentum_already_spent":val("momentum_already_spent","noul"),"liquidity_fits_ticket":val("liquidity_fits_ticket","noul"),"shape":val("shape","choice"),"sell_side_risk":val("sell_side_risk","choice")},
      "chain":{"dev_still_loaded":val("dev_still_loaded","noul"),"sellable_by_evidence":val("sellable_by_evidence","noul"),"crowd_probability":val("crowd_probability","noul")},
      "social":{"account_is_the_project":val("account_is_the_project","noul"),"recycled_account":val("recycled_account","noul"),"audience_is_real":val("audience_is_real","noul"),"effort":val("effort","score")}}
    return {"judgment":judgment,"model":data.get("model"),"usage":data.get("usage")}
