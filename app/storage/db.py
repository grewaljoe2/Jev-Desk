import json,aiosqlite
from datetime import timedelta
from app.core.models import Event
from app.core.config import settings
HORIZONS=(5,15,30,60,180,360,720,1440,2880,4320)
PG_SCHEMA="""
CREATE TABLE IF NOT EXISTS events(id BIGSERIAL PRIMARY KEY,created_at TIMESTAMPTZ NOT NULL,event_type TEXT NOT NULL,token_id TEXT,arm TEXT,payload_json JSONB NOT NULL);
CREATE INDEX IF NOT EXISTS idx_events_token ON events(token_id);
CREATE INDEX IF NOT EXISTS idx_events_type_time ON events(event_type,created_at);
CREATE TABLE IF NOT EXISTS virtual_positions(id BIGSERIAL PRIMARY KEY,token_id TEXT NOT NULL,arm TEXT NOT NULL,status TEXT NOT NULL,requested_size_usd DOUBLE PRECISION NOT NULL,filled_size_usd DOUBLE PRECISION NOT NULL DEFAULT 0,entry_price DOUBLE PRECISION,opened_at TIMESTAMPTZ,closed_at TIMESTAMPTZ,exit_price DOUBLE PRECISION,UNIQUE(token_id,arm,status));
CREATE TABLE IF NOT EXISTS outcome_jobs(id BIGSERIAL PRIMARY KEY,token_id TEXT NOT NULL,horizon_minutes INTEGER NOT NULL,due_at TIMESTAMPTZ NOT NULL,status TEXT NOT NULL DEFAULT 'pending',UNIQUE(token_id,horizon_minutes));
ALTER TABLE outcome_jobs ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ;
ALTER TABLE outcome_jobs ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE outcome_jobs ADD COLUMN IF NOT EXISTS last_error TEXT;
ALTER TABLE outcome_jobs ADD COLUMN IF NOT EXISTS timing_provenance TEXT NOT NULL DEFAULT 'legacy_pre_v061';
ALTER TABLE outcome_jobs ADD COLUMN IF NOT EXISTS baseline_event_id BIGINT;
"""
SQLITE_SCHEMA="""CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,event_type TEXT NOT NULL,token_id TEXT,arm TEXT,payload_json TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_events_token ON events(token_id);CREATE INDEX IF NOT EXISTS idx_events_type_time ON events(event_type,created_at);CREATE TABLE IF NOT EXISTS virtual_positions(id INTEGER PRIMARY KEY AUTOINCREMENT,token_id TEXT NOT NULL,arm TEXT NOT NULL,status TEXT NOT NULL,requested_size_usd REAL NOT NULL,filled_size_usd REAL NOT NULL DEFAULT 0,entry_price REAL,opened_at TEXT,closed_at TEXT,exit_price REAL,UNIQUE(token_id,arm,status));"""
async def init_db():
    if settings.database_url:
        import psycopg
        async with await psycopg.AsyncConnection.connect(settings.database_url) as db: await db.execute(PG_SCHEMA)
        return
    async with aiosqlite.connect(settings.db_path) as db: await db.executescript(SQLITE_SCHEMA);await db.commit()
async def log_event(event):
    payload=json.dumps(event.payload,default=str)
    if settings.database_url:
        import psycopg
        async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
            cur=await db.execute("INSERT INTO events(created_at,event_type,token_id,arm,payload_json) VALUES(%s,%s,%s,%s,%s::jsonb) RETURNING id",(event.created_at,event.event_type,event.token_id,event.arm,payload))
            row=await cur.fetchone();return row[0]
    async with aiosqlite.connect(settings.db_path) as db: await db.execute("INSERT INTO events(created_at,event_type,token_id,arm,payload_json) VALUES(?,?,?,?,?)",(event.created_at.isoformat(),event.event_type,event.token_id,event.arm,payload));await db.commit()
