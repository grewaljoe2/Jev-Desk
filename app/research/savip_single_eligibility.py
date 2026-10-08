"""Independent typed single-survivor eligibility contract (offline; not wired to trading)."""
from pydantic import BaseModel, Field, ConfigDict
from app.strategy.reference_thresholds import PICK

class SingleEligibility(BaseModel):
    model_config = ConfigDict(extra="forbid")
    worth_trading_at_all: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    size_factor: float = Field(ge=0, le=1)

def decide_single_eligibility(raw, expected_token_id, observed_token_id, evidence):
    """Fail closed on invalid identity, missing evidence, or scores below frozen gates."""
    if not expected_token_id or observed_token_id != expected_token_id:
        return False, "identity_mismatch", None
    if not isinstance(evidence, dict) or not isinstance(evidence.get("market"), dict) or not isinstance(evidence.get("chain"), dict):
        return False, "missing_evidence", None
    market=evidence["market"]
    if not isinstance(market.get("proposed_ticket_usd"), (int,float)) or market["proposed_ticket_usd"] <= 0:
        return False, "missing_ticket", None
    if not isinstance(market.get("liquidity_usd"), (int,float)) or market["liquidity_usd"] <= 0:
        return False, "missing_liquidity", None
    try:
        result=SingleEligibility.model_validate(raw)
    except Exception:
        return False, "invalid_judgment", None
    if result.worth_trading_at_all < PICK["worth_trading_at_all"]:
        return False, "worth_trading_at_all", result
    if result.confidence < PICK["winner_confidence"]:
        return False, "confidence", result
    if result.size_factor <= 0:
        return False, "zero_size", result
    return True, "pass", result
