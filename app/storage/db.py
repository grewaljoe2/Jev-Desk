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
ALTER TABLE virtual_positions ADD COLUMN IF NOT EXISTS baseline_event_id BIGINT;
ALTER TABLE virtual_positions ADD COLUMN IF NOT EXISTS last_price DOUBLE PRECISION;
ALTER TABLE virtual_positions ADD COLUMN IF NOT EXISTS last_marked_at TIMESTAMPTZ;
ALTER TABLE virtual_positions ADD COLUMN IF NOT EXISTS provenance TEXT NOT NULL DEFAULT 'legacy_pre_forward';
CREATE TABLE IF NOT EXISTS shadow_exit_arms(id BIGSERIAL PRIMARY KEY,position_id BIGINT NOT NULL,policy TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',entry_price DOUBLE PRECISION NOT NULL,opened_at TIMESTAMPTZ NOT NULL,peak_price DOUBLE PRECISION NOT NULL,exit_price DOUBLE PRECISION,closed_at TIMESTAMPTZ,exit_reason TEXT,last_price DOUBLE PRECISION,last_marked_at TIMESTAMPTZ,UNIQUE(position_id,policy));
CREATE TABLE IF NOT EXISTS outcome_jobs(id BIGSERIAL PRIMARY KEY,token_id TEXT NOT NULL,horizon_minutes INTEGER NOT NULL,due_at TIMESTAMPTZ NOT NULL,status TEXT NOT NULL DEFAULT 'pending',UNIQUE(token_id,horizon_minutes));
ALTER TABLE outcome_jobs ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ;
ALTER TABLE outcome_jobs ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE outcome_jobs ADD COLUMN IF NOT EXISTS last_error TEXT;
ALTER TABLE outcome_jobs ADD COLUMN IF NOT EXISTS timing_provenance TEXT NOT NULL DEFAULT 'legacy_pre_v061';
ALTER TABLE outcome_jobs ADD COLUMN IF NOT EXISTS baseline_event_id BIGINT;
ALTER TABLE outcome_jobs DROP CONSTRAINT IF EXISTS outcome_jobs_token_id_horizon_minutes_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_outcome_jobs_baseline_horizon ON outcome_jobs(baseline_event_id,horizon_minutes) WHERE baseline_event_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_outcome_jobs_legacy_token_horizon ON outcome_jobs(token_id,horizon_minutes) WHERE baseline_event_id IS NULL;
CREATE TABLE IF NOT EXISTS qualification_jobs(id BIGSERIAL PRIMARY KEY,token_id TEXT NOT NULL,chain TEXT NOT NULL,pool_id TEXT NOT NULL,due_at TIMESTAMPTZ NOT NULL,status TEXT NOT NULL DEFAULT 'pending',attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT,completed_at TIMESTAMPTZ,UNIQUE(chain,pool_id));
ALTER TABLE qualification_jobs ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_qualification_jobs_due ON qualification_jobs(status,due_at);
CREATE TABLE IF NOT EXISTS fast_entry_jobs(id BIGSERIAL PRIMARY KEY,token_id TEXT NOT NULL,chain TEXT NOT NULL,pool_id TEXT NOT NULL,cohort_minutes INTEGER NOT NULL,due_at TIMESTAMPTZ NOT NULL,status TEXT NOT NULL DEFAULT 'pending',attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT,completed_at TIMESTAMPTZ,next_attempt_at TIMESTAMPTZ,UNIQUE(chain,pool_id,cohort_minutes));
CREATE INDEX IF NOT EXISTS idx_fast_entry_jobs_due ON fast_entry_jobs(status,due_at);
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
async def schedule_outcomes(token_id,observed_at,baseline_event_id=None,force=False,horizons=None):
    if not settings.database_url:return
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        if not force:
            cur=await db.execute("SELECT 1 FROM outcome_jobs WHERE token_id=%s AND baseline_event_id IS NOT NULL AND due_at >= %s LIMIT 1",(token_id,observed_at))
            if await cur.fetchone():return
        for h in (HORIZONS if horizons is None else tuple(horizons)):
            await db.execute("INSERT INTO outcome_jobs(token_id,horizon_minutes,due_at,status,timing_provenance,baseline_event_id) VALUES(%s,%s,%s,'pending','clean_v061',%s) ON CONFLICT DO NOTHING",(token_id,h,observed_at+timedelta(minutes=h),baseline_event_id))
async def savip_candidate_pool(window_minutes=15,limit=200):
    """Savip FREE CUT from fresh candidates using the freshest already-collected facts.

    Candidate membership still comes only from recent DISCOVERY. For each candidate,
    reuse its newest DISCOVERY or >=15m qualification SNAPSHOT so Savip does not
    discard a later provider refresh. This adds no network calls and changes no gate.
    """
    if not settings.database_url:return {"scanned":0,"free_cut_survivors":[],"wait_too_young":[],"kills":{},"missing_fields":{}}
    import psycopg
    from psycopg.rows import dict_row
    from app.strategy.reference_thresholds import HARD
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("""WITH candidates AS (
          SELECT DISTINCT ON (e.token_id)
            e.id AS discovery_event_id,e.token_id,e.created_at AS discovered_at
          FROM events e
          WHERE e.event_type='DISCOVERY'
            AND e.created_at>=NOW()-(%s * interval '1 minute')
          ORDER BY e.token_id,e.created_at DESC
        )
        SELECT c.discovery_event_id,c.token_id,c.discovered_at,
          o.payload_json->>'chain' AS chain,
          NULLIF(o.payload_json->>'age_minutes','')::double precision AS age_minutes,
          NULLIF(o.payload_json->>'price_usd','')::double precision AS price_usd,
          NULLIF(o.payload_json->>'liquidity_usd','')::double precision AS liquidity_usd,
          NULLIF(o.payload_json->>'volume_h24_usd','')::double precision AS volume_h24_usd,
          NULLIF(o.payload_json->>'mcap_usd','')::double precision AS mcap_usd,
          NULLIF(o.payload_json->>'trades_h24','')::integer AS trades_h24,
          o.event_type AS fact_source,o.created_at AS facts_at
        FROM candidates c
        JOIN LATERAL (
          SELECT e2.event_type,e2.created_at,e2.payload_json
          FROM events e2
          WHERE e2.token_id=c.token_id AND e2.event_type IN ('DISCOVERY','SNAPSHOT')
          ORDER BY e2.created_at DESC LIMIT 1
        ) o ON TRUE
        ORDER BY c.discovered_at DESC LIMIT %s""",(window_minutes,limit))
        rows=await cur.fetchall()
    survivors=[];wait=[];kills={};missing={}
    for r in rows:
        x=dict(r);age=x.get("age_minutes");liq=x.get("liquidity_usd");vol=x.get("volume_h24_usd");mc=x.get("mcap_usd")
        absent=[k for k,v in (("age_minutes",age),("liquidity_usd",liq),("volume_h24_usd",vol),("mcap_usd",mc)) if v is None]
        reason=None
        if absent:
            reason="missing_free_fact"
            for k in absent:missing[k]=missing.get(k,0)+1
            x["missing_free_fields"]=absent
        elif age<HARD["min_age_minutes"]:reason="wait_too_young"
        elif age>HARD["max_age_hours"]*60:reason="too_old"
        elif liq<HARD["min_liquidity_usd"]:reason="liquidity"
        elif vol<HARD["min_volume_h24"]:reason="volume"
        elif mc<HARD["min_mcap_usd"]:reason="mcap_low"
        elif mc>HARD["max_mcap_usd"]:reason="mcap_high"
        if reason=="wait_too_young":wait.append(x)
        elif reason:kills[reason]=kills.get(reason,0)+1
        else:survivors.append(x)
    return {"scanned":len(rows),"free_cut_survivors":survivors,"wait_too_young":wait,"kills":kills,"missing_fields":missing}

async def open_shadow_position(snapshot,baseline_event_id,notional_usd=100.0):
    """Open one research-only position from a contemporaneous qualified snapshot. No broker/wallet action."""
    if not settings.database_url or snapshot.price_usd is None or snapshot.price_usd<=0:return None
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        async with db.transaction():
            cur=await db.execute("SELECT id FROM virtual_positions WHERE token_id=%s AND arm='reference' AND status='open' LIMIT 1",(snapshot.token_id,))
            if await cur.fetchone():return None
            cur=await db.execute("INSERT INTO virtual_positions(token_id,arm,status,requested_size_usd,filled_size_usd,entry_price,opened_at,baseline_event_id,provenance) VALUES(%s,'reference','open',%s,%s,%s,%s,%s,'forward_qualification_v1') RETURNING id",(snapshot.token_id,notional_usd,notional_usd,snapshot.price_usd,snapshot.observed_at,baseline_event_id))
            position_id=(await cur.fetchone())[0]
            for policy in ('tp20_sl10_v1','trail15_after10_v1','time24h_v1'):
                await db.execute("INSERT INTO shadow_exit_arms(position_id,policy,status,entry_price,opened_at,peak_price,last_price,last_marked_at) VALUES(%s,%s,'open',%s,%s,%s,%s,%s) ON CONFLICT(position_id,policy) DO NOTHING",(position_id,policy,snapshot.price_usd,snapshot.observed_at,snapshot.price_usd,snapshot.price_usd,snapshot.observed_at))
            payload=json.dumps({"position_id":position_id,"baseline_event_id":baseline_event_id,"notional_usd":notional_usd,"entry_price":snapshot.price_usd,"price_basis":"provider_observed_price_proxy","research_only":True,"real_execution":False},default=str)
            await db.execute("INSERT INTO events(created_at,event_type,token_id,arm,payload_json) VALUES(%s,'SHADOW_ENTRY',%s,'reference',%s::jsonb)",(snapshot.observed_at,snapshot.token_id,payload))
            return position_id

async def mark_shadow_positions(token_id,price,observed_at,baseline_event_id=None):
    """Mark open research positions from an already-collected provider observation; never makes an extra market-data call."""
    if not settings.database_url or price is None or price<=0:return
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        await db.execute("UPDATE virtual_positions SET last_price=%s,last_marked_at=%s WHERE token_id=%s AND status='open'",(price,observed_at,token_id))
        cur=await db.execute("SELECT a.id,a.policy,a.entry_price,a.opened_at,a.peak_price,p.filled_size_usd FROM shadow_exit_arms a JOIN virtual_positions p ON p.id=a.position_id WHERE p.token_id=%s AND p.status='open' AND a.status='open'",(token_id,))
        for arm_id,policy,entry,opened,peak,size in await cur.fetchall():
            peak=max(float(peak or entry),float(price));ret=float(price)/float(entry)-1;reason=None
            if policy=='tp20_sl10_v1':
                if ret>=0.20:reason='take_profit_20'
                elif ret<=-0.10:reason='stop_loss_10'
            elif policy=='trail15_after10_v1' and peak>=float(entry)*1.10 and float(price)<=peak*0.85:reason='trailing_15_after_10'
            elif policy=='time24h_v1' and (observed_at-opened).total_seconds()>=86400:reason='time_24h'
            if reason:
                await db.execute("UPDATE shadow_exit_arms SET status='closed',peak_price=%s,last_price=%s,last_marked_at=%s,exit_price=%s,closed_at=%s,exit_reason=%s WHERE id=%s",(peak,price,observed_at,price,observed_at,reason,arm_id))
            else:
                await db.execute("UPDATE shadow_exit_arms SET peak_price=%s,last_price=%s,last_marked_at=%s WHERE id=%s",(peak,price,observed_at,arm_id))

async def active_shadow_targets():
    """Open forward positions that need high-priority marks. Pool identity comes from the immutable entry snapshot."""
    if not settings.database_url:return []
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("""SELECT DISTINCT ON (p.token_id) p.id,p.token_id,p.baseline_event_id,p.last_marked_at,
          e.payload_json->>'chain' AS chain,e.payload_json->'raw'->>'pool_id' AS pool_id
          FROM virtual_positions p JOIN events e ON e.id=p.baseline_event_id
          WHERE p.status='open' AND (p.provenance='forward_qualification_v1' OR p.provenance LIKE 'forward_fast_%')
            AND EXISTS (SELECT 1 FROM shadow_exit_arms a WHERE a.position_id=p.id AND a.status='open')
          ORDER BY p.token_id,p.last_marked_at ASC NULLS FIRST""")
        return await cur.fetchall()

async def fast_entry_summary():
    if not settings.database_url:return {"jobs":{},"cohorts":[]}
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("SELECT cohort_minutes,count(*) FILTER(WHERE status='pending') AS pending,count(*) FILTER(WHERE status='done') AS checked,count(*) FILTER(WHERE status='missed') AS missed FROM fast_entry_jobs GROUP BY cohort_minutes ORDER BY cohort_minutes")
        jobs=await cur.fetchall()
        cur=await db.execute("""SELECT CASE p.arm WHEN 'fast_1m' THEN 1 WHEN 'fast_3m' THEN 3 WHEN 'fast_5m' THEN 5 WHEN 'fast_10m' THEN 10 END AS cohort_minutes,a.policy,
          count(*) AS positions,count(*) FILTER(WHERE a.status='closed') AS closed,
          count(*) FILTER(WHERE a.status='closed' AND a.exit_price>a.entry_price) AS wins,
          COALESCE(sum(CASE WHEN a.status='closed' THEN 100.0*(a.exit_price/a.entry_price-1) ELSE 0 END),0) AS realized_pnl_usd
          FROM virtual_positions p JOIN shadow_exit_arms a ON a.position_id=p.id
          WHERE p.arm IN ('fast_1m','fast_3m','fast_5m','fast_10m')
          GROUP BY p.arm,a.policy ORDER BY cohort_minutes,a.policy""")
        return {"jobs":jobs,"cohorts":await cur.fetchall()}

async def shadow_exit_summary():
    """Per-policy forward evidence using actual observed exit prices; open P&L stays separate."""
    if not settings.database_url:return []
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("""SELECT a.policy,
          count(*) FILTER(WHERE a.status='open') AS open,
          count(*) FILTER(WHERE a.status='closed') AS closed,
          count(*) FILTER(WHERE a.status='closed' AND a.exit_price>a.entry_price) AS wins,
          count(*) FILTER(WHERE a.status='closed' AND a.exit_price<=a.entry_price) AS losses,
          COALESCE(sum(CASE WHEN a.status='closed' THEN 100.0*(a.exit_price/a.entry_price-1) ELSE 0 END),0) AS realized_pnl_usd,
          COALESCE(sum(CASE WHEN a.status='open' AND a.last_price IS NOT NULL THEN 100.0*(a.last_price/a.entry_price-1) ELSE 0 END),0) AS unrealized_pnl_usd,
          COALESCE(avg(CASE WHEN a.status='closed' THEN 100.0*(a.exit_price/a.entry_price-1) END),0) AS avg_return_pct,
          COALESCE(sum(CASE WHEN a.status='closed' AND a.exit_price>a.entry_price THEN 100.0*(a.exit_price/a.entry_price-1) ELSE 0 END),0) AS gross_profit_usd,
          COALESCE(-sum(CASE WHEN a.status='closed' AND a.exit_price<a.entry_price THEN 100.0*(a.exit_price/a.entry_price-1) ELSE 0 END),0) AS gross_loss_usd
          FROM shadow_exit_arms a JOIN virtual_positions p ON p.id=a.position_id
          WHERE p.provenance='forward_qualification_v1'
          GROUP BY a.policy ORDER BY a.policy""")
        rows=await cur.fetchall()
        for r in rows:
            gp=float(r["gross_profit_usd"] or 0);gl=float(r["gross_loss_usd"] or 0);closed=int(r["closed"] or 0)
            r["win_rate_pct"]=(100.0*int(r["wins"] or 0)/closed) if closed else None
            r["profit_factor"]=(gp/gl) if gl>0 else (None if gp==0 else "inf")
        return rows

async def fast_entry_discovery_funnel():
    """Count first-seen discovery eligibility for each Fast horizon without changing scheduling."""
    if not settings.database_url:return []
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("""WITH first_seen AS (
          SELECT DISTINCT ON (token_id) token_id,
            NULLIF(payload_json->>'age_minutes','')::double precision AS age_minutes
          FROM events
          WHERE event_type='DISCOVERY'
          ORDER BY token_id,created_at ASC
        ), horizons(cohort_minutes) AS (VALUES (1),(3),(5),(10))
        SELECT h.cohort_minutes,
          count(*) FILTER(WHERE f.age_minutes IS NOT NULL) AS discovered_with_age,
          count(*) FILTER(WHERE f.age_minutes IS NOT NULL AND f.age_minutes<=h.cohort_minutes) AS eligible_at_first_seen,
          count(*) FILTER(WHERE f.age_minutes IS NOT NULL AND f.age_minutes>h.cohort_minutes) AS already_too_old,
          count(*) FILTER(WHERE f.age_minutes IS NULL) AS missing_age
        FROM horizons h CROSS JOIN first_seen f
        GROUP BY h.cohort_minutes ORDER BY h.cohort_minutes""")
        rows=await cur.fetchall()
        cur=await db.execute("""WITH first_seen AS (
          SELECT DISTINCT ON (token_id) token_id,
            split_part(token_id,':',1) AS chain,
            NULLIF(payload_json->>'age_minutes','')::double precision AS age_minutes
          FROM events WHERE event_type='DISCOVERY'
          ORDER BY token_id,created_at ASC
        )
        SELECT chain,count(*) AS discovered,
          count(*) FILTER(WHERE age_minutes<=1) AS within_1m,
          count(*) FILTER(WHERE age_minutes<=3) AS within_3m,
          count(*) FILTER(WHERE age_minutes<=5) AS within_5m,
          count(*) FILTER(WHERE age_minutes<=10) AS within_10m,
          avg(age_minutes) AS avg_first_seen_age_minutes
        FROM first_seen WHERE age_minutes IS NOT NULL
        GROUP BY chain ORDER BY discovered DESC""")
        return {"horizons":rows,"by_chain":await cur.fetchall()}

async def fast_entry_diagnostics():
    """Explain whether fast cohorts are empty because of filters, lateness, or backlog."""
    if not settings.database_url:return {"decisions":[],"jobs":[]}
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("""SELECT arm,payload_json->>'reason' AS reason,count(*) AS n,
          avg(NULLIF(payload_json->>'observed_age_minutes','')::double precision) AS avg_observed_age_minutes
          FROM events WHERE event_type='FAST_ENTRY_DECISION'
          GROUP BY arm,payload_json->>'reason' ORDER BY arm,n DESC""")
        decisions=await cur.fetchall()
        cur=await db.execute("""SELECT cohort_minutes,status,count(*) AS n,
          min(due_at) FILTER(WHERE status='pending') AS oldest_pending_due_at,
          max(due_at) FILTER(WHERE status='pending') AS newest_pending_due_at,
          max(attempts) AS max_attempts
          FROM fast_entry_jobs GROUP BY cohort_minutes,status ORDER BY cohort_minutes,status""")
        return {"decisions":decisions,"jobs":await cur.fetchall()}

async def fast_shadow_positions_detail(limit=200):
    """Individual forward fast-entry positions, kept separate from the 15m control ledger."""
    if not settings.database_url:return []
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("""SELECT p.id,p.token_id,p.arm,p.status,p.filled_size_usd,p.entry_price,p.opened_at,p.last_price,p.last_marked_at,p.baseline_event_id,p.provenance,
          CASE WHEN p.entry_price>0 AND p.last_price IS NOT NULL THEN p.filled_size_usd*(p.last_price/p.entry_price-1) ELSE 0 END AS hold_pnl_usd,
          COALESCE(jsonb_agg(jsonb_build_object('policy',a.policy,'status',a.status,'entry_price',a.entry_price,'peak_price',a.peak_price,'last_price',a.last_price,'exit_price',a.exit_price,'opened_at',a.opened_at,'closed_at',a.closed_at,'exit_reason',a.exit_reason)) FILTER(WHERE a.id IS NOT NULL),'[]'::jsonb) AS exit_arms
          FROM virtual_positions p LEFT JOIN shadow_exit_arms a ON a.position_id=p.id
          WHERE p.arm = ANY(%s)
          GROUP BY p.id ORDER BY p.opened_at DESC,p.id DESC LIMIT %s""",(["fast_1m","fast_3m","fast_5m","fast_10m"],limit))
        return await cur.fetchall()

async def shadow_positions_detail(limit=100):
    """Read-only shadow ledger. Legacy rows remain visible but are excluded from forward validation."""
    if not settings.database_url:return []
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("""SELECT p.id,p.token_id,p.arm,p.status,p.requested_size_usd,p.filled_size_usd,p.entry_price,p.opened_at,p.closed_at,p.exit_price,p.last_price,p.last_marked_at,p.baseline_event_id,p.provenance,
          CASE WHEN p.status='open' AND p.entry_price>0 AND p.last_price IS NOT NULL THEN p.filled_size_usd*(p.last_price/p.entry_price-1)
               WHEN p.status='closed' AND p.entry_price>0 AND p.exit_price IS NOT NULL THEN p.filled_size_usd*(p.exit_price/p.entry_price-1) ELSE 0 END AS pnl_usd,
          COALESCE(jsonb_agg(jsonb_build_object('policy',a.policy,'status',a.status,'entry_price',a.entry_price,'peak_price',a.peak_price,'last_price',a.last_price,'exit_price',a.exit_price,'opened_at',a.opened_at,'closed_at',a.closed_at,'exit_reason',a.exit_reason)) FILTER(WHERE a.id IS NOT NULL),'[]'::jsonb) AS exit_arms
          FROM virtual_positions p LEFT JOIN shadow_exit_arms a ON a.position_id=p.id
          WHERE p.arm='reference' GROUP BY p.id ORDER BY p.opened_at DESC NULLS LAST,p.id DESC LIMIT %s""",(limit,))
        return await cur.fetchall()

async def shadow_position_summary():
    if not settings.database_url:return {"open":0,"closed":0,"realized_pnl_usd":0.0}
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        cur=await db.execute("SELECT count(*) FILTER(WHERE status='open'),count(*) FILTER(WHERE status='closed'),COALESCE(sum(CASE WHEN status='closed' AND entry_price>0 AND exit_price IS NOT NULL THEN filled_size_usd*(exit_price/entry_price-1) ELSE 0 END),0),COALESCE(sum(CASE WHEN status='open' AND entry_price>0 AND last_price IS NOT NULL THEN filled_size_usd*(last_price/entry_price-1) ELSE 0 END),0) FROM virtual_positions WHERE arm='reference'")
        r=await cur.fetchone()
        cur=await db.execute("SELECT count(*) FILTER(WHERE status='open' AND provenance='forward_qualification_v1'),COALESCE(sum(CASE WHEN provenance='forward_qualification_v1' AND status='open' AND entry_price>0 AND last_price IS NOT NULL THEN filled_size_usd*(last_price/entry_price-1) WHEN provenance='forward_qualification_v1' AND status='closed' AND entry_price>0 AND exit_price IS NOT NULL THEN filled_size_usd*(exit_price/entry_price-1) ELSE 0 END),0),count(*) FILTER(WHERE status='open' AND provenance<>'forward_qualification_v1'),COALESCE(sum(CASE WHEN provenance<>'forward_qualification_v1' AND status='open' AND entry_price>0 AND last_price IS NOT NULL THEN filled_size_usd*(last_price/entry_price-1) WHEN provenance<>'forward_qualification_v1' AND status='closed' AND entry_price>0 AND exit_price IS NOT NULL THEN filled_size_usd*(exit_price/entry_price-1) ELSE 0 END),0) FROM virtual_positions WHERE arm='reference'")
        x=await cur.fetchone();return {"open":r[0],"closed":r[1],"realized_pnl_usd":float(r[2] or 0),"unrealized_pnl_usd":float(r[3] or 0),"forward_open":x[0],"forward_pnl_usd":float(x[1] or 0),"legacy_open":x[2],"legacy_pnl_usd":float(x[3] or 0)}

async def research_counts():
    if not settings.database_url:return {"storage":"sqlite","snapshots":0,"decisions":0,"outcomes":0,"pending":0}
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        cur=await db.execute("SELECT count(*) FILTER(WHERE event_type='SNAPSHOT'),count(*) FILTER(WHERE event_type='DECISION'),count(*) FILTER(WHERE event_type='OUTCOME') FROM events"); a=await cur.fetchone()
        cur=await db.execute("SELECT count(*) FROM outcome_jobs WHERE status='pending'"); p=(await cur.fetchone())[0]
        cur=await db.execute("SELECT count(*) FROM outcome_jobs WHERE status='pending' AND due_at<=NOW() AND COALESCE(next_attempt_at,due_at)<=NOW()"); due=(await cur.fetchone())[0]
        return {"storage":"postgres","snapshots":a[0],"decisions":a[1],"outcomes":a[2],"pending":p,"due_now":due}
async def outcome_quality():
    if not settings.database_url:return {"clean_done":0,"legacy_done":0,"clean_pending":0,"clean_cohorts":0,"clean_complete_cohorts":0}
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        cur=await db.execute("SELECT count(*) FILTER(WHERE status='done' AND timing_provenance='clean_v061'),count(*) FILTER(WHERE status='done' AND timing_provenance='legacy_pre_v061'),count(*) FILTER(WHERE status='pending' AND timing_provenance='clean_v061'),count(DISTINCT baseline_event_id) FILTER(WHERE baseline_event_id IS NOT NULL),count(DISTINCT baseline_event_id) FILTER(WHERE baseline_event_id IS NOT NULL AND status='done' AND NOT EXISTS (SELECT 1 FROM outcome_jobs p WHERE p.baseline_event_id=outcome_jobs.baseline_event_id AND p.status<>'done')) FROM outcome_jobs")
        r=await cur.fetchone();return {"clean_done":r[0],"legacy_done":r[1],"clean_pending":r[2],"clean_cohorts":r[3],"clean_complete_cohorts":r[4]}
async def recent_events(limit=50):
    if settings.database_url:
        import psycopg
        from psycopg.rows import dict_row
        async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
            cur=await db.execute("SELECT * FROM events ORDER BY id DESC LIMIT %s",(limit,));return await cur.fetchall()
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory=aiosqlite.Row;cur=await db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?",(limit,));return [dict(r) for r in await cur.fetchall()]

async def due_outcome_jobs(limit=120):
    """Prioritize corrected >=15m entry cohorts and likely-qualified evidence before background cohorts."""
    if not settings.database_url:return []
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("SELECT j.id,j.token_id,j.horizon_minutes,j.due_at,j.timing_provenance,j.baseline_event_id,e.payload_json FROM outcome_jobs j JOIN LATERAL (SELECT payload_json FROM events WHERE (j.baseline_event_id IS NOT NULL AND id=j.baseline_event_id) OR (j.baseline_event_id IS NULL AND token_id=j.token_id AND event_type='SNAPSHOT') ORDER BY CASE WHEN j.baseline_event_id IS NOT NULL THEN 0 ELSE 1 END,id ASC LIMIT 1) e ON true WHERE j.status='pending' AND j.due_at<=NOW() AND COALESCE(j.next_attempt_at,j.due_at)<=NOW() ORDER BY CASE WHEN e.payload_json->'raw'->>'qualification_job_id' IS NOT NULL AND (e.payload_json->>'age_minutes')::double precision>=15 AND EXISTS (SELECT 1 FROM events d WHERE d.event_type='DECISION' AND d.token_id=j.token_id AND d.arm='reference' AND d.payload_json->>'eligible'='true') THEN 0 WHEN e.payload_json->'raw'->>'qualification_job_id' IS NOT NULL AND (e.payload_json->>'age_minutes')::double precision>=15 THEN 1 WHEN j.timing_provenance='clean_v061' THEN 2 ELSE 3 END,j.due_at DESC LIMIT %s",(limit,))
        return await cur.fetchall()
async def expire_stale_outcome_jobs():
    """Retire historical checks whose intended point-in-time window is already gone.

    Tolerance scales with the requested horizon: 20% of horizon, with a 5 minute
    floor and 60 minute cap. No provider call is spent on these jobs; evidence is
    preserved as missed rather than pretending a late observation was on time.
    """
    if not settings.database_url:return 0
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        cur=await db.execute("""UPDATE outcome_jobs SET status='missed',last_error='missed_observation_window'
          WHERE status='pending' AND due_at < NOW() -
            (LEAST(60.0,GREATEST(5.0,horizon_minutes*0.20)) * interval '1 minute')
          RETURNING id""")
        return len(await cur.fetchall())

async def fast_entry_pressure():
    """Time-sensitive sub-15m work that background historical checks must never outrank."""
    if not settings.database_url:return {"due":0,"due_soon":0}
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        cur=await db.execute("""SELECT
          count(*) FILTER(WHERE status='pending' AND due_at<=NOW() AND COALESCE(next_attempt_at,due_at)<=NOW()),
          count(*) FILTER(WHERE status='pending' AND due_at<=NOW()+interval '90 seconds' AND COALESCE(next_attempt_at,due_at)<=NOW()+interval '90 seconds')
          FROM fast_entry_jobs""")
        r=await cur.fetchone();return {"due":r[0],"due_soon":r[1]}

async def due_outcome_group(limit=120):
    jobs=await due_outcome_jobs(limit)
    groups={}
    for job in jobs:
        base=job["payload_json"];pool_id=(base.get("raw") or {}).get("pool_id");key=(base.get("chain"),pool_id)
        if not pool_id:continue
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
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:await db.execute("UPDATE outcome_jobs SET next_attempt_at=NOW()+(%s * interval '1 minute'),attempts=attempts+1,last_error=%s WHERE id=%s AND status='pending'",(minutes,error,job_id))

async def clean_replay_rows(limit=500):
    """Return exact-baseline clean cohorts for offline/replay analysis."""
    if not settings.database_url:return []
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("SELECT j.baseline_event_id,b.payload_json AS snapshot_payload,jsonb_agg(DISTINCT o.payload_json) FILTER(WHERE o.id IS NOT NULL) AS outcomes FROM outcome_jobs j JOIN events b ON b.id=j.baseline_event_id LEFT JOIN events o ON o.event_type='OUTCOME' AND (o.payload_json->>'baseline_event_id')::bigint=j.baseline_event_id WHERE j.timing_provenance='clean_v061' AND j.baseline_event_id IS NOT NULL GROUP BY j.baseline_event_id,b.payload_json ORDER BY j.baseline_event_id DESC LIMIT %s",(limit,))
        return await cur.fetchall()

async def qualification_replay_rows(limit=500):
    """Return corrected >=15m qualification-entry cohorts, including cohorts awaiting outcomes."""
    if not settings.database_url:return []
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("SELECT j.baseline_event_id,b.payload_json AS snapshot_payload,jsonb_agg(o.payload_json ORDER BY o.created_at) FILTER(WHERE o.id IS NOT NULL) AS outcomes FROM outcome_jobs j JOIN events b ON b.id=j.baseline_event_id LEFT JOIN events o ON o.event_type='OUTCOME' AND (o.payload_json->>'baseline_event_id')::bigint=j.baseline_event_id WHERE j.timing_provenance='clean_v061' AND j.baseline_event_id IS NOT NULL AND b.payload_json->'raw'->>'qualification_job_id' IS NOT NULL AND (b.payload_json->>'age_minutes')::double precision >= 15 GROUP BY j.baseline_event_id,b.payload_json ORDER BY j.baseline_event_id DESC LIMIT %s",(limit,))
        return await cur.fetchall()

async def qualification_decision_totals():
    """Aggregate ALL corrected >=15m qualification decisions without a replay-row cap."""
    if not settings.database_url:return {"sample_count":0,"qualification":{}}
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("""
        WITH baselines AS (
          SELECT DISTINCT j.baseline_event_id,b.token_id,b.created_at
          FROM outcome_jobs j JOIN events b ON b.id=j.baseline_event_id
          WHERE j.timing_provenance='clean_v061' AND j.baseline_event_id IS NOT NULL
            AND b.event_type='SNAPSHOT'
            AND b.payload_json->'raw'->>'qualification_job_id' IS NOT NULL
            AND (b.payload_json->>'age_minutes')::double precision >= 15
        ), decisions AS (
          SELECT bl.baseline_event_id,d.arm,d.payload_json
          FROM baselines bl
          CROSS JOIN LATERAL (
            SELECT e.arm,e.payload_json
            FROM events e
            WHERE e.event_type='DECISION' AND e.token_id=bl.token_id
              AND e.created_at>=bl.created_at
              AND e.created_at<bl.created_at+interval '2 minutes'
            ORDER BY e.created_at
            LIMIT 3
          ) d
        ), counts AS (
          SELECT arm,
            count(*) FILTER(WHERE (payload_json->>'eligible')::boolean IS TRUE) eligible,
            count(*) FILTER(WHERE (payload_json->>'eligible')::boolean IS NOT TRUE AND ((payload_json->>'reason') LIKE 'missing:%%' OR payload_json->>'reason'='jev_not_configured_fail_closed')) unscorable,
            count(*) FILTER(WHERE (payload_json->>'eligible')::boolean IS NOT TRUE AND NOT ((payload_json->>'reason') LIKE 'missing:%%' OR payload_json->>'reason'='jev_not_configured_fail_closed')) rejected
          FROM decisions GROUP BY arm
        ), reasons AS (
          SELECT arm,jsonb_object_agg(reason,cnt) reasons FROM (
            SELECT arm,payload_json->>'reason' reason,count(*) cnt
            FROM decisions
            WHERE (payload_json->>'eligible')::boolean IS NOT TRUE
            GROUP BY arm,payload_json->>'reason'
          ) r GROUP BY arm
        )
        SELECT (SELECT count(*) FROM baselines) sample_count,c.arm,c.eligible,c.unscorable,c.rejected,COALESCE(r.reasons,'{}'::jsonb) reasons
        FROM counts c LEFT JOIN reasons r USING(arm)
        """)
        rows=await cur.fetchall();sample_count=max([r["sample_count"] for r in rows],default=0)
        q={r["arm"]:{"eligible":r["eligible"],"unscorable":r["unscorable"],"rejected":r["rejected"],"reasons":r["reasons"] or {}} for r in rows}
        return {"sample_count":sample_count,"qualification":q}

async def scoreable_snapshot_quality():
    """Count immutable snapshots by whether deterministic age is present."""
    if not settings.database_url:return {"with_age":0,"missing_age":0,"latest_with_age":None}
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        cur=await db.execute("SELECT count(*) FILTER(WHERE payload_json->>'age_minutes' IS NOT NULL),count(*) FILTER(WHERE payload_json->>'age_minutes' IS NULL),max(created_at) FILTER(WHERE payload_json->>'age_minutes' IS NOT NULL) FROM events WHERE event_type='SNAPSHOT'")
        r=await cur.fetchone();return {"with_age":r[0],"missing_age":r[1],"latest_with_age":r[2].isoformat() if r[2] else None}

async def schedule_qualification(token_id,chain,pool_id,due_at):
    if not settings.database_url or not pool_id:return
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        await db.execute("INSERT INTO qualification_jobs(token_id,chain,pool_id,due_at,status) VALUES(%s,%s,%s,%s,'pending') ON CONFLICT(chain,pool_id) DO NOTHING",(token_id,chain,pool_id,due_at))

async def schedule_fast_entry(token_id,chain,pool_id,cohort_minutes,due_at):
    if not settings.database_url or not pool_id:return
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        await db.execute("INSERT INTO fast_entry_jobs(token_id,chain,pool_id,cohort_minutes,due_at,status) VALUES(%s,%s,%s,%s,%s,'pending') ON CONFLICT(chain,pool_id,cohort_minutes) DO NOTHING",(token_id,chain,pool_id,cohort_minutes,due_at))

async def expire_stale_fast_entry_jobs(grace_minutes=1.0):
    """Mark expired point-in-time Fast observations missed without spending provider calls."""
    if not settings.database_url:return 0
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        cur=await db.execute("""UPDATE fast_entry_jobs
          SET status='missed',completed_at=NOW(),last_error='missed_observation_window',next_attempt_at=NULL
          WHERE status='pending' AND due_at < NOW()-(%s * interval '1 minute')
          RETURNING id""",(grace_minutes,))
        return len(await cur.fetchall())

async def due_fast_entry_jobs(limit=120):
    """Return only still-useful Fast observations, ordered by nearest expiry."""
    if not settings.database_url:return []
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("""SELECT * FROM fast_entry_jobs
          WHERE status='pending' AND due_at<=NOW()
            AND due_at>=NOW()-interval '1 minute'
            AND COALESCE(next_attempt_at,due_at)<=NOW()
          ORDER BY (due_at+interval '1 minute') ASC,cohort_minutes ASC,id ASC
          LIMIT %s""",(limit,))
        return await cur.fetchall()

async def complete_fast_entry_job(job_id):
    if not settings.database_url:return
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        await db.execute("UPDATE fast_entry_jobs SET status='done',completed_at=NOW(),last_error=NULL,next_attempt_at=NULL WHERE id=%s AND status='pending'",(job_id,))

async def defer_fast_entry_job(job_id,minutes=1,error=None):
    if not settings.database_url:return
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        await db.execute("UPDATE fast_entry_jobs SET next_attempt_at=NOW()+(%s * interval '1 minute'),attempts=attempts+1,last_error=%s WHERE id=%s AND status='pending'",(minutes,error,job_id))

async def open_fast_shadow_position(snapshot,baseline_event_id,cohort_minutes,notional_usd=100.0):
    """Separate forward experiment; never changes the 15m reference/control position."""
    if not settings.database_url or snapshot.price_usd is None or snapshot.price_usd<=0:return None
    import psycopg
    arm=f"fast_{int(cohort_minutes)}m"
    provenance=f"forward_fast_{int(cohort_minutes)}m_v1"
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        async with db.transaction():
            cur=await db.execute("SELECT id FROM virtual_positions WHERE token_id=%s AND arm=%s AND status='open' LIMIT 1",(snapshot.token_id,arm))
            if await cur.fetchone():return None
            cur=await db.execute("INSERT INTO virtual_positions(token_id,arm,status,requested_size_usd,filled_size_usd,entry_price,opened_at,baseline_event_id,provenance) VALUES(%s,%s,'open',%s,%s,%s,%s,%s,%s) RETURNING id",(snapshot.token_id,arm,notional_usd,notional_usd,snapshot.price_usd,snapshot.observed_at,baseline_event_id,provenance))
            position_id=(await cur.fetchone())[0]
            for policy in ('tp20_sl10_v1','trail15_after10_v1','time24h_v1'):
                await db.execute("INSERT INTO shadow_exit_arms(position_id,policy,status,entry_price,opened_at,peak_price,last_price,last_marked_at) VALUES(%s,%s,'open',%s,%s,%s,%s,%s) ON CONFLICT(position_id,policy) DO NOTHING",(position_id,policy,snapshot.price_usd,snapshot.observed_at,snapshot.price_usd,snapshot.price_usd,snapshot.observed_at))
            payload=json.dumps({"position_id":position_id,"baseline_event_id":baseline_event_id,"cohort_minutes":cohort_minutes,"notional_usd":notional_usd,"entry_price":snapshot.price_usd,"experiment":"fast_entry_v1","research_only":True,"real_execution":False},default=str)
            await db.execute("INSERT INTO events(created_at,event_type,token_id,arm,payload_json) VALUES(%s,'FAST_SHADOW_ENTRY',%s,%s,%s::jsonb)",(snapshot.observed_at,snapshot.token_id,arm,payload))
            return position_id

async def due_qualification_jobs(limit=12):
    if not settings.database_url:return []
    import psycopg
    from psycopg.rows import dict_row
    async with await psycopg.AsyncConnection.connect(settings.database_url,row_factory=dict_row) as db:
        cur=await db.execute("SELECT * FROM qualification_jobs WHERE status='pending' AND due_at<=NOW() AND COALESCE(next_attempt_at,due_at)<=NOW() ORDER BY due_at LIMIT %s",(limit,))
        return await cur.fetchall()

async def qualification_pressure():
    """Entry-critical queue pressure used to protect scarce provider calls."""
    if not settings.database_url:return {"due":0,"due_soon":0,"oldest_late_seconds":0.0}
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        cur=await db.execute("SELECT count(*) FILTER(WHERE status='pending' AND due_at<=NOW() AND COALESCE(next_attempt_at,due_at)<=NOW()),count(*) FILTER(WHERE status='pending' AND due_at<=NOW()+interval '90 seconds' AND COALESCE(next_attempt_at,due_at)<=NOW()+interval '90 seconds'),COALESCE(EXTRACT(EPOCH FROM (NOW()-min(due_at) FILTER(WHERE status='pending' AND due_at<=NOW()))),0) FROM qualification_jobs")
        r=await cur.fetchone();return {"due":r[0],"due_soon":r[1],"oldest_late_seconds":float(r[2] or 0)}

async def qualification_health():
    """Read-only lifecycle diagnostics for the >=15m entry queue."""
    if not settings.database_url:return {"waiting":0,"due":0,"done":0,"retried":0,"oldest_late_seconds":0.0,"next_due_at":None}
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        cur=await db.execute("SELECT count(*) FILTER(WHERE status='pending' AND due_at>NOW()),count(*) FILTER(WHERE status='pending' AND due_at<=NOW()),count(*) FILTER(WHERE status='done'),count(*) FILTER(WHERE attempts>0),COALESCE(EXTRACT(EPOCH FROM (NOW()-min(due_at) FILTER(WHERE status='pending' AND due_at<=NOW()))),0),min(due_at) FILTER(WHERE status='pending' AND due_at>NOW()) FROM qualification_jobs")
        r=await cur.fetchone();return {"waiting":r[0],"due":r[1],"done":r[2],"retried":r[3],"oldest_late_seconds":float(r[4] or 0),"next_due_at":r[5]}

async def complete_qualification_job(job_id):
    if not settings.database_url:return
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        await db.execute("UPDATE qualification_jobs SET status='done',completed_at=NOW(),last_error=NULL,next_attempt_at=NULL WHERE id=%s AND status='pending'",(job_id,))

async def defer_qualification_job(job_id,minutes=2,error=None):
    if not settings.database_url:return
    import psycopg
    async with await psycopg.AsyncConnection.connect(settings.database_url) as db:
        await db.execute("UPDATE qualification_jobs SET next_attempt_at=NOW()+(%s * interval '1 minute'),attempts=attempts+1,last_error=%s WHERE id=%s AND status='pending'",(minutes,error,job_id))
