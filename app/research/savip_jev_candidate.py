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
