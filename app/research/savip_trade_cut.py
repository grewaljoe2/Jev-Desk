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
        th=x.get("trades_m5");bh=x.get("buys_m5");sh=x.get("sells_m5");vol=x.get("volume_m5_usd")
        absent=[k for k,v in (("trades_m5",th),("buys_m5",bh),("sells_m5",sh),("volume_m5_usd",vol)) if v is None]
        if absent:
            kills["missing_trade_fact"]=kills.get("missing_trade_fact",0)+1
            for k in absent:missing[k]=missing.get(k,0)+1
        elif vol<3000 or th<20 or bh<10 or sh<2:
            kills["early_activity"]=kills.get("early_activity",0)+1
        else:
            # DEX trade telemetry must never overwrite FREE CUT gated age, liquidity, volume or market cap.
            # Keep the exact source facts used to admit the token and attach DEX facts separately.
            survivors.append({**row,"dex_trade_facts":x,"momentum_m5":{"buys":x.get("buys_m5"),"sells":x.get("sells_m5"),"trades":x.get("trades_m5"),"volume_usd":x.get("volume_m5_usd"),"price_change_pct":x.get("price_change_m5_pct"),"observation_only":True}})
    return {"survivors":survivors,"kills":kills,"missing_fields":missing}
