from datetime import datetime,timezone,timedelta
from app.research.policy_rank import rank_exit_policies

def _sample(vals):
    t=datetime(2026,1,1,tzinfo=timezone.utc)
    return {"baseline_at":t,"path":[{"observed_at":t+timedelta(minutes=m),"return_pct":r} for m,r in vals]}

def test_policy_rank_uses_net_returns():
    samples=[_sample([(15,10),(30,20),(60,30)]),_sample([(15,-5),(30,-10),(60,-20)])]
    ranked=rank_exit_policies(samples,horizons=(15,30,60),tp_stop=())
    assert len(ranked)==3
    assert all("net_expectancy_pct" in x and "profit_factor" in x for x in ranked)
    assert {x["policy"] for x in ranked}=={"fixed_15m","fixed_30m","fixed_60m"}
