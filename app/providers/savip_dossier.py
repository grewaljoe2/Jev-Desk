"""Savip dossier facts matching the published collector. Shadow research only."""
import asyncio
import httpx\nimport time

class SavipDossierProvider:
    GT="https://api.geckoterminal.com/api/v2"
    NET={"solana":"solana","bsc":"bsc","base":"base","eth":"eth"}
    def __init__(self):\n        self.client=httpx.AsyncClient(timeout=20,headers={"Accept":"application/json","User-Agent":"JevDesk/0.6.3"})\n        self._lock=asyncio.Lock();self._next_gt_at=0.0
    async def fetch(self,chain,address):
        net=self.NET.get(chain)
        if not net:return None
        r=await self.client.get(f"{self.GT}/networks/{net}/tokens/{address}/info")
        if r.status_code==429:
            await asyncio.sleep(7)
            r=await self.client.get(f"{self.GT}/networks/{net}/tokens/{address}/info")
        r.raise_for_status()
        a=((r.json().get("data") or {}).get("attributes") or {})
        holders=a.get("holders") or {};dist=holders.get("distribution_percentage") or {}
        return {
          "holder_count":holders.get("count"),
          "top_10_percent":dist.get("top_10"),
          "developer_holding_percentage":a.get("developer_holding_percentage"),
          "gt_score_details":a.get("gt_score_details"),
          "is_honeypot":a.get("is_honeypot"),
          "mint_authority":a.get("mint_authority"),
          "freeze_authority":a.get("freeze_authority"),
          "description":a.get("description"),
          "x_handle":clean_handle(a.get("twitter_handle")),
          "source":"geckoterminal_info",
        }

def clean_handle(h):
    if not h:return None
    h=str(h).strip().lstrip("@").split("?")[0].split("/")[0]
    return h if h and h.replace("_","").isalnum() and len(h)<=15 else None
