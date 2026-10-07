from datetime import datetime,timezone
from typing import Any
from pydantic import BaseModel,Field
def utcnow():return datetime.now(timezone.utc)
class TokenSnapshot(BaseModel):
    token_id:str;address:str;chain:str;ticker:str;observed_at:datetime=Field(default_factory=utcnow)
    price_usd:float|None=None;age_minutes:float|None=None;liquidity_usd:float|None=None;volume_h24_usd:float|None=None;mcap_usd:float|None=None
    trades_h24:int|None=None;buys_h1:int|None=None;sells_h1:int|None=None;holders:int|None=None;top_wallet_fraction:float|None=None;top10_fraction:float|None=None;raw:dict[str,Any]=Field(default_factory=dict)
class Decision(BaseModel):
    arm:str;eligible:bool;reason:str;score:float|None=None;proposed_size_usd:float=0.0;metadata:dict[str,Any]=Field(default_factory=dict)
class Event(BaseModel):
    event_type:str;token_id:str|None=None;arm:str|None=None;payload:dict[str,Any]=Field(default_factory=dict);created_at:datetime=Field(default_factory=utcnow)
