from app.core.models import Event
from app.strategy.arms import evaluate_all
from app.storage.db import log_event,schedule_outcomes,open_shadow_position

async def process_snapshot(snapshot):
    baseline_event_id=await log_event(Event(event_type="SNAPSHOT",token_id=snapshot.token_id,payload=snapshot.model_dump(mode="json")))
    decisions=evaluate_all(snapshot)
    for d in decisions:
        await log_event(Event(event_type="DECISION",token_id=snapshot.token_id,arm=d.arm,payload=d.model_dump(mode="json")))
    # Entry-qualified cohorts deserve the full outcome curve. Corrected rejected
    # qualification cohorts remain useful controls, but use a sparse horizon set
    # prospectively so they cannot consume the provider budget needed for entries.
    qualified=any(d.arm=="reference" and d.eligible for d in decisions)
    is_qualification=bool((snapshot.raw or {}).get("qualification_job_id"))
    horizons=None if qualified or not is_qualification else (15,60,360,1440,4320)
    await schedule_outcomes(snapshot.token_id,snapshot.observed_at,baseline_event_id,force=is_qualification,horizons=horizons)
    if is_qualification and qualified:
        await open_shadow_position(snapshot,baseline_event_id)
    return decisions
