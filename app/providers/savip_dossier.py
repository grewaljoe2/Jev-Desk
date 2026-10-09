"""Savip dossier facts matching the published collector. Shadow research only."""
import httpx
import time

class SavipDossierProvider:
    GT="https://api.geckoterminal.com/api/v2"
    NET={"solana":"solana","bsc":"bsc","base":"base","eth":"eth"}
    def __init__(self,gt_provider=None):
        self.client=httpx.AsyncClient(timeout=20,headers={"Accept":"application/json","User-Agent":"JevDesk/0.6.3"})
        self.gt_provider=gt_provider
        self._cache={}
        self.cache_ttl_seconds=300
    async def fetch(self,chain,address):
        net=self.NET.get(chain)
        if not net:return None
        key=(net,address)
        now=time.monotonic()
        cached=self._cache.get(key)
        if cached and cached[0]>now:
            return dict(cached[1])
        url=f"{self.GT}/networks/{net}/tokens/{address}/info"
        r=await self.gt_provider._get(url) if self.gt_provider else await self.client.get(url)
        r.raise_for_status()
        a=((r.json().get("data") or {}).get("attributes") or {})
        holders=a.get("holders") or {};dist=holders.get("distribution_percentage") or {}
        result={
          "holder_count":holders.get("count"),
          "top_10_percent":dist.get("top_10"),
          "top_10_source":"geckoterminal.holders.distribution_percentage.top_10",
          "top_10_exclusions_verified":False,
          "developer_holding_percentage":a.get("developer_holding_percentage"),
          "gt_score_details":a.get("gt_score_details"),
          "is_honeypot":a.get("is_honeypot"),
          "mint_authority":a.get("mint_authority"),
          "freeze_authority":a.get("freeze_authority"),
          "description":a.get("description"),
          "x_handle":clean_handle(a.get("twitter_handle")),
          "source":"geckoterminal_info",
        }
        self._cache={k:v for k,v in self._cache.items() if v[0]>now}
        self._cache[key]=(time.monotonic()+self.cache_ttl_seconds,result)
        return dict(result)

def clean_handle(h):
    if not h:return None
    h=str(h).strip().lstrip("@").split("?")[0].split("/")[0]
    return h if h and h.replace("_","").isalnum() and len(h)<=15 else None
