"""Read-only multi-pool coverage accounting; never aggregates executable liquidity."""
from collections import defaultdict

def summarize_pool_coverage(observations):
    by_token=defaultdict(list)
    by_dex=defaultdict(lambda: {"pools":0,"newly_admitted":0})
    for row in observations:
        token=row.get("token_id")
        pool=row.get("pool_id")
        if not token or not pool:
            continue
        dex=row.get("dex_id") or "unknown"
        by_token[token].append(row)
        by_dex[dex]["pools"]+=1
        by_dex[dex]["newly_admitted"]+=bool(row.get("newly_admitted"))
    tokens=[]
    for token, rows in sorted(by_token.items()):
        distinct={r["pool_id"]:r for r in rows}
        ranked=sorted(distinct.values(),key=lambda r: (-(r.get("liquidity_usd") or 0),r["pool_id"]))
        tokens.append({"token_id":token,"pool_count":len(ranked),
                       "dex_ids":sorted({r.get("dex_id") or "unknown" for r in ranked}),
                       "best_observed_pool_id":ranked[0]["pool_id"],
                       "best_observed_liquidity_usd":ranked[0].get("liquidity_usd"),
                       "any_experiment_eligible":any(r.get("experiment_eligible") for r in ranked),
                       "any_newly_admitted":any(r.get("newly_admitted") for r in ranked)})
    return {"observed_pools":sum(len({r["pool_id"] for r in rows}) for rows in by_token.values()),
            "unique_tokens":len(tokens),"dex_counts":dict(by_dex),"tokens":tokens}
