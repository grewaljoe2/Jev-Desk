"""Fresh risk observations from the exact DexScreener pair persisted at entry."""
from app.providers.dexscreener import DexScreenerProvider
from app.core.config import settings

class SavipRiskMarketProvider:
    def __init__(self,dex=None):self.dex=dex or DexScreenerProvider()
    async def observe(self,token_id:str):
        if not settings.database_url:return None
        import psycopg
        from psycopg.rows import dict_row
        async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
            cur=await db.execute("""SELECT payload_json FROM events WHERE token_id=%s
              AND event_type IN ('SAVIP_CHAIN','SAVIP_DEX') ORDER BY created_at DESC LIMIT 1""",(token_id,))
            row=await cur.fetchone()
        if not row:return None
        p=row["payload_json"];chain=p.get("chain");pool=p.get("pool_id") or p.get("pair_address")
        if not chain or not pool:return None
        x=await self.dex.fetch_pair(chain,pool)
        if not x or x.get("pair_found") is False:return None
        return {"price_usd":x.get("price_usd"),"volume_6h":x.get("volume_h6_usd"),"volume_24h":x.get("volume_h24_usd"),"source":"dexscreener","pair_address":x.get("pair_address")}
