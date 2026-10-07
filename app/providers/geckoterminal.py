import httpx
from app.providers.base import DiscoveryProvider
from app.core.models import TokenSnapshot

class GeckoTerminalDiscovery(DiscoveryProvider):
    BASE="https://api.geckoterminal.com/api/v2"; NETWORKS=("solana","eth","base","bsc")
    def __init__(self): self.last_diagnostics={}
    async def discover(self):
        out=[];diag={}
        async with httpx.AsyncClient(timeout=15,headers={"Accept":"application/json","User-Agent":"JevDesk/0.6"}) as c:
            for network in self.NETWORKS:
                try:
                    r=await c.get(f"{self.BASE}/networks/{network}/new_pools",params={"page":1});diag[network]={"http":r.status_code,"bytes":len(r.content)};r.raise_for_status()
                    rows=r.json().get("data",[]);diag[network]["rows"]=len(rows)
                    for row in rows[:20]:
                        s=self._snapshot(network,row)
                        if s:out.append(s)
                except Exception as e:diag.setdefault(network,{})["error"]=f"{type(e).__name__}: {str(e)[:180]}"
        self.last_diagnostics=diag;return out
    async def fetch_pool(self,network,pool_id):
        pool_address=(pool_id or "").split("_",1)[-1]
        if not pool_address:return None
        async with httpx.AsyncClient(timeout=15,headers={"Accept":"application/json","User-Agent":"JevDesk/0.6"}) as c:
            r=await c.get(f"{self.BASE}/networks/{network}/pools/{pool_address}")
            if r.status_code==429:raise RuntimeError("provider_rate_limited_429")
            r.raise_for_status();row=r.json().get("data")
            return self._snapshot(network,row) if row else None
    def _snapshot(self,network,row):
        a=row.get("attributes",{});rel=row.get("relationships",{});token=(rel.get("base_token") or {}).get("data") or {};addr=(token.get("id") or "").split("_",1)[-1]
        if not addr:return None
        vol=a.get("volume_usd") or {};tx=(a.get("transactions") or {}).get("h24") or {}
        return TokenSnapshot(token_id=f"{network}:{addr}",address=addr,chain=network,ticker=a.get("name") or addr[:8],price_usd=_f(a.get("base_token_price_usd")),liquidity_usd=_f(a.get("reserve_in_usd")),volume_h24_usd=_f(vol.get("h24")),mcap_usd=_f(a.get("market_cap_usd") or a.get("fdv_usd")),trades_h24=_i(tx.get("buys"))+_i(tx.get("sells")),raw={"source":"geckoterminal","pool_id":row.get("id"),"pool_created_at":a.get("pool_created_at")})
def _f(v):
    try:return float(v) if v is not None else None
    except:return None
def _i(v):
    try:return int(v or 0)
    except:return 0
