import asyncio,time,httpx
from email.utils import parsedate_to_datetime
from datetime import datetime,timezone
from app.providers.base import DiscoveryProvider
from app.core.models import TokenSnapshot

class GeckoTerminalDiscovery(DiscoveryProvider):
    BASE="https://api.geckoterminal.com/api/v2"; NETWORKS=("solana","eth","base","bsc")
    DISCOVERY_SEQUENCE=("solana","bsc","solana","base","solana","bsc","solana","eth")
    def __init__(self): self.last_diagnostics={};self._lock=asyncio.Lock();self._next_call_at=0.0;self._entry_pressure=False;self._last_429_at=0.0;self._discovery_index=0;self._client=httpx.AsyncClient(timeout=15,headers={"Accept":"application/json","User-Agent":"JevDesk/0.6.2"})
    async def _get(self,url,params=None):
        async with self._lock:
            wait=self._next_call_at-time.monotonic()
            if wait>0:await asyncio.sleep(wait)
            r=await self._client.get(url,params=params)
            self._next_call_at=time.monotonic()+6.5
            if r.status_code==429:
                self._last_429_at=time.monotonic()
                retry_after=60.0
                raw=r.headers.get("Retry-After")
                if raw:
                    try: retry_after=max(retry_after,float(raw))
                    except ValueError:
                        try: retry_after=max(retry_after,(parsedate_to_datetime(raw)-datetime.now(timezone.utc)).total_seconds())
                        except Exception: pass
                self._next_call_at=max(self._next_call_at,time.monotonic()+max(1.0,retry_after))
                raise RuntimeError("provider_rate_limited_429")
            return r
    def set_entry_pressure(self,active): self._entry_pressure=bool(active)
    async def discover(self):
        """Spend one discovery call per tick using a fixed evidence-based chain allocation."""
        if self._entry_pressure:
            self.last_diagnostics={"skipped":"entry_pressure"};return []
        network=self.DISCOVERY_SEQUENCE[self._discovery_index%len(self.DISCOVERY_SEQUENCE)]
        slot=self._discovery_index%len(self.DISCOVERY_SEQUENCE)
        self._discovery_index=(self._discovery_index+1)%len(self.DISCOVERY_SEQUENCE)
        out=[];diag={"mode":"weighted_fast_v1","network":network,"slot":slot,"sequence_length":len(self.DISCOVERY_SEQUENCE)}
        try:
            r=await self._get(f"{self.BASE}/networks/{network}/new_pools",params={"page":1});diag.update({"http":r.status_code,"bytes":len(r.content)});r.raise_for_status()
            rows=r.json().get("data",[]);diag["rows"]=len(rows)
            for row in rows[:20]:
                s=self._snapshot(network,row)
                if s:out.append(s)
        except Exception as e:diag["error"]=f"{type(e).__name__}: {str(e)[:180]}"
        self.last_diagnostics=diag;return out
    async def fetch_pools(self,network,pool_ids):
        """Fetch up to 30 same-network pools in one public API request."""
        ids=[p for p in pool_ids if p]
        addresses=[p.split("_",1)[-1] for p in ids][:30]
        if not addresses:return {}
        r=await self._get(f"{self.BASE}/networks/{network}/pools/multi/{','.join(addresses)}")
        r.raise_for_status();rows=r.json().get("data",[]) or []
        out={}
        for row in rows:
            snap=self._snapshot(network,row)
            if snap:out[row.get("id")]=snap
        return out
    async def fetch_pool(self,network,pool_id):
        pool_address=(pool_id or "").split("_",1)[-1]
        if not pool_address:return None
        r=await self._get(f"{self.BASE}/networks/{network}/pools/{pool_address}")
        r.raise_for_status();row=r.json().get("data")
        return self._snapshot(network,row) if row else None
    def _snapshot(self,network,row):
        a=row.get("attributes",{});rel=row.get("relationships",{});token=(rel.get("base_token") or {}).get("data") or {};addr=(token.get("id") or "").split("_",1)[-1]
        if not addr:return None
        vol=a.get("volume_usd") or {};tx=(a.get("transactions") or {}).get("h24") or {}
        created=a.get("pool_created_at");age=None
        if created:
            try:age=max(0.0,(datetime.now(timezone.utc)-datetime.fromisoformat(str(created).replace("Z","+00:00"))).total_seconds()/60.0)
            except:pass
        return TokenSnapshot(token_id=f"{network}:{addr}",address=addr,chain=network,ticker=a.get("name") or addr[:8],price_usd=_f(a.get("base_token_price_usd")),age_minutes=age,liquidity_usd=_f(a.get("reserve_in_usd")),volume_h24_usd=_f(vol.get("h24")),mcap_usd=_f(a.get("market_cap_usd") or a.get("fdv_usd")),trades_h24=_i(tx.get("buys"))+_i(tx.get("sells")),raw={"source":"geckoterminal","pool_id":row.get("id"),"pool_created_at":a.get("pool_created_at")})
def _f(v):
    try:return float(v) if v is not None else None
    except:return None
def _i(v):
    try:return int(v or 0)
    except:return 0
