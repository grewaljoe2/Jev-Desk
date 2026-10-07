import httpx
from app.providers.base import DiscoveryProvider
from app.core.models import TokenSnapshot

class GeckoTerminalDiscovery(DiscoveryProvider):
    """Public-data discovery adapter. No wallet/order capability."""
    BASE="https://api.geckoterminal.com/api/v2"
    NETWORKS=("solana","eth","base","bsc")

    async def discover(self)->list[TokenSnapshot]:
        out=[]
        async with httpx.AsyncClient(timeout=15,headers={"Accept":"application/json"}) as c:
            for network in self.NETWORKS:
                try:
                    r=await c.get(f"{self.BASE}/networks/{network}/new_pools",params={"page":1})
                    r.raise_for_status()
                    for row in r.json().get("data",[])[:20]:
                        a=row.get("attributes",{})
                        rel=row.get("relationships",{})
                        token=(rel.get("base_token") or {}).get("data") or {}
                        addr=(token.get("id") or "").split("_",1)[-1]
                        if not addr: continue
                        vol=(a.get("volume_usd") or {})
                        tx=(a.get("transactions") or {}).get("h24") or {}
                        out.append(TokenSnapshot(
                            token_id=f"{network}:{addr}",address=addr,chain=network,
                            ticker=a.get("name") or addr[:8],
                            liquidity_usd=_f(a.get("reserve_in_usd")),
                            volume_h24_usd=_f(vol.get("h24")),
                            mcap_usd=_f(a.get("market_cap_usd") or a.get("fdv_usd")),
                            trades_h24=_i(tx.get("buys"))+_i(tx.get("sells")),
                            raw={"source":"geckoterminal","pool_id":row.get("id"),"pool_created_at":a.get("pool_created_at")}
                        ))
                except Exception as e:
                    # Provider errors are observable; never fabricate market facts.
                    continue
        return out

def _f(v):
    try:return float(v) if v is not None else None
    except:return None
def _i(v):
    try:return int(v or 0)
    except:return 0
