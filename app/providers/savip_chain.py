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
        """Verify stable full token-account ownership with independent RPC corroboration.

        Two complete cursor scans must match account-by-account; an independent
        RPC must corroborate supply, mint program, and largest account amounts.
        This is a cross-checked Helius map, not two independent full maps.
        """
        from app.research.solana_helius_cursor_research import collect_cursor_owner_research
        from app.research.solana_rpc_owner_decoder import TOKEN_PROGRAM, decode_mint_account
        key=os.environ.get("HELIUS_API_KEY")
        denied={"owner_coverage_complete":False,"chain_pass_allowed":False}
        if not key:return {**denied,"status":"helius_not_configured"}
        try:
            scans=[]
            for _ in range(2):
                scan=await collect_cursor_owner_research(address,api_key=key,max_pages=20,
                                                         page_size=1000,timeout_seconds=10)
                if scan.get("status")!="cursor_exhausted_unverified":
                    return {**denied,"status":scan.get("status","scan_failed")}
                scans.append(scan)
            first,second=scans
            fields=("account_balance_digest","owner_balance_digest","accounts_total",
                    "token_accounts","holder_count","largest_owner_amount","top_10_owner_amount")
            if any(first.get(field) is None or first.get(field)!=second.get(field) for field in fields):
                return {**denied,"status":"unstable_owner_map"}
            async with httpx.AsyncClient(timeout=12) as client:
                async def rpc(method,params):
                    response=await client.post(self.FALLBACK_RPC,json={
                        "jsonrpc":"2.0","id":1,"method":method,"params":params})
                    response.raise_for_status()
                    body=response.json()
                    if not isinstance(body,dict) or body.get("error") or not isinstance(body.get("result"),dict):
                        raise ValueError("invalid_independent_rpc")
                    return body["result"]
                info=await rpc("getAccountInfo",[address,{"encoding":"base64","commitment":"confirmed"}])
                value=info.get("value")
                if not isinstance(value,dict) or value.get("owner")!=TOKEN_PROGRAM:
                    return {**denied,"status":"unsupported_mint_program"}
                mint_data=decode_mint_account(value,program=TOKEN_PROGRAM)
                supply=await rpc("getTokenSupply",[address,{"commitment":"confirmed"}])
                sv=supply.get("value") or {}
                amount=sv.get("amount")
                if not isinstance(amount,str) or not amount.isdecimal() or type(sv.get("decimals")) is not int:
                    return {**denied,"status":"invalid_independent_supply"}
                total=int(amount)
                if total<=0 or total!=first["accounts_total"] or mint_data["amount"]!=total or mint_data["decimals"]!=sv["decimals"]:
                    return {**denied,"status":"independent_supply_mismatch"}
                largest=await rpc("getTokenLargestAccounts",[address,{"commitment":"confirmed"}])
                largest_rows=largest.get("value")
                if not isinstance(largest_rows,list) or not largest_rows:
                    return {**denied,"status":"independent_largest_unavailable"}
                amounts=[x.get("amount") for x in largest_rows]
                if any(not isinstance(x,str) or not x.isdecimal() for x in amounts):
                    return {**denied,"status":"invalid_independent_largest"}
                # Account-level amounts are a lower bound on owner concentration.
                # They must not exceed the maximum aggregated wallet amount.
                if max(map(int,amounts))>first["largest_owner_amount"]:
                    return {**denied,"status":"independent_largest_mismatch"}
            fraction=first["largest_owner_amount"]/total
            top10=100*first["top_10_owner_amount"]/total
            if not (0<=fraction<=1 and 0<=top10<=100) or first["holder_count"]<1:
                return {**denied,"status":"invalid_concentration"}
            return {"owner_coverage_complete":True,"chain_pass_allowed":True,
                    "status":"helius_double_scan_independent_supply_correlated",
                    "source":"helius_correlated_owner_evidence",
                    "top_wallet_fraction":fraction,"holder_count":first["holder_count"],
                    "top_10_percent":top10,"token_accounts":first["token_accounts"],
                    "owner_balance_digest":first["owner_balance_digest"]}
        except Exception:
            return {**denied,"status":"helius_verification_unavailable"}

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
