"""Read the newest persisted CHAIN-pass dossier for controlled Jev validation."""
from app.core.config import settings

async def latest_chain_pass():
    if not settings.database_url:return None
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("""SELECT id AS chain_event_id,token_id,payload_json,created_at FROM events
          WHERE event_type='SAVIP_CHAIN' AND payload_json->>'chain_pass'='true' AND created_at>=NOW()-interval '20 minutes'
          ORDER BY created_at DESC LIMIT 1""")
        r=await cur.fetchone()
        return dict(r) if r else None

async def unjudged_chain_passes(limit:int=3):
    """Durable unclaimed CHAIN passes, excluding tokens with a newer CHAIN rejection."""
    if not settings.database_url:return []
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("""SELECT e.id AS chain_event_id,e.token_id,e.payload_json,e.created_at FROM events e
          LEFT JOIN savip_jev_claims c ON c.chain_event_id=e.id
          WHERE e.event_type='SAVIP_CHAIN' AND e.payload_json->>'chain_pass'='true' AND e.created_at>=NOW()-interval '72 hours' AND c.chain_event_id IS NULL
            AND NOT EXISTS (SELECT 1 FROM events newer WHERE newer.token_id=e.token_id AND newer.event_type='SAVIP_CHAIN' AND newer.created_at>e.created_at AND newer.payload_json->>'chain_pass'='false')
          ORDER BY e.created_at ASC LIMIT %s""",(limit,))
        return [dict(r) for r in await cur.fetchall()]
