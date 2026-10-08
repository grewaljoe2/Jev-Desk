"""Persistent Savip shadow BOOK helpers. No real execution."""
from app.core.config import settings

async def open_book_position(token_id:str,ticket_usd:float,entry_price:float,fill:dict,provenance:str="savip_shadow"):
    if not settings.database_url:return None
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        await db.execute("SELECT pg_advisory_xact_lock(734101, 1)")
        held=await db.execute("SELECT 1 FROM virtual_positions WHERE arm='savip_reference' AND status='open' LIMIT 1")
        if await held.fetchone():
            await db.commit()
            return None
        cur=await db.execute("""INSERT INTO virtual_positions(token_id,arm,status,requested_size_usd,filled_size_usd,entry_price,opened_at,provenance)
          VALUES(%s,'savip_reference','open',%s,%s,%s,NOW(),%s)
          ON CONFLICT (token_id,arm) WHERE status='open' DO NOTHING RETURNING id""",
          (token_id,ticket_usd,fill.get("net_asset_usd",0.0),entry_price,provenance))
        row=await cur.fetchone();await db.commit();return row[0] if row else None

async def close_book_position(position_id:int,exit_price:float):
    if not settings.database_url:return False
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        cur=await db.execute("UPDATE virtual_positions SET status='closed',closed_at=NOW(),exit_price=%s WHERE id=%s AND status='open'",(exit_price,position_id))
        await db.commit();return cur.rowcount==1
