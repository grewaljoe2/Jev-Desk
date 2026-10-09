"""Bounded, read-only Helius DAS token-account pagination.

An indexed page sequence is not an atomic Solana snapshot. This collector
never grants CHAIN approval; it provides diagnostics and owner aggregation
for comparison against independently verifiable evidence.
"""
from collections import defaultdict
import hashlib
import json
import httpx

async def collect_indexed_owner_research(mint, *, api_key, max_pages=10,
                                         page_size=1000, timeout_seconds=12,
                                         max_response_bytes=2_000_000,
                                         transport=None):
    denied={"status":"invalid_input","owner_coverage_complete":False,
            "chain_pass_allowed":False,"source":"helius_das_research"}
    if not isinstance(mint,str) or not mint or not isinstance(api_key,str) or not api_key:
        return denied
    if type(max_pages) is not int or not 1<=max_pages<=100 or type(page_size) is not int or not 1<=page_size<=1000:
        return denied
    owners=defaultdict(int)
    seen=set()
    total=0
    pages=0
    expected_total=None
    indexed_slot=None
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds,transport=transport) as client:
            for page in range(1,max_pages+1):
                payload={"jsonrpc":"2.0","id":page,"method":"getTokenAccounts",
                         "params":{"mint":mint,"page":page,"limit":page_size}}
                async with client.stream("POST","https://mainnet.helius-rpc.com/",
                                         params={"api-key":api_key},json=payload) as response:
                    if response.status_code==429:
                        return {**denied,"status":"rate_limited","pages":pages}
                    if response.status_code!=200:
                        return {**denied,"status":"provider_http_error","pages":pages}
                    size=0
                    chunks=[]
                    async for chunk in response.aiter_bytes():
                        size+=len(chunk)
                        if size>max_response_bytes:
                            return {**denied,"status":"response_too_large","pages":pages}
                        chunks.append(chunk)
                body=json.loads(b"".join(chunks))
                if not isinstance(body,dict) or body.get("error"):
                    return {**denied,"status":"provider_rpc_error","pages":pages}
                result=body.get("result")
                if not isinstance(result,dict) or not isinstance(result.get("token_accounts"),list):
                    return {**denied,"status":"invalid_page","pages":pages}
                page_total=result.get("total")
                page_slot=result.get("last_indexed_slot")
                if type(page_total) is not int or page_total<0 or type(page_slot) is not int or page_slot<0:
                    return {**denied,"status":"missing_index_metadata","pages":pages}
                if expected_total is None:
                    expected_total=page_total
                    indexed_slot=page_slot
                elif page_total!=expected_total or page_slot!=indexed_slot:
                    return {**denied,"status":"index_changed_during_pagination","pages":pages}
                rows=result["token_accounts"]
                if len(rows)>page_size:
                    return {**denied,"status":"oversized_page","pages":pages}
                for row in rows:
                    if not isinstance(row,dict) or row.get("mint")!=mint:
                        return {**denied,"status":"mint_mismatch","pages":pages}
                    address,owner,amount=row.get("address"),row.get("owner"),row.get("amount")
                    if not isinstance(address,str) or not address or address in seen:
                        return {**denied,"status":"duplicate_or_missing_account","pages":pages}
                    if not isinstance(owner,str) or not owner or type(amount) is not int or not 0<=amount<=2**64-1:
                        return {**denied,"status":"invalid_account","pages":pages}
                    seen.add(address)
                    owners[owner]+=amount
                    total+=amount
                pages=page
                if len(seen)>expected_total:
                    return {**denied,"status":"index_total_exceeded","pages":pages}
                if len(rows)<page_size and len(seen)!=expected_total:
                    return {**denied,"status":"index_total_mismatch","pages":pages}
                if len(seen)==expected_total:
                    digest=hashlib.sha256(json.dumps(sorted(owners.items()),separators=(",",":")).encode()).hexdigest()
                    return {**denied,"status":"indexed_pages_exhausted_unverified",
                            "pages":pages,"token_accounts":len(seen),
                            "last_indexed_slot":indexed_slot,"indexed_total":expected_total,
                            "unique_owners":len(owners),"accounts_total":total,
                            "largest_owner_amount":max(owners.values(),default=0),
                            "owner_balance_digest":digest}
            return {**denied,"status":"page_cap_reached","pages":pages,
                    "token_accounts":len(seen)}
    except httpx.TimeoutException:
        return {**denied,"status":"timeout","pages":pages}
    except (httpx.HTTPError,ValueError,TypeError,KeyError):
        return {**denied,"status":"provider_or_decode_error","pages":pages}
