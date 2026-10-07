"""Build replay samples from stored clean forward evidence.

This is intentionally separate from the live worker. It reads immutable
SNAPSHOT/OUTCOME events and never calls a market provider or execution code.
"""
from datetime import datetime
from app.core.models import TokenSnapshot
from app.research.replay import ReplayPoint,replay_candidate

def _dt(v):
    if isinstance(v,datetime):return v
    return datetime.fromisoformat(str(v).replace("Z","+00:00"))

def sample_from_events(snapshot_payload:dict,outcome_payloads:list[dict]):
    baseline=TokenSnapshot.model_validate(snapshot_payload)
    points=[]
    for o in outcome_payloads:
        obs=o.get("observation") or {}
        when=o.get("observed_at")
        if not when:continue
        points.append(ReplayPoint(
            observed_at=_dt(when),
            price_usd=obs.get("price_usd"),
            liquidity_usd=obs.get("liquidity_usd"),
            volume_h24_usd=obs.get("volume_h24_usd"),
            mcap_usd=obs.get("mcap_usd"),
        ))
    points.sort(key=lambda p:p.observed_at)
    result=replay_candidate(baseline,points)
    result["evidence"]="forward_clean"
    result["outcome_points"]=len(points)
    return result


async def load_clean_replay_samples(limit=500):
    from app.storage.db import clean_replay_rows
    rows=await clean_replay_rows(limit)
    samples=[]
    for row in rows:
        outcomes=row.get("outcomes") or []
        if outcomes:
            samples.append(sample_from_events(row["snapshot_payload"],outcomes))
    return samples
