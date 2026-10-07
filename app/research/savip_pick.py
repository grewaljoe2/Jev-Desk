"""Deterministic Savip PICK contract. Shadow only."""
from pydantic import BaseModel,Field
from app.strategy.reference_thresholds import PICK
class PickCandidate(BaseModel):
    token_id:str
    worth_trading_at_all:float=Field(ge=0.0,le=1.0)
    winner_confidence:float=Field(ge=0.0,le=1.0)
    size_factor:float=Field(ge=0.0,le=1.0)
class PickResult(BaseModel):
    winner:PickCandidate|None=None
    def accepted(self):
        if not self.winner:return False,"no_winner"
        if self.winner.worth_trading_at_all<PICK["worth_trading_at_all"]:return False,"worth_trading_at_all"
        if self.winner.winner_confidence<PICK["winner_confidence"]:return False,"winner_confidence"
        return True,"pass"
def single_survivor(token_id:str):
    return {"token_id":token_id,"pick_skipped":True,"reason":"single_survivor"}
