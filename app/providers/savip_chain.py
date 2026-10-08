"""Savip Solana top-wallet helper. Fail closed on RPC limits; shadow only."""
import asyncio
import time
import httpx

class SavipChainProvider:
    SOL_RPC="https://api.mainnet-beta.solana.com"
    def __init__(self):
        self.client=httpx.AsyncClient(timeout=20,headers={"Accept":"application/json","User-Agent":"JevDesk/0.6.3"})
        self._lock=asyncio.Lock()
        self._next_call_at=0.0
        self._cooldown_until=0.0
    def cooling_down(self):
        return time.monotonic()<self._cooldown_until
    async def fetch(self,chain,address):
        if chain!="solana":return None
        # A failed RPC must never be interpreted as a clean wallet check.
        if self.cooling_down():
            raise RuntimeError("solana_rpc_cooldown_429")
        supply=await self._rpc("getTokenSupply",[address,{"commitment":"confirmed"}])
        largest=await self._rpc("getTokenLargestAccounts",[address,{"commitment":"confirmed"}])
        total=int((supply or {}).get("value",{}).get("amount") or 0)
        vals=(largest or {}).get("value") or []
        if total<=0 or not vals:
            raise RuntimeError("solana_rpc_unverified_supply_or_accounts")
        # Resolve owners for the largest token accounts. This remains a lower
        # bound on owner concentration because an owner may have other accounts.
        accounts=[x.get("address") for x in vals if x.get("address")]
        if len(accounts)!=len(vals):
            raise RuntimeError("solana_rpc_missing_token_account")
        details=await self._rpc("getMultipleAccounts",[accounts,{"encoding":"jsonParsed","commitment":"confirmed"}])
        info=(details or {}).get("value") or []
        if len(info)!=len(accounts):
            raise RuntimeError("solana_rpc_account_lookup_incomplete")
        owners={}
        for item,entry in zip(info,vals):
            parsed=(((item or {}).get("data") or {}).get("parsed") or {})
            details_info=parsed.get("info") or {}
            owner=details_info.get("owner")
            amount=details_info.get("tokenAmount") or {}
            if not owner or str(amount.get("amount"))!=str(entry.get("amount")):
                raise RuntimeError("solana_rpc_owner_unverified")
            owners[owner]=owners.get(owner,0)+int(entry["amount"])
        # No full-owner coverage from largest-account sampling: do not report
        # a verified top-wallet fraction or allow CHAIN approval from it.
        return {"top_wallet_fraction":None,"largest_sampled_owner_fraction":max(owners.values())/total,"sampled_token_accounts":len(accounts),"owner_coverage_complete":False,"source":"solana_rpc_owner_sample"}
    async def _rpc(self,method,params):
        async with self._lock:
            now=time.monotonic()
            if now<self._cooldown_until:
                raise RuntimeError("solana_rpc_cooldown_429")
            delay=self._next_call_at-now
            if delay>0:await asyncio.sleep(delay)
            r=await self.client.post(self.SOL_RPC,json={"jsonrpc":"2.0","id":1,"method":method,"params":params})
            self._next_call_at=time.monotonic()+2.0
            if r.status_code==429:
                retry=120.0
                try:retry=max(60.0,min(900.0,float(r.headers.get("Retry-After","120"))))
                except (TypeError,ValueError):pass
                self._cooldown_until=time.monotonic()+retry
                raise RuntimeError("solana_rpc_rate_limited_429")
            r.raise_for_status()
            j=r.json()
            if j.get("error"):
                code=j["error"].get("code")
                if code==429 or code==-32005:
                    self._cooldown_until=time.monotonic()+120.0
                    raise RuntimeError("solana_rpc_rate_limited_429")
                raise RuntimeError(f"solana_rpc:{code}")
            return j.get("result")
