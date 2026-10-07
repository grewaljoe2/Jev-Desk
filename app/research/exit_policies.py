"""Exit-policy shadows over immutable replay paths."""
def _at_or_after(path,minutes,baseline_at):
    target=baseline_at.timestamp()+minutes*60
    for p in path:
        t=p["observed_at"].timestamp() if hasattr(p["observed_at"],"timestamp") else None
        if t is not None and t>=target:return p
    return None

def shadow_fixed_horizons(sample:dict,horizons=(15,30,60,180,360,720,1440,4320)):
    baseline=sample.get("baseline_at");path=sample.get("path") or []
    if baseline is None:return {}
    out={}
    for h in horizons:
        p=_at_or_after(path,h,baseline)
        out[str(h)]=p.get("return_pct") if p else None
    return out

def shadow_take_profit_stop(sample:dict,take_profit_pct=50.0,stop_pct=-25.0):
    """First observed checkpoint crossing wins; sparse observations are explicit."""
    for p in sample.get("path") or []:
        r=p.get("return_pct")
        if r is None:continue
        if r<=stop_pct:return {"return_pct":r,"reason":"stop_observed","observed_at":p["observed_at"]}
        if r>=take_profit_pct:return {"return_pct":r,"reason":"take_profit_observed","observed_at":p["observed_at"]}
    path=sample.get("path") or []
    return {"return_pct":path[-1]["return_pct"],"reason":"terminal_observation","observed_at":path[-1]["observed_at"]} if path else None
