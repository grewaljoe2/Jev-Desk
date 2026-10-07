"""One-shot replay research pipeline with sealed holdout evaluation."""
from app.research.validation_split import split_samples
from app.research.policy_rank import rank_exit_policies

def _policy_return(sample,policy):
    from app.research.exit_policies import shadow_fixed_horizons,shadow_take_profit_stop
    from app.research.execution_sim import simulate_terminal_trade
    if policy.startswith("fixed_"):
        h=int(policy.split("_")[1][:-1]);raw=shadow_fixed_horizons(sample,(h,)).get(str(h))
    else:
        a,b=policy.split("_");tp=float(a[2:]);sl=-float(b[2:]);x=shadow_take_profit_stop(sample,tp,sl);raw=x["return_pct"] if x else None
    sim=simulate_terminal_trade({"terminal_return_pct":raw}) if raw is not None else None
    return sim["net_return_pct"] if sim else None

def run_replay_research(samples:list[dict]):
    calibration,holdout=split_samples(samples)
    leaderboard=rank_exit_policies(calibration)
    winner=leaderboard[0] if leaderboard and leaderboard[0]["trades"] else None
    holdout_metrics=None
    if winner:
        vals=[_policy_return(s,winner["policy"]) for s in holdout]
        vals=[v for v in vals if v is not None]
        if vals:
            gp=sum(v for v in vals if v>0);gl=-sum(v for v in vals if v<0)
            holdout_metrics={"policy":winner["policy"],"trades":len(vals),"net_expectancy_pct":sum(vals)/len(vals),"win_rate":sum(v>0 for v in vals)/len(vals),"profit_factor":gp/gl if gl else None}
    return {"calibration_count":len(calibration),"holdout_count":len(holdout),"calibration_leaderboard":leaderboard,"frozen_policy":winner["policy"] if winner else None,"holdout":holdout_metrics}
