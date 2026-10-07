"""Replay diagnostics for explaining calibration/holdout behavior."""
from app.research.validation_split import split_samples
from app.research.replay_pipeline import _policy_return

def _summary(samples,policy):
    vals=[_policy_return(s,policy) for s in samples] if policy else []
    vals=[v for v in vals if v is not None]
    if not vals:return {"samples":len(samples),"scored":0,"expectancy_pct":None,"win_rate":None,"profit_factor":None}
    gp=sum(v for v in vals if v>0);gl=-sum(v for v in vals if v<0)
    return {"samples":len(samples),"scored":len(vals),"expectancy_pct":sum(vals)/len(vals),"win_rate":sum(v>0 for v in vals)/len(vals),"profit_factor":gp/gl if gl else None}

def replay_diagnostics(samples,policy):
    calibration,holdout=split_samples(samples)
    chains=sorted({str(s.get("token_id","")).split(":",1)[0] for s in samples})
    by_chain={}
    for chain in chains:
        group=[s for s in samples if str(s.get("token_id","")).startswith(chain+":")]
        ca,ho=split_samples(group)
        by_chain[chain]={"all":_summary(group,policy),"calibration":_summary(ca,policy),"holdout":_summary(ho,policy)}
    eligibility={}
    for arm in ("reference","python_only","jev_python"):
        yes=[];no=[]
        for s in samples:
            d=next((x for x in s.get("decisions",[]) if x.get("arm")==arm),None)
            if d:(yes if d.get("eligible") else no).append(s)
        eligibility[arm]={"eligible":_summary(yes,policy),"rejected":_summary(no,policy)}
    return {"policy":policy,"all":_summary(samples,policy),"calibration":_summary(calibration,policy),"holdout":_summary(holdout,policy),"by_chain":by_chain,"by_eligibility":eligibility}
