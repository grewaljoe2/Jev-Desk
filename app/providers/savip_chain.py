"""Bounded CHAIN CUT fact providers. Shadow research only."""
import base64,struct,httpx

class SavipChainProvider:
    SOL_RPC="https://api.mainnet-beta.solana.com"
    HONEYPOT="https://api.honeypot.is/v2/IsHoneypot"
    TOP_HOLDERS="https://api.honeypot.is/v1/TopHolders"
    CHAIN_ID={"eth":1,"bsc":56,"base":8453}
    def __init__(self):self.client=httpx.AsyncClient(timeout=20,headers={"Accept":"application/json","User-Agent":"JevDesk/0.6.3"})

    async def fetch(self,chain,address):
        if chain=="solana":return await self._solana(address)
        if chain in self.CHAIN_ID:return await self._evm(chain,address)
        return None

    async def _rpc(self,method,params):
        r=await self.client.post(self.SOL_RPC,json={"jsonrpc":"2.0","id":1,"method":method,"params":params});r.raise_for_status()
        j=r.json()
        if j.get("error"):raise RuntimeError(f"solana_rpc:{j['error'].get('code')}")
        return j.get("result")

    async def _solana(self,mint):
        supply=await self._rpc("getTokenSupply",[mint,{"commitment":"confirmed"}])
        largest=await self._rpc("getTokenLargestAccounts",[mint,{"commitment":"confirmed"}])
        acct=await self._rpc("getAccountInfo",[mint,{"encoding":"base64","commitment":"confirmed"}])
        total=int((supply or {}).get("value",{}).get("amount") or 0)
        vals=(largest or {}).get("value") or []
        amounts=[int(x.get("amount") or 0) for x in vals]
        top=amounts[0]/total if total and amounts else None
        top10=sum(amounts[:10])/total if total else None
        data=((acct or {}).get("value") or {}).get("data") or []
        authority_open=None
        if data:
            raw=base64.b64decode(data[0])
            # SPL Token Mint layout: mint-authority option at 0, freeze-authority option at 46.
            if len(raw)>=82:
                mint_opt=struct.unpack_from("<I",raw,0)[0];freeze_opt=struct.unpack_from("<I",raw,46)[0]
                authority_open=bool(mint_opt or freeze_opt)
        # Standard RPC has no cheap exact distinct-holder count; fail closed until a holder-index provider supplies it.
        return {"top_wallet_fraction":top,"top10_fraction":top10,"holders":None,"authority_open":authority_open,"honeypot":None,"source":"solana_rpc"}

    async def _evm(self,chain,address):
        r=await self.client.get(self.HONEYPOT,params={"address":address,"chainID":self.CHAIN_ID[chain]});r.raise_for_status();j=r.json()
        h=await self.client.get(self.TOP_HOLDERS,params={"address":address,"chainID":self.CHAIN_ID[chain]});h.raise_for_status();hj=h.json()
        hp=(j.get("honeypotResult") or {}).get("isHoneypot")
        holders=(j.get("token") or {}).get("totalHolders")
        total=int(hj.get("totalSupply") or 0);balances=[int(x.get("balance") or 0) for x in (hj.get("holders") or [])]
        top=balances[0]/total if total and balances else None;top10=sum(balances[:10])/total if total else None
        return {"top_wallet_fraction":top,"top10_fraction":top10,"holders":int(holders) if holders is not None else None,"authority_open":None,"honeypot":hp if chain=="bsc" else None,"source":"honeypot.is"}