async def schedule_outcomes(token_id,observed_at,baseline_event_id=None):
    if not settings.database_url:return
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        for h in HORIZONS:
            await db.execute("INSERT INTO outcome_jobs(token_id,horizon_minutes,due_at,status,timing_provenance,baseline_event_id) VALUES(%s,%s,%s,'pending','clean_v061',%s) ON CONFLICT(token_id,horizon_minutes) DO NOTHING",(token_id,h,observed_at+timedelta(minutes=h),baseline_event_id))
async def research_counts():
    if not settings.database_url:return {"storage":"sqlite","snapshots":0,"decisions":0,"outcomes":0,"pending":0}
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        cur=await db.execute("SELECT count(*) FILTER(WHERE event_type='SNAPSHOT'),count(*) FILTER(WHERE event_type='DECISION'),count(*) FILTER(WHERE event_type='OUTCOME') FROM events"); a=await cur.fetchone()
        cur=await db.execute("SELECT count(*) FROM outcome_jobs WHERE status='pending'"); p=(await cur.fetchone())[0]
        cur=await db.execute("SELECT count(*) FROM outcome_jobs WHERE status='pending' AND due_at<=NOW() AND COALESCE(next_attempt_at,due_at)<=NOW()"); due=(await cur.fetchone())[0]
        return {"storage":"postgres","snapshots":a[0],"decisions":a[1],"outcomes":a[2],"pending":p,"due_now":due}
async def recent_events(limit=50):
    if settings.database_url:
        import psycopg
        from psycopg.rows import dict_row
        async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
            cur=await db.execute("SELECT * FROM events ORDER BY id DESC LIMIT %s",(limit,));return await cur.fetchall()
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory=aiosqlite.Row;cur=await db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?",(limit,));return [dict(r) for r in await cur.fetchall()]

async def due_outcome_jobs(limit=12):
    if not settings.database_url:return []
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("SELECT j.id,j.token_id,j.horizon_minutes,j.due_at,j.timing_provenance,e.payload_json FROM outcome_jobs j JOIN LATERAL (SELECT payload_json FROM events WHERE (j.baseline_event_id IS NOT NULL AND id=j.baseline_event_id) OR (j.baseline_event_id IS NULL AND token_id=j.token_id AND event_type='SNAPSHOT') ORDER BY CASE WHEN j.baseline_event_id IS NOT NULL THEN 0 ELSE 1 END,id ASC LIMIT 1) e ON true WHERE j.status='pending' AND j.due_at<=NOW() AND COALESCE(j.next_attempt_at,j.due_at)<=NOW() ORDER BY j.due_at LIMIT %s",(limit,))
        return await cur.fetchall()
async def due_outcome_group(limit=4):
    jobs=await due_outcome_jobs(limit*10)
    groups={}
    for job in jobs:
        base=job["payload_json"];pool_id=(base.get("raw") or {}).get("pool_id");key=(base.get("chain"),pool_id)
        if not pool_id:continue
        if key not in groups and len(groups)>=limit:continue
        groups.setdefault(key,[]).append(job)
    return list(groups.values())
async def complete_outcome_job(job_id,event):
    if not settings.database_url:return
    import psycopg
    payload=json.dumps(event.payload,default=str)
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        async with db.transaction():
            cur=await db.execute("UPDATE outcome_jobs SET status='done',last_error=NULL WHERE id=%s AND status='pending' RETURNING id",(job_id,))
            if not await cur.fetchone():return
            await db.execute("INSERT INTO events(created_at,event_type,token_id,arm,payload_json) VALUES(%s,%s,%s,%s,%s::jsonb)",(event.created_at,event.event_type,event.token_id,event.arm,payload))
async def defer_outcome_job(job_id,minutes=5,error=None):
    if not settings.database_url:return
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:await db.execute("UPDATE outcome_jobs SET next_attempt_at=NOW()+(%s * interval '1 minute'),attempts=attempts+1,last_error=%s WHERE id=%s",(minutes,error,job_id))
