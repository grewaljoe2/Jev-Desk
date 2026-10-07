import json,aiosqlite
from app.core.models import Event
from app.core.config import settings

PG_SCHEMA="""
CREATE TABLE IF NOT EXISTS events(id BIGSERIAL PRIMARY KEY,created_at TIMESTAMPTZ NOT NULL,event_type TEXT NOT NULL,token_id TEXT,arm TEXT,payload_json JSONB NOT NULL);
CREATE INDEX IF NOT EXISTS idx_events_token ON events(token_id);
CREATE INDEX IF NOT EXISTS idx_events_type_time ON events(event_type,created_at);
CREATE TABLE IF NOT EXISTS virtual_positions(id BIGSERIAL PRIMARY KEY,token_id TEXT NOT NULL,arm TEXT NOT NULL,status TEXT NOT NULL,requested_size_usd DOUBLE PRECISION NOT NULL,filled_size_usd DOUBLE PRECISION NOT NULL DEFAULT 0,entry_price DOUBLE PRECISION,opened_at TIMESTAMPTZ,closed_at TIMESTAMPTZ,exit_price DOUBLE PRECISION,UNIQUE(token_id,arm,status));
CREATE TABLE IF NOT EXISTS outcome_jobs(id BIGSERIAL PRIMARY KEY,token_id TEXT NOT NULL,horizon_minutes INTEGER NOT NULL,due_at TIMESTAMPTZ NOT NULL,status TEXT NOT NULL DEFAULT 'pending',UNIQUE(token_id,horizon_minutes));
"""
SQLITE_SCHEMA="""
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,event_type TEXT NOT NULL,token_id TEXT,arm TEXT,payload_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_events_token ON events(token_id);
CREATE INDEX IF NOT EXISTS idx_events_type_time ON events(event_type,created_at);
CREATE TABLE IF NOT EXISTS virtual_positions(id INTEGER PRIMARY KEY AUTOINCREMENT,token_id TEXT NOT NULL,arm TEXT NOT NULL,status TEXT NOT NULL,requested_size_usd REAL NOT NULL,filled_size_usd REAL NOT NULL DEFAULT 0,entry_price REAL,opened_at TEXT,closed_at TEXT,exit_price REAL,UNIQUE(token_id,arm,status));
"""

async def init_db():
    if settings.database_url:
        import psycopg
        async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
            async with db.cursor() as cur:
                await cur.execute(PG_SCHEMA)
        return
    async with aiosqlite.connect(settings.db_path) as db:
        await db.executescript(SQLITE_SCHEMA);await db.commit()

async def log_event(event:Event):
    payload=json.dumps(event.payload,default=str)
    if settings.database_url:
        import psycopg
        async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
            await db.execute("INSERT INTO events(created_at,event_type,token_id,arm,payload_json) VALUES(%s,%s,%s,%s,%s::jsonb)",(event.created_at,event.event_type,event.token_id,event.arm,payload))
        return
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("INSERT INTO events(created_at,event_type,token_id,arm,payload_json) VALUES(?,?,?,?,?)",(event.created_at.isoformat(),event.event_type,event.token_id,event.arm,payload));await db.commit()

async def recent_events(limit:int=50):
    if settings.database_url:
        import psycopg
        from psycopg.rows import dict_row
        async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
            cur=await db.execute("SELECT * FROM events ORDER BY id DESC LIMIT %s",(limit,))
            return await cur.fetchall()
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory=aiosqlite.Row;cur=await db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?",(limit,));return [dict(r) for r in await cur.fetchall()]
