"""Explicit, read-only Solana evidence pipeline. No production CHAIN pass.

Three bounded RPC calls maximum, no retries. Supply and account snapshot slots
must agree. Matching balances do not independently certify RPC completeness.
"""
import asyncio
import json
import httpx
from app.research.solana_rpc_owner_decoder import SUPPORTED, TOKEN_PROGRAM, decode_rpc_snapshot, decode_mint_account
from app.research.solana_owner_reconciliation import reconcile_owner_balances

RPC = "https://api.mainnet-beta.solana.com"

async def collect_owner_evidence(mint, *, rpc_url=RPC, timeout_seconds=12,
                                 max_bytes=2_000_000, max_accounts=5000, transport=None):
    denied={"status":"invalid_evidence","chain_pass_allowed":False,"owner_coverage_complete":False}
    if not isinstance(mint,str) or not mint or type(max_bytes) is not int or max_bytes < 1000 or type(max_accounts) is not int or max_accounts < 1:
        return denied
    async def request(client,method,params):
        payload={"jsonrpc":"2.0","id":1,"method":method,"params":params}
        async with client.stream("POST",rpc_url,json=payload) as response:
            if response.status_code == 429:
                raise ValueError("rate_limited")
            if response.status_code != 200:
                raise ValueError("http_error")
            chunks=[]
            size=0
            async for chunk in response.aiter_bytes():
                size+=len(chunk)
                if size>max_bytes:
                    raise ValueError("response_too_large")
                chunks.append(chunk)
        body=json.loads(b"".join(chunks))
        if not isinstance(body,dict) or body.get("error") or not isinstance(body.get("result"),dict):
            raise ValueError("rpc_error")
        return body["result"]
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds,transport=transport) as client:
            info=await request(client,"getAccountInfo",[mint,{"encoding":"base64","commitment":"confirmed"}])
            value=info.get("value")
            if not isinstance(value,dict) or value.get("owner") not in SUPPORTED:
                return {**denied,"status":"unsupported_or_missing_mint"}
            program=value["owner"]
            mint_data=decode_mint_account(value,program=program)
            mint_slot=(info.get("context") or {}).get("slot")
            if type(mint_slot) is not int or mint_slot < 0:
                return {**denied,"status":"invalid_mint_slot"}
            filters=[{"memcmp":{"offset":0,"bytes":mint}}]
            if program==TOKEN_PROGRAM:
                filters.insert(0,{"dataSize":165})
            accounts=await request(client,"getProgramAccounts",[program,{"encoding":"base64","commitment":"confirmed","withContext":True,"minContextSlot":mint_slot,"filters":filters}])
            snapshot=decode_rpc_snapshot(accounts,mint=mint,program=program,max_accounts=max_accounts)
            if snapshot["slot"] < mint_slot:
                return {**denied,"status":"stale_accounts_snapshot"}
            supply=await request(client,"getTokenSupply",[mint,{"commitment":"confirmed","minContextSlot":snapshot["slot"]}])
            amount=(supply.get("value") or {}).get("amount")
            slot=(supply.get("context") or {}).get("slot")
            decimals=(supply.get("value") or {}).get("decimals")
            if not isinstance(amount,str) or not amount.isdecimal() or type(decimals) is not int or decimals != mint_data["decimals"]:
                return {**denied,"status":"invalid_supply"}
            if type(slot) is not int or slot < snapshot["slot"]:
                return {**denied,"status":"stale_supply_snapshot","mint_program":program,
                        "mint_slot":mint_slot,"accounts_slot":snapshot["slot"],"supply_slot":slot}
            if slot != snapshot["slot"]:
                return {**denied,"status":"snapshot_slot_mismatch","mint_program":program,
                        "mint_slot":mint_slot,"accounts_slot":snapshot["slot"],"supply_slot":slot}
            outcome=reconcile_owner_balances(snapshot,mint=mint,program=program,supply_amount=int(amount),supply_slot=slot)
            return {**outcome,"mint_program":program,"mint_slot":mint_slot,"accounts_slot":snapshot["slot"],"supply_slot":slot}
    except (httpx.TimeoutException,asyncio.TimeoutError):
        return {**denied,"status":"timeout"}
    except httpx.HTTPError:
        return {**denied,"status":"transport_error"}
    except (ValueError,TypeError,KeyError) as exc:
        known={"rate_limited","http_error","response_too_large","rpc_error"}
        return {**denied,"status":str(exc) if str(exc) in known else "invalid_rpc_response"}

async def collect_independently_confirmed_owner_evidence(mint, *, primary_rpc=RPC,
                                                         secondary_rpc="https://public.rpc.solanavibestation.com/",
                                                         transport=None):
    """Research-only: require two independent RPC views of identical owner balances.

    This does not authorize production CHAIN passes. Both snapshots must
    independently conserve supply at their respective slots, and have identical
    per-owner balances. Different slots require exact owner-map and supply\n    equality; no interpolation or inferred state is accepted.
    """
    denied={"status":"independent_confirmation_unavailable",
            "owner_coverage_complete":False,"chain_pass_allowed":False}
    if primary_rpc == secondary_rpc:
        return {**denied,"status":"same_provider"}
    first=await collect_owner_evidence(mint,rpc_url=primary_rpc,transport=transport)
    if first.get("status") in ("snapshot_slot_mismatch","stale_supply_snapshot"):
        first=await collect_owner_evidence(mint,rpc_url=primary_rpc,transport=transport)
    if first.get("positive_balance_coverage_proven") is not True:
        return {**denied,"primary_status":first.get("status")}
    second=await collect_owner_evidence(mint,rpc_url=secondary_rpc,transport=transport)
    if second.get("status") in ("snapshot_slot_mismatch","stale_supply_snapshot"):
        second=await collect_owner_evidence(mint,rpc_url=secondary_rpc,transport=transport)
    if second.get("positive_balance_coverage_proven") is not True:
        return {**denied,"primary_status":first.get("status"),"secondary_status":second.get("status")}
    if first.get("supply_amount") != second.get("supply_amount"):
        return {**denied,"status":"cross_provider_supply_mismatch"}
    digest=first.get("owner_balance_digest")
    if not isinstance(digest,str) or not digest or digest!=second.get("owner_balance_digest"):
        return {**denied,"status":"cross_provider_owner_mismatch"}
    return {**denied,"status":"independently_correlated_research",
            "cross_provider_owner_match":True,"positive_balance_coverage_proven":True,
            "primary_snapshot_slot":first["accounts_slot"],
            "secondary_snapshot_slot":second["accounts_slot"],
            "cross_provider_same_slot":first["accounts_slot"]==second["accounts_slot"],
            "owner_balance_digest":digest,
            "largest_owner_fraction":first.get("largest_owner_fraction")}
