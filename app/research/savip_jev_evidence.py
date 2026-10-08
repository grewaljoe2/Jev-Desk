"""Evidence packets for Savip typed Jev judgments. Shadow only."""
from pydantic import BaseModel
from typing import Any
from app.providers.savip_social import exact_x_observation
from app.research.savip_shadow_execution import ticket_usd

class MarketEvidence(BaseModel):
    proposed_ticket_usd:float|None=None
    price_usd:float|None=None;liquidity_usd:float|None=None;volume_h24_usd:float|None=None
    trades_h24:int|None=None;buys_h1:int|None=None;sells_h1:int|None=None
    age_minutes:float|None=None;mcap_usd:float|None=None

class ChainEvidence(BaseModel):
    chain:str;holder_count:int|None=None;top_wallet_percent:float|None=None;top_10_percent:float|None=None
    developer_holding_percentage:float|None=None;gt_score_details:Any=None
    is_honeypot:bool|None=None;mint_authority:Any=None;freeze_authority:Any=None

class SocialEvidence(BaseModel):
    x_handle:str|None=None
    description:str|None=None
    x_observation:dict[str,Any]|None=None

class JevEvidence(BaseModel):
    token_id:str;ticker:str|None=None
    market:MarketEvidence;chain:ChainEvidence;social:SocialEvidence

def build_evidence(d:dict,x_observation:dict|None=None)->JevEvidence:
    # SOCIAL may only use the exact handle supplied by the chain dossier.
    handle=d.get("x_handle")
    xo=exact_x_observation(handle,x_observation)
    return JevEvidence(
      token_id=d["token_id"],ticker=d.get("ticker"),
      market=MarketEvidence(**{**{k:d.get(k) for k in MarketEvidence.model_fields if k!='proposed_ticket_usd'},'proposed_ticket_usd':ticket_usd(1000.0,float(d['liquidity_usd']),1.0,missing_x=xo is None) if d.get('liquidity_usd') is not None and float(d['liquidity_usd'])>0 else None}),
      chain=ChainEvidence(**{k:d.get(k) for k in ChainEvidence.model_fields}),
      social=SocialEvidence(x_handle=handle,description=d.get("description"),x_observation=xo),
    )
