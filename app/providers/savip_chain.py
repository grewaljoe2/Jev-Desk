"""Savip Solana top-wallet helper. Fail closed on RPC limits; shadow only."""
import asyncio
import time
import os
import httpx
from app.research.solana_owner_evidence_pipeline import collect_independently_confirmed_owner_evidence

class SavipChainProvider:
    SOL_RPC="https://api.mainnet-beta.solana.com"
    # Public, no-key secondary route; never used to authorize owner coverage.
    FALLBACK_RPC="https://public.rpc.solanavibestation.com/"
    def __init__(self):
        self.client=httpx.AsyncClient(timeout=20,headers={"Accept":"application/json","User-Agent":"JevDesk/0.6.3"})
        self._lock=asyncio.Lock()
        self._next_call_at=0.0
        self._cooldown_until=0.0
        self._active_rpc=self.SOL_RPC
    def cooling_down(self):
        return time.monotonic()<self._cooldown_until
    async def fetch(self,chain,address):
        if chain!="solana":return None
        # A failed RPC must never be interpreted as a clean wallet check.
        if self.cooling_down():
            raise RuntimeError("solana_rpc_cooldown_429")
        if self._active_rpc==self.FALLBACK_RPC and time.monotonic()>=self._cooldown_until and self._cooldown_until>0:
            self._active_rpc=self.SOL_RPC
            self._cooldown_until=0.0
        try:
            supply=await self._rpc("getTokenSupply",[address,{"commitment":"confirmed"}])
            largest=await self._rpc("getTokenLargestAccounts",[address,{"commitment":"confirmed"}])
        except RuntimeError as exc:
            if str(exc)!="solana_rpc_primary_rate_limited_fallback_selected_429":
                raise
            # One bounded immediate failover, never a retry loop. Restart both
            # observations on the same provider after switching endpoints.
            supply=await self._rpc("getTokenSupply",[address,{"commitment":"confirmed"}])
            largest=await self._rpc("getTokenLargestAccounts",[address,{"commitment":"confirmed"}])
        total=int((supply or {}).get("value",{}).get("amount") or 0)
        vals=(largest or {}).get("value") or [];amounts=[int(x.get("amount") or 0) for x in vals]
        # Largest token *accounts* do not prove wallet-owner concentration.
        # Preserve this as a lower-bound observation, never a verified pass.
        return {"top_wallet_fraction":None,"largest_token_account_fraction":amounts[0]/total if total and amounts else None,"owner_coverage_complete":False,"source":"solana_rpc_token_accounts_unverified"}

    async def fetch_independent_owner_evidence(self,address):
        """Bounded read-only two-provider verification; never trusts single-RPC claims.

        Fail closed on unavailable/mismatched evidence. Concentration rejection
        may use independently reconciled balances, but only a verified complete
        owner map is eligible to set the production owner-coverage flag.
        """
        try:
            result=await collect_independently_confirmed_owner_evidence(address)
        except Exception:
            return {"owner_coverage_complete":False,"status":"evidence_exception",
                    "source":"solana_independent_owner_evidence"}
        confirmed=(result.get("cross_provider_owner_match") is True
                   and result.get("positive_balance_coverage_proven") is True
                   and result.get("status")=="independently_correlated_research")
        fraction=result.get("largest_owner_fraction")
        if not confirmed or type(fraction) not in (int,float) or not (0<=fraction<=1):
            return {"owner_coverage_complete":False,"status":result.get("status","invalid_evidence"),
                    "source":"solana_independent_owner_evidence",
                    "primary_status":result.get("primary_status"),"secondary_status":result.get("secondary_status"),
                    "failed_provider":result.get("failed_provider")}
        holders=result.get("holder_count")
        top10=result.get("top_10_percent")
        if type(holders) is not int or holders<1 or type(top10) not in (int,float) or not (0<=top10<=100):
            return {"owner_coverage_complete":False,"status":"missing_reconciled_concentration",
                    "source":"solana_independent_owner_evidence"}
        return {"owner_coverage_complete":True,"top_wallet_fraction":float(fraction),
                "holder_count":holders,"top_10_percent":float(top10),
                "status":"independently_verified","source":"solana_independent_owner_evidence"}

    async def fetch_helius_owner_evidence(self,address):
        """Bounded real-candidate Helius scan. Diagnostic only, never a wallet pass."""
        from app.research.solana_helius_cursor_research import collect_cursor_owner_research
        key=os.environ.get("HELIUS_API_KEY")
        if not key:
            return {"status":"helius_not_configured","owner_coverage_complete":False}
        try:
            result=await collect_cursor_owner_research(address,api_key=key,max_pages=20,
                                                       page_size=1000,timeout_seconds=10)
            return {"status":result.get("status","invalid_evidence"),
                    "token_accounts":result.get("token_accounts"),
                    "holder_count":result.get("holder_count"),
                    "slot_stable":result.get("slot_stable"),
                    "owner_coverage_complete":False}
        except Exception:
            return {"status":"helius_evidence_exception","owner_coverage_complete":False}

    async def _rpc(self,method,params):
        async with self._lock:
            now=time.monotonic()
            if now<self._cooldown_until:
                raise RuntimeError("solana_rpc_cooldown_429")
            delay=self._next_call_at-now
            if delay>0:await asyncio.sleep(delay)
            r=await self.client.post(self._active_rpc,json={"jsonrpc":"2.0","id":1,"method":method,"params":params})
            self._next_call_at=time.monotonic()+2.0
            if r.status_code==429:
                retry=120.0
                try:retry=max(60.0,min(900.0,float(r.headers.get("Retry-After","120"))))
                except (TypeError,ValueError):pass
                if self._active_rpc==self.SOL_RPC:
                    self._active_rpc=self.FALLBACK_RPC
                    self._next_call_at=time.monotonic()+2.0
                    raise RuntimeError("solana_rpc_primary_rate_limited_fallback_selected_429")
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
