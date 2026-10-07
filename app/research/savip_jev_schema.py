"""Typed Savip Jev judgments and deterministic soft gates. No prose parsing."""
from typing import Literal
from pydantic import BaseModel,Field
from app.strategy.reference_thresholds import SOFT,REJECT_SHAPES,REJECT_SELL_SIDE

P=Field(ge=0.0,le=1.0)

class MarketJudgment(BaseModel):
    concentration_is_exit_risk:float=P
    momentum_already_spent:float=P
    liquidity_fits_ticket:float=P
    shape:Literal["healthy","fading","one_buyer","unclear"]
    sell_side_risk:Literal["clean","flagged","suspicious","unclear"]

class ChainJudgment(BaseModel):
    dev_still_loaded:float=P
    sellable_by_evidence:float=P
    crowd_probability:float=P

class SocialJudgment(BaseModel):
    account_is_the_project:float=P
    recycled_account:float=P
    audience_is_real:float=P
    effort:float=Field(ge=0.0)

class SavipJudgment(BaseModel):
    market:MarketJudgment
    chain:ChainJudgment
    social:SocialJudgment|None=None

def soft_gate(j:SavipJudgment):
    d={**j.market.model_dump(),**j.chain.model_dump(),**(j.social.model_dump() if j.social is not None else {})}
    if d["shape"] in REJECT_SHAPES:return False,"shape"
    if d["sell_side_risk"] in REJECT_SELL_SIDE:return False,"sell_side"
    for name,(kind,cut) in SOFT.items():
        if name not in d:continue  # No social judgment without exact-X evidence.
        v=d[name]
        if (kind=="max" and v>cut) or (kind=="min" and v<cut):return False,name
    return True,"pass"
