"""Savip reference DEX target selection. Shadow research only."""
from app.core.config import settings
from app.strategy.reference_thresholds import HARD

async def savip_dex_targets_72h(limit=25):
    if not settings.database_url:
        return []
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("""WITH c AS (
          SELECT DISTINCT ON(token_id) token_id,created_at,payload_json
          FROM events WHERE event_type='DISCOVERY' AND created_at>=NOW()-interval '72 hours'
          ORDER BY token_id,created_at DESC
        )
        SELECT token_id,payload_json->>'chain' chain,payload_json->'raw'->>'pool_id' pool_id,payload_json
        FROM c WHERE CASE
            WHEN COALESCE(payload_json->'raw'->>'pool_created_at',payload_json->>'pool_created_at') IS NOT NULL
            THEN EXTRACT(EPOCH FROM (NOW()-COALESCE(payload_json->'raw'->>'pool_created_at',payload_json->>'pool_created_at')::timestamptz))/60.0
            ELSE NULLIF(payload_json->>'age_minutes','')::double precision
          END BETWEEN %s AND %s
          AND NULLIF(payload_json->>'volume_h24_usd','')::double precision >= %s
          AND NULLIF(payload_json->>'mcap_usd','')::double precision BETWEEN %s AND %s
          AND NULLIF(payload_json->>'liquidity_usd','')::double precision >= %s
          AND NOT EXISTS(SELECT 1 FROM events x WHERE x.token_id=c.token_id AND x.event_type='SAVIP_DEX' AND x.created_at>=NOW()-interval '15 minutes')
        ORDER BY created_at DESC LIMIT %s""",(HARD["min_age_minutes"],HARD["max_age_hours"]*60,HARD["min_volume_h24"],HARD["min_mcap_usd"],HARD["max_mcap_usd"],HARD["min_liquidity_usd"],limit))
        return await cur.fetchall()
