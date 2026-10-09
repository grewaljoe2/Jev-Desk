"""Explicitly invoked, read-only Solana RPC owner-enumeration feasibility probe.

Not scheduled, not connected to CHAIN, never certifies owner coverage.
One request only, with response-byte cap and no retries.
"""
import asyncio
import json
import httpx
from app.research.solana_rpc_owner_decoder import SUPPORTED, decode_rpc_snapshot

DEFAULT_RPC = "https://api.mainnet-beta.solana.com"

async def probe_owner_accounts(mint, program, *, rpc_url=DEFAULT_RPC,
                               timeout_seconds=12, max_bytes=2_000_000,
                               max_accounts=5000, transport=None):
    if not isinstance(mint,str) or not mint or program not in SUPPORTED:
        return {"status":"invalid_request","owner_coverage_complete":False}
    params=[program,{"encoding":"base64","commitment":"confirmed","withContext":True,
                     "filters":[{"memcmp":{"offset":0,"bytes":mint}}]}]
    payload={"jsonrpc":"2.0","id":1,"method":"getProgramAccounts","params":params}
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds,transport=transport) as client:
            async with client.stream("POST",rpc_url,json=payload) as response:
                if response.status_code==429:
                    return {"status":"rate_limited","owner_coverage_complete":False}
                if response.status_code!=200:
                    return {"status":"http_error","http_status":response.status_code,"owner_coverage_complete":False}
                chunks=[]
                size=0
                async for chunk in response.aiter_bytes():
                    size+=len(chunk)
                    if size>max_bytes:
                        return {"status":"response_too_large","owner_coverage_complete":False}
                    chunks.append(chunk)
        data=json.loads(b"".join(chunks))
        if not isinstance(data,dict) or data.get("error"):
            return {"status":"rpc_error","owner_coverage_complete":False}
        snapshot=decode_rpc_snapshot(data.get("result"),mint=mint,program=program,max_accounts=max_accounts)
        return {"status":"decoded_unverified","slot":snapshot["slot"],
                "token_accounts":len(snapshot["rows"]),"owner_coverage_complete":False}
    except (httpx.HTTPError,ValueError,TypeError,KeyError,asyncio.TimeoutError):
        return {"status":"unavailable_or_invalid","owner_coverage_complete":False}
