"""Savip reference DEX target selection. Shadow research only."""
from app.core.config import settings
from app.strategy.reference_thresholds import EARLY_LAUNCH

async def savip_dex_targets_72h(limit=25):
    if not settings.database_url:
        return []
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("""WITH c AS (
          SELECT DISTINCT ON(token_id) token_id,created_at,payload_json
          FROM events WHERE event_type='DISCOVERY' AND created_at>=NOW()-interval '15 minutes'
          ORDER BY token_id,created_at DESC
        )
        SELECT d.token_id,o.payload_json->>'chain' chain,
          COALESCE(o.payload_json->'raw'->>'pool_id',d.payload_json->'raw'->>'pool_id') pool_id,o.payload_json
        FROM c d
        JOIN LATERAL (
          SELECT payload_json FROM events e
          WHERE e.token_id=d.token_id AND e.event_type IN ('DISCOVERY','SNAPSHOT')
          ORDER BY e.created_at DESC LIMIT 1
        ) o ON TRUE
        WHERE CASE
            WHEN COALESCE(o.payload_json->'raw'->>'pool_created_at',o.payload_json->>'pool_created_at') IS NOT NULL
            THEN EXTRACT(EPOCH FROM (NOW()-COALESCE(o.payload_json->'raw'->>'pool_created_at',o.payload_json->>'pool_created_at')::timestamptz))/60.0
            ELSE NULLIF(o.payload_json->>'age_minutes','')::double precision
          END BETWEEN %s AND %s
          AND NULLIF(o.payload_json->>'mcap_usd','')::double precision BETWEEN %s AND %s
          AND NULLIF(o.payload_json->>'liquidity_usd','')::double precision >= %s
          AND COALESCE(o.payload_json->'raw'->>'pool_id',d.payload_json->'raw'->>'pool_id') IS NOT NULL
          AND NOT EXISTS(SELECT 1 FROM events x WHERE x.token_id=d.token_id AND x.event_type='SAVIP_DEX' AND x.created_at>=NOW()-interval '15 minutes')
        ORDER BY CASE WHEN EXISTS(SELECT 1 FROM events x WHERE x.token_id=d.token_id AND x.event_type='SAVIP_DEX') THEN 1 ELSE 0 END ASC, d.created_at DESC LIMIT %s""",(EARLY_LAUNCH["min_age_minutes"],EARLY_LAUNCH["max_age_minutes"],EARLY_LAUNCH["min_mcap_usd"],EARLY_LAUNCH["max_mcap_usd"],EARLY_LAUNCH["min_liquidity_usd"],limit))
        return await cur.fetchall()
