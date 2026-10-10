"""Bounded atomic Solana mint + token-account snapshot, research-only.

Discover account addresses first, then read mint and token accounts in
bounded getMultipleAccounts batches. Every batch MUST report the same slot.\nNever infer completeness merely from
discovery; conservation against the mint supply at that same response slot
is mandatory. This path intentionally does not authorize production CHAIN.
"""
import asyncio
import base64
import httpx
from app.research.solana_rpc_owner_decoder import SUPPORTED, TOKEN_PROGRAM, decode_mint_account, decode_token_account
from app.research.solana_owner_reconciliation import reconcile_owner_balances

class RpcRejected(Exception):
    """Sanitized JSON-RPC rejection category, never raw provider data."""
    pass

async def collect_atomic_small_mint(mint, *, rpc_url="https://api.mainnet-beta.solana.com", transport=None, timeout=15):
    denied={"status":"atomic_evidence_unavailable","chain_pass_allowed":False,"owner_coverage_complete":False}
    if not isinstance(mint,str) or not mint:
        return denied
    async def rpc(client,method,params):
        response=await client.post(rpc_url,json={"jsonrpc":"2.0","id":1,"method":method,"params":params})
        response.raise_for_status()
        if len(response.content)>2_000_000:
            raise RpcRejected("response_too_large")
        body=response.json()
        if isinstance(body,dict) and isinstance(body.get("error"),dict):
            code=body["error"].get("code")
            kind=("method_unsupported" if code==-32601 else
                  "provider_limit" if code in (-32005,-32004) else
                  "invalid_params" if code==-32602 else "provider_rejected")
            raise RpcRejected(kind)
        if not isinstance(body,dict) or not isinstance(body.get("result"),dict):
            raise ValueError("invalid_rpc")
        return body["result"]
    stage="getAccountInfo"
    try:
        async with httpx.AsyncClient(timeout=timeout,transport=transport) as client:
            info=await rpc(client,"getAccountInfo",[mint,{"encoding":"base64","commitment":"confirmed"}])
            mint_account=info.get("value")
            if not isinstance(mint_account,dict) or mint_account.get("owner") not in SUPPORTED:
                return {**denied,"status":"invalid_mint"}
            program=mint_account["owner"]
            # Token-2022 extensions can alter accounting semantics; scope the
            # first real-token canary to classic SPL until extension-aware proof.
            if program!=TOKEN_PROGRAM:
                return {**denied,"status":"token_2022_not_yet_supported"}
            filters=[{"memcmp":{"offset":0,"bytes":mint}}]
            if program==TOKEN_PROGRAM:
                filters.insert(0,{"dataSize":165})
            stage="getProgramAccounts"
            discovery=await rpc(client,"getProgramAccounts",[program,{"encoding":"base64","commitment":"confirmed","withContext":True,"filters":filters,"dataSlice":{"offset":0,"length":0}}])
            accounts=discovery.get("value")
            # A provider may serve an older snapshot after discovery; conservation
            # alone must not certify a snapshot older than the discovery context.
            discovery_slot=(discovery.get("context") or {}).get("slot")
            if type(discovery_slot) is not int or discovery_slot<0:
                return {**denied,"status":"invalid_discovery_slot"}
            if not isinstance(accounts,list) or len(accounts)>299:
                return {**denied,"status":"atomic_account_limit"}
            addresses=[item.get("pubkey") for item in accounts if isinstance(item,dict)]
            if len(addresses)!=len(accounts) or any(not isinstance(a,str) or not a for a in addresses) or len(set(addresses))!=len(addresses):
                return {**denied,"status":"invalid_discovery"}
            # Each RPC call is atomic, but multiple calls are NOT automatically
            # atomic together. Only reconcile if every batch reports one exact
            # slot, including the mint supply. No slot interpolation is allowed.
            batches=[[mint]+addresses[:99]]
            batches.extend(addresses[i:i+100] for i in range(99,len(addresses),100))
            # Issue bounded reads concurrently to improve the chance of a
            # shared bank slot. Concurrency never substitutes for the exact
            # slot check below; every response is independently validated.
            stage="getMultipleAccounts"
            results=await asyncio.gather(*(rpc(client,"getMultipleAccounts",
                [batch,{"encoding":"base64","commitment":"confirmed",
                        "minContextSlot":discovery_slot}]) for batch in batches))
            slot=None
            values=[]
            for batch,result in zip(batches,results):
                batch_slot=(result.get("context") or {}).get("slot")
                batch_values=result.get("value")
                if (type(batch_slot) is not int or batch_slot<discovery_slot
                    or not isinstance(batch_values,list) or len(batch_values)!=len(batch)):
                    return {**denied,"status":"invalid_atomic_response"}
                if slot is None:
                    slot=batch_slot
                elif slot!=batch_slot:
                    return {**denied,"status":"multi_batch_slot_mismatch"}
                values.extend(batch_values)
            if not isinstance(values[0],dict) or values[0].get("owner")!=program:
                return {**denied,"status":"mint_program_changed"}
            mint_data=decode_mint_account(values[0],program=program)
            mint_raw=base64.b64decode(values[0]["data"][0],validate=True)
            # SPL COption discriminants must be exactly 0 (None) or 1 (Some).
            # Malformed values must never be interpreted as revoked authorities.
            mint_authority_option=int.from_bytes(mint_raw[0:4],"little")
            freeze_authority_option=int.from_bytes(mint_raw[46:50],"little")
            if mint_authority_option not in (0,1) or freeze_authority_option not in (0,1):
                return {**denied,"status":"invalid_mint_authority_encoding"}
            mint_authority_open=mint_authority_option==1
            freeze_authority_open=freeze_authority_option==1
            rows=[]
            for address,value in zip(addresses,values[1:]):
                if value is None:
                    return {**denied,"status":"discovered_account_missing"}
                rows.append(decode_token_account({"pubkey":address,"account":value},mint=mint,program=program,slot=slot))
            snapshot={"slot":slot,"rows":rows,"owner_coverage_complete":False}
            outcome=reconcile_owner_balances(snapshot,mint=mint,program=program,
                                             supply_amount=mint_data["amount"],supply_slot=slot)
            return {**outcome,"status":"atomic_research_"+str(outcome.get("status")),
                    "atomic_snapshot_slot":slot,"discovered_accounts":len(addresses),
                    "mint_authority":mint_authority_open,"freeze_authority":freeze_authority_open,
                    "owner_balance_digest":outcome.get("owner_balance_digest"),
                    "chain_pass_allowed":False,"owner_coverage_complete":False}
    except RpcRejected as exc:
        return {**denied,"status":"atomic_rpc_"+str(exc),"rpc_method":stage}
    except httpx.HTTPStatusError as exc:
        code=exc.response.status_code
        category=("rate_limited" if code==429 else "forbidden" if code in (401,403)
                  else "server_error" if code>=500 else "http_error")
        return {**denied,"status":"atomic_rpc_"+category,"rpc_method":stage}
    except httpx.HTTPError:
        return {**denied,"status":"atomic_rpc_transport_error","rpc_method":stage}
    except (ValueError, TypeError, KeyError, IndexError, UnicodeError):
        return {**denied,"status":"atomic_rpc_decode_error","rpc_method":stage}

