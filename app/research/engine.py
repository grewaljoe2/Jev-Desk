from app.core.models import Event
from app.strategy.arms import evaluate_all
from app.storage.db import log_event,schedule_outcomes
async def process_snapshot(snapshot):
    baseline_event_id=await log_event(Event(event_type="SNAPSHOT",token_id=snapshot.token_id,payload=snapshot.model_dump(mode="json")))
    await schedule_outcomes(snapshot.token_id,snapshot.observed_at,baseline_event_id)
    decisions=evaluate_all(snapshot)
    for d in decisions: await log_event(Event(event_type="DECISION",token_id=snapshot.token_id,arm=d.arm,payload=d.model_dump(mode="json")))
    return decisions
