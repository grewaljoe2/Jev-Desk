"""Bounded atomic Solana mint + token-account snapshot, research-only.

Discover account addresses first, then read mint and up to 99 token accounts
in ONE getMultipleAccounts response. Never infer completeness merely from
discovery; conservation against the mint supply at that same response slot
is mandatory. This path intentionally does not authorize production CHAIN.
"""
import base64
import httpx
from app.research.solana_rpc_owner_decoder import SUPPORTED, TOKEN_PROGRAM, decode_mint_account, decode_token_account
from app.research.solana_owner_reconciliation import reconcile_owner_balances

async def collect_atomic_small_mint(mint, *, rpc_url="https://api.mainnet-beta.solana.com", transport=None, timeout=15):
    denied={"status":"atomic_evidence_unavailable","chain_pass_allowed":False,"owner_coverage_complete":False}
    if not isinstance(mint,str) or not mint:
        return denied
    async def rpc(client,method,params):
        response=await client.post(rpc_url,json={"jsonrpc":"2.0","id":1,"method":method,"params":params})
        response.raise_for_status()
        if len(response.content)>2_000_000:
            raise ValueError("oversized_response")
        body=response.json()
        if not isinstance(body,dict) or "error" in body or not isinstance(body.get("result"),dict):
            raise ValueError("invalid_rpc")
        return body["result"]
    try:
        async with httpx.AsyncClient(timeout=timeout,transport=transport) as client:
            info=await rpc(client,"getAccountInfo",[mint,{"encoding":"base64","commitment":"confirmed"}])
            mint_account=info.get("value")
            if not isinstance(mint_account,dict) or mint_account.get("owner") not in SUPPORTED:
                return {**denied,"status":"invalid_mint"}
            program=mint_account["owner"]
            filters=[{"memcmp":{"offset":0,"bytes":mint}}]
            if program==TOKEN_PROGRAM:
                filters.insert(0,{"dataSize":165})
            discovery=await rpc(client,"getProgramAccounts",[program,{"encoding":"base64","commitment":"confirmed","withContext":True,"filters":filters,"dataSlice":{"offset":0,"length":0}}])
            accounts=discovery.get("value")
            if not isinstance(accounts,list) or len(accounts)>99:
                return {**denied,"status":"atomic_account_limit"}
            addresses=[item.get("pubkey") for item in accounts if isinstance(item,dict)]
            if len(addresses)!=len(accounts) or any(not isinstance(a,str) or not a for a in addresses) or len(set(addresses))!=len(addresses):
                return {**denied,"status":"invalid_discovery"}
            result=await rpc(client,"getMultipleAccounts",[[mint]+addresses,{"encoding":"base64","commitment":"confirmed"}])
            slot=(result.get("context") or {}).get("slot")
            values=result.get("value")
            if type(slot) is not int or slot<0 or not isinstance(values,list) or len(values)!=len(addresses)+1:
                return {**denied,"status":"invalid_atomic_response"}
            mint_data=decode_mint_account(values[0],program=program)
            mint_raw=base64.b64decode(values[0]["data"][0],validate=True)
            mint_authority_open=int.from_bytes(mint_raw[0:4],"little")==1
            freeze_authority_open=int.from_bytes(mint_raw[46:50],"little")==1
            rows=[]
            for address,value in zip(addresses,values[1:]):
                if value is None:
                    continue
                rows.append(decode_token_account({"pubkey":address,"account":value},mint=mint,program=program,slot=slot))
            snapshot={"slot":slot,"rows":rows,"owner_coverage_complete":False}
            outcome=reconcile_owner_balances(snapshot,mint=mint,program=program,
                                             supply_amount=mint_data["amount"],supply_slot=slot)
            return {**outcome,"status":"atomic_research_"+str(outcome.get("status")),
                    "atomic_snapshot_slot":slot,"discovered_accounts":len(addresses),
                    "mint_authority":mint_authority_open,"freeze_authority":freeze_authority_open,
                    "chain_pass_allowed":False,"owner_coverage_complete":False}
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError, UnicodeError):
        return {**denied,"status":"atomic_rpc_or_decode_error"}