async def collect_full_sliced_snapshot(mint, *, rpc_url="https://api.mainnet-beta.solana.com",
                                       transport=None, timeout=25, max_accounts=20000):
    """Large classic-SPL mint: one contextual sliced account scan and same-slot mint.

    Bounded to 20k accounts / 6 MB; retries are read-only and fail closed.
    No live execution or independent proof is implied by this collector.
    """
    from app.research.solana_rpc_owner_decoder import decode_sliced_rpc_snapshot
    denied={"status":"full_snapshot_unverified","chain_pass_allowed":False,
            "owner_coverage_complete":False}
    if not isinstance(mint,str) or not mint or type(max_accounts) is not int or max_accounts>20000 or max_accounts<1:
        return denied
    async def rpc(client,method,params):
        response=await client.post(rpc_url,json={"jsonrpc":"2.0","id":1,
                                                  "method":method,"params":params})
        response.raise_for_status()
        if len(response.content)>6_000_000:
            raise RpcRejected("response_too_large")
        body=response.json()
        if isinstance(body,dict) and "error" in body:
            raise RpcRejected("provider_rejected")
        if not isinstance(body,dict) or not isinstance(body.get("result"),dict):
            raise ValueError("invalid_rpc")
        return body["result"]
    try:
        async with httpx.AsyncClient(timeout=timeout,transport=transport) as client:
            for _ in range(3):
                before=await rpc(client,"getAccountInfo",[mint,{
                    "encoding":"base64","commitment":"confirmed"}])
                before_slot=(before.get("context") or {}).get("slot")
                before_value=before.get("value")
                before_mint=decode_mint_account(before_value,program=TOKEN_PROGRAM)
                before_raw=base64.b64decode(before_value["data"][0],validate=True)
                # Revoked mint authority is essential: supply cannot increase,
                # and matching bracketing supplies therefore rule out burns.
                if int.from_bytes(before_raw[:4],"little")!=0:
                    return {**denied,"status":"mint_authority_open"}
                discovery=await rpc(client,"getProgramAccounts",[TOKEN_PROGRAM,{
                    "encoding":"base64","commitment":"confirmed","withContext":True,
                    "minContextSlot":before_slot,
                    "filters":[{"dataSize":165},{"memcmp":{"offset":0,"bytes":mint}}],
                    "dataSlice":{"offset":32,"length":77}}])
                snapshot=decode_sliced_rpc_snapshot(discovery,mint=mint,
                                                     program=TOKEN_PROGRAM,max_accounts=max_accounts)
                slot=snapshot["slot"]
                after=await rpc(client,"getAccountInfo",[mint,{
                    "encoding":"base64","commitment":"confirmed",
                    "minContextSlot":slot}])
                after_slot=(after.get("context") or {}).get("slot")
                if (type(before_slot) is not int or type(after_slot) is not int
                    or not (before_slot<=slot<=after_slot)):
                    continue
                after_value=after.get("value")
                after_mint=decode_mint_account(after_value,program=TOKEN_PROGRAM)
                after_raw=base64.b64decode(after_value["data"][0],validate=True)
                if (int.from_bytes(after_raw[:4],"little")!=0
                    or before_mint["amount"]!=after_mint["amount"]
                    or before_mint["decimals"]!=after_mint["decimals"]
                    or before_raw[46:50]!=after_raw[46:50]):
                    return {**denied,"status":"mint_bracket_inconsistent"}
                outcome=reconcile_owner_balances(snapshot,mint=mint,program=TOKEN_PROGRAM,
                                                  supply_amount=after_mint["amount"],supply_slot=slot)
                return {**outcome,"status":"full_sliced_"+str(outcome.get("status")),
                        "atomic_snapshot_slot":slot,"mint_before_slot":before_slot,
                        "mint_after_slot":after_slot,
                        "discovered_accounts":len(snapshot["rows"]),
                        "mint_authority":False,
                        "freeze_authority":int.from_bytes(after_raw[46:50],"little")==1,
                        "chain_pass_allowed":False,"owner_coverage_complete":False}
            return {**denied,"status":"full_snapshot_slot_mismatch"}
    except RpcRejected as exc:
        return {**denied,"status":"full_snapshot_rpc_"+str(exc)}
    except httpx.HTTPStatusError as exc:
        code=exc.response.status_code
        category=("rate_limited" if code==429 else "forbidden" if code in (401,403)
                  else "server_error" if code>=500 else "http_error")
        return {**denied,"status":"full_snapshot_rpc_"+category}
    except httpx.HTTPError:
        return {**denied,"status":"full_snapshot_rpc_transport_error"}
    except (ValueError,TypeError,KeyError,IndexError,UnicodeError):
        return {**denied,"status":"full_snapshot_decode_error"}
