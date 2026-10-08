"""Auditable standalone eligibility decisions, not comparative PICK."""
from app.research.savip_single_eligibility import decide_single_eligibility

def build_single_audit(row, scores, model=None, usage=None):
    data=row.get('payload_json') or {}
    result=data.get('result') or {}
    evidence=data.get('evidence')
    if result.get('ok') is not True or result.get('soft_pass') is not True or not isinstance(result.get('judgment'),dict):
        accepted,reason,parsed=False,'unverified_soft_pass',None
    else:
        accepted,reason,parsed=decide_single_eligibility(scores,row.get('token_id'),row.get('token_id'),evidence)
    return {'token_id':row.get('token_id'),'jev_event_id':row.get('id'),'accepted':accepted,'reason':reason,'eligibility':parsed.model_dump(mode='json') if parsed else None,'model':model,'usage':usage,'decision_type':'standalone_eligibility','shadow_only':True}
