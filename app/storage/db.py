import json,aiosqlite
from app.core.models import Event
from app.core.config import settings
SCHEMA="""
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,event_type TEXT NOT NULL,token_id TEXT,arm TEXT,payload_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_events_token ON events(token_id);
CREATE INDEX IF NOT EXISTS idx_events_type_time ON events(event_type,created_at);
CREATE TABLE IF NOT EXISTS virtual_positions(id INTEGER PRIMARY KEY AUTOINCREMENT,token_id TEXT NOT NULL,arm TEXT NOT NULL,status TEXT NOT NULL,requested_size_usd REAL NOT NULL,filled_size_usd REAL NOT NULL DEFAULT 0,entry_price REAL,opened_at TEXT,closed_at TEXT,exit_price REAL,UNIQUE(token_id,arm,status));
"""
async def init_db():
    async with aiosqlite.connect(settings.db_path) as db:
        await db.executescript(SCHEMA);await db.commit()
async def log_event(event:Event):
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("INSERT INTO events(created_at,event_type,token_id,arm,payload_json) VALUES(?,?,?,?,?)",(event.created_at.isoformat(),event.event_type,event.token_id,event.arm,json.dumps(event.payload,default=str)));await db.commit()
async def recent_events(limit:int=50):
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory=aiosqlite.Row;cur=await db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?",(limit,));return [dict(r) for r in await cur.fetchall()]
