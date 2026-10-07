"""Aggregate replay results into research metrics. No execution path."""
def summarize_replays(samples:list[dict],winner_cut_pct:float=25.0):
    arms={}
    for s in samples:
        terminal=s.get("terminal_return_pct");mfe=s.get("mfe_pct");mae=s.get("mae_pct")
        for d in s.get("decisions",[]):
            a=arms.setdefault(d["arm"],{"eligible":0,"rejected":0,"returns":[],"mfes":[],"maes":[],"missed_winners":0})
            if d.get("eligible"):
                a["eligible"]+=1
                if terminal is not None:a["returns"].append(terminal)
                if mfe is not None:a["mfes"].append(mfe)
                if mae is not None:a["maes"].append(mae)
            else:
                a["rejected"]+=1
                if mfe is not None and mfe>=winner_cut_pct:a["missed_winners"]+=1
    out={}
    for arm,a in arms.items():
        r=a["returns"];m=a["mfes"];loss=a["maes"];n=len(r)
        wins=sum(x>0 for x in r)
        gross_profit=sum(x for x in r if x>0);gross_loss=-sum(x for x in r if x<0)
        out[arm]={
            "eligible":a["eligible"],"rejected":a["rejected"],"scored":n,
            "win_rate":wins/n if n else None,
            "mean_terminal_return_pct":sum(r)/n if n else None,
            "profit_factor_return_space":gross_profit/gross_loss if gross_loss>0 else None,
            "mean_mfe_pct":sum(m)/len(m) if m else None,
            "mean_mae_pct":sum(loss)/len(loss) if loss else None,
            "missed_winners":a["missed_winners"],
        }
    return out
