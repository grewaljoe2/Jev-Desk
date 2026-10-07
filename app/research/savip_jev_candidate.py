"""Read the newest persisted CHAIN-pass dossier for controlled Jev validation."""
from app.core.config import settings

async def latest_chain_pass():
    if not settings.database_url:return None
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("""SELECT id AS chain_event_id,token_id,payload_json,created_at FROM events
          WHERE event_type='SAVIP_CHAIN' AND payload_json->>'chain_pass'='true'
          ORDER BY created_at DESC LIMIT 1""")
        r=await cur.fetchone()
        return dict(r) if r else None

async def unjudged_chain_passes(limit:int=3):
    """Newest genuine CHAIN survivors not yet claimed for Jev, bounded per cycle."""
    if not settings.database_url:return []
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("""SELECT e.id AS chain_event_id,e.token_id,e.payload_json,e.created_at FROM events e
          LEFT JOIN savip_jev_claims c ON c.chain_event_id=e.id
          WHERE e.event_type='SAVIP_CHAIN' AND e.payload_json->>'chain_pass'='true' AND (c.chain_event_id IS NULL OR c.status='failed')
          ORDER BY e.created_at ASC LIMIT %s""",(limit,))
        return [dict(r) for r in await cur.fetchall()]
