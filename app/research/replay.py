"""Historical replay primitives. Research only; no execution path."""
from dataclasses import dataclass
from datetime import datetime
from app.core.models import TokenSnapshot
from app.strategy.arms import evaluate_all

@dataclass(frozen=True)
class ReplayPoint:
    observed_at: datetime
    price_usd: float | None
    liquidity_usd: float | None = None
    volume_h24_usd: float | None = None
    mcap_usd: float | None = None

def replay_candidate(snapshot: TokenSnapshot, future: list[ReplayPoint]):
    """Evaluate using baseline facts only, then score future path separately.

    This separation is the anti-lookahead boundary: future points are never
    supplied to strategy evaluation.
    """
    decisions=evaluate_all(snapshot)
    valid=[p for p in future if p.observed_at>=snapshot.observed_at]
    returns=[]
    if snapshot.price_usd and snapshot.price_usd>0:
        for p in valid:
            if p.price_usd is not None:
                returns.append({"observed_at":p.observed_at,"return_pct":(p.price_usd/snapshot.price_usd-1.0)*100.0})
    vals=[x["return_pct"] for x in returns]
    return {
        "token_id":snapshot.token_id,
        "baseline_at":snapshot.observed_at,
        "decisions":[d.model_dump(mode="json") for d in decisions],
        "path":returns,
        "mfe_pct":max(vals) if vals else None,
        "mae_pct":min(vals) if vals else None,
        "terminal_return_pct":vals[-1] if vals else None,
    }
