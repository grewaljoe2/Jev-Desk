import httpx

class DexScreenerProvider:
    BASE="https://api.dexscreener.com/latest/dex/pairs"
    CHAIN={"solana":"solana","eth":"ethereum","base":"base","bsc":"bsc"}
    def __init__(self):self._client=httpx.AsyncClient(timeout=15,headers={"Accept":"application/json","User-Agent":"JevDesk/0.6.2"})
    async def fetch_pairs(self,chain,pool_ids):
        """One chain-specific request for up to 20 exact pair addresses."""
        cid=self.CHAIN.get(chain)
        pairs=[(p or "").split("_",1)[-1] for p in pool_ids]
        if not cid or not pairs or len(pairs)>20 or any(not p or "," in p or "/" in p for p in pairs):
            raise ValueError("invalid_dex_batch")
        r=await self._client.get(f"{self.BASE}/{cid}/{\",\".join(pairs)}")
        r.raise_for_status()
        rows=r.json().get("pairs") or []
        by_pair={str(x.get("pairAddress","")).lower():x for x in rows if x.get("pairAddress")}
        return [self._parse_pair(pair,by_pair.get(pair.lower())) for pair in pairs]
    async def fetch_pair(self,chain,pool_id):
        pair=(pool_id or "").split("_",1)[-1];cid=self.CHAIN.get(chain)
        if not cid or not pair:return None
        r=await self._client.get(f"{self.BASE}/{cid}/{pair}");r.raise_for_status();rows=r.json().get("pairs") or []
        x=next((p for p in rows if str(p.get("pairAddress","")).lower()==pair.lower()),None)
        return self._parse_pair(pair,x)
    @staticmethod
    def _parse_pair(pair,x):
        if x is None:return {"pair_found":False,"requested_pair":pair,"source":"dexscreener"}
        tx=x.get("txns") or {};h1=tx.get("h1") or {};h24=tx.get("h24") or {};liq=x.get("liquidity") or {};vol=x.get("volume") or {}
        return {"pair_found":True,"liquidity_usd":_f(liq.get("usd")),"buys_h1":_i(h1.get("buys")),"sells_h1":_i(h1.get("sells")),"trades_h24":_tx_total(h24),"pair_address":x.get("pairAddress"),"price_usd":_f(x.get("priceUsd")),"volume_h6_usd":_f(vol.get("h6")),"volume_h24_usd":_f(vol.get("h24")),"source":"dexscreener"}
def _f(v):
    try:return float(v) if v is not None else None
    except:return None
def _i(v):
    try:return int(v) if v is not None else None
    except:return None
def _tx_total(bucket):
    b=_i((bucket or {}).get("buys"));s=_i((bucket or {}).get("sells"))
    return None if b is None or s is None else b+s
