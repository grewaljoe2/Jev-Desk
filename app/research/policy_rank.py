"""Rank exit-policy shadows without touching the forward collector."""
from app.research.execution_sim import simulate_terminal_trade
from app.research.exit_policies import shadow_fixed_horizons,shadow_take_profit_stop

def _metrics(returns):
    r=[x for x in returns if x is not None]
    if not r:return {"trades":0,"net_expectancy_pct":None,"profit_factor":None,"win_rate":None}
    gp=sum(x for x in r if x>0);gl=-sum(x for x in r if x<0)
    return {"trades":len(r),"net_expectancy_pct":sum(r)/len(r),"profit_factor":gp/gl if gl>0 else None,"win_rate":sum(x>0 for x in r)/len(r)}

def rank_exit_policies(samples:list[dict],horizons=(15,30,60,180,360,720,1440,4320),tp_stop=((25,-15),(50,-25),(100,-30))):
    buckets={f"fixed_{h}m":[] for h in horizons}
    for tp,sl in tp_stop:buckets[f"tp{tp}_sl{abs(sl)}"]=[]
    for s in samples:
        fixed=shadow_fixed_horizons(s,horizons)
        for h in horizons:
            raw=fixed.get(str(h))
            if raw is not None:
                sim=simulate_terminal_trade({"terminal_return_pct":raw})
                buckets[f"fixed_{h}m"].append(sim["net_return_pct"] if sim else None)
        for tp,sl in tp_stop:
            x=shadow_take_profit_stop(s,tp,sl)
            if x:
                sim=simulate_terminal_trade({"terminal_return_pct":x["return_pct"]})
                buckets[f"tp{tp}_sl{abs(sl)}"].append(sim["net_return_pct"] if sim else None)
    ranked=[{"policy":k,**_metrics(v)} for k,v in buckets.items()]
    ranked.sort(key=lambda x:(x["net_expectancy_pct"] is not None,x["net_expectancy_pct"] or float("-inf")),reverse=True)
    return ranked
