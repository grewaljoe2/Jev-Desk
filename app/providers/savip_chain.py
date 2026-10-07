"""Savip Solana top-wallet helper matching the published collector. Shadow only."""
import httpx

class SavipChainProvider:
    SOL_RPC="https://api.mainnet-beta.solana.com"
    def __init__(self):self.client=httpx.AsyncClient(timeout=20,headers={"Accept":"application/json","User-Agent":"JevDesk/0.6.3"})
    async def fetch(self,chain,address):
        if chain!="solana":return None
        supply=await self._rpc("getTokenSupply",[address,{"commitment":"confirmed"}])
        largest=await self._rpc("getTokenLargestAccounts",[address,{"commitment":"confirmed"}])
        total=int((supply or {}).get("value",{}).get("amount") or 0)
        vals=(largest or {}).get("value") or [];amounts=[int(x.get("amount") or 0) for x in vals]
        return {"top_wallet_fraction":amounts[0]/total if total and amounts else None,"source":"solana_rpc"}
    async def _rpc(self,method,params):
        r=await self.client.post(self.SOL_RPC,json={"jsonrpc":"2.0","id":1,"method":method,"params":params});r.raise_for_status();j=r.json()
        if j.get("error"):raise RuntimeError(f"solana_rpc:{j['error'].get('code')}")
        return j.get("result")
