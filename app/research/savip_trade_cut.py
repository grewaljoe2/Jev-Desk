"""Exact published Savip TRADE CUT evaluation. Shadow only."""
from app.core.config import settings
from app.strategy.reference_thresholds import HARD

async def exact_trade_cut(free_survivors):
    if not free_survivors or not settings.database_url:
        return {"survivors":[],"kills":{},"missing_fields":{}}
    import psycopg
    from psycopg.rows import dict_row
    ids=[r.get("token_id") for r in free_survivors if r.get("token_id")]
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("""SELECT DISTINCT ON(token_id) token_id,payload_json
          FROM events WHERE event_type='SAVIP_DEX' AND token_id=ANY(%s)
          ORDER BY token_id,created_at DESC""",(ids,))
        facts={r["token_id"]:r["payload_json"] for r in await cur.fetchall()}
    survivors=[];kills={};missing={}
    for row in free_survivors:
        x=facts.get(row.get("token_id"))
        if x is None:
            kills["missing_trade_fact"]=kills.get("missing_trade_fact",0)+1
            missing["dex_observation"]=missing.get("dex_observation",0)+1
            continue
        if x.get("pair_found") is False:
            kills["no_pair"]=kills.get("no_pair",0)+1
            continue
        th=x.get("trades_h24");bh=x.get("buys_h1");sh=x.get("sells_h1")
        absent=[k for k,v in (("trades_h24",th),("buys_h1",bh),("sells_h1",sh)) if v is None]
        if absent:
            kills["missing_trade_fact"]=kills.get("missing_trade_fact",0)+1
            for k in absent:missing[k]=missing.get(k,0)+1
        elif th<HARD["min_trades_h24"]:
            kills["trades"]=kills.get("trades",0)+1
        elif sh==0 and bh>20:
            kills["no_sells"]=kills.get("no_sells",0)+1
        else:
            survivors.append({**row,**x})
    return {"survivors":survivors,"kills":kills,"missing_fields":missing}
