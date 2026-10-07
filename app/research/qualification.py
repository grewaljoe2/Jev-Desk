"""Qualification diagnostics distinguish failed facts from unavailable facts."""
from collections import Counter

def qualification_diagnostics(samples:list[dict]):
    out={}
    for arm in ("reference","python_only","jev_python"):
        reasons=Counter();eligible=0;unscorable=0;rejected=0
        for s in samples:
            d=next((x for x in s.get("decisions",[]) if x.get("arm")==arm),None)
            if not d:continue
            if d.get("eligible"):eligible+=1;continue
            reason=str(d.get("reason") or "unknown");reasons[reason]+=1
            if reason.startswith("missing:") or reason=="jev_not_configured_fail_closed":unscorable+=1
            else:rejected+=1
        out[arm]={"eligible":eligible,"unscorable":unscorable,"rejected":rejected,"reasons":dict(reasons)}
    return out
