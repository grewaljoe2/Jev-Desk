"""Bounded Helius cursor-pagination research for SPL token accounts.

This collector is intentionally NOT a CHAIN approval source. Cursor exhaustion
is not an atomic snapshot and does not prove supply conservation.
"""
import httpx
from app.research.solana_rpc_owner_decoder import TOKEN_PROGRAM, TOKEN_2022, decode_sliced_rpc_snapshot

async def collect_cursor_owner_research(mint, *, api_key, program=TOKEN_PROGRAM,
                                        max_pages=5, page_size=1000,
                                        max_bytes=2_000_000, timeout_seconds=12,
                                        transport=None):
    denied={"owner_coverage_complete":False,"chain_pass_allowed":False,
            "source":"helius_rpc_v2_research"}
    if not isinstance(mint,str) or not mint or not isinstance(api_key,str) or not api_key or program not in (TOKEN_PROGRAM,TOKEN_2022):
        return {**denied,"status":"invalid_input"}
    if type(max_pages) is not int or not 1<=max_pages<=100 or type(page_size) is not int or not 1<=page_size<=1000 or type(max_bytes) is not int or max_bytes<1000:
        return {**denied,"status":"invalid_input"}
    cursor=None
    seen_accounts=set()
    owners={}
    slots=[]
    seen_cursors=set()
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds,transport=transport) as client:
            for page in range(1,max_pages+1):
                config={"encoding":"base64","withContext":True,"commitment":"confirmed",
                        "limit":page_size,"filters":[{"memcmp":{"offset":0,"bytes":mint}}],
                        "dataSlice":{"offset":32,"length":77}}
                if program==TOKEN_PROGRAM:config["filters"].insert(0,{"dataSize":165})
                if cursor is not None:config["paginationKey"]=cursor
                payload={"jsonrpc":"2.0","id":page,"method":"getProgramAccountsV2","params":[program,config]}
                async with client.stream("POST","https://mainnet.helius-rpc.com/",params={"api-key":api_key},json=payload) as response:
                    if response.status_code==429:return {**denied,"status":"rate_limited","pages":page-1}
                    if response.status_code!=200:return {**denied,"status":"http_error","pages":page-1}
                    size=0
                    chunks=[]
                    async for chunk in response.aiter_bytes():
                        size+=len(chunk)
                        if size>max_bytes:return {**denied,"status":"response_too_large","pages":page-1}
                        chunks.append(chunk)
                import json
                body=json.loads(b"".join(chunks))
                if not isinstance(body,dict) or body.get("error"):return {**denied,"status":"rpc_error","pages":page-1}
                result=body.get("result")
                if not isinstance(result,dict):return {**denied,"status":"invalid_response","pages":page-1}
                context=result.get("context")
                value=result.get("value")
                if not isinstance(context,dict) or not isinstance(value,dict) or not isinstance(value.get("accounts"),list):
                    return {**denied,"status":"invalid_response","pages":page-1}
                snapshot=decode_sliced_rpc_snapshot({"context":context,"value":value["accounts"]},mint=mint,program=program,max_accounts=page_size)
                slots.append(snapshot["slot"])
                for row in snapshot["rows"]:
                    if row["account"] in seen_accounts:return {**denied,"status":"duplicate_account","pages":page}
                    seen_accounts.add(row["account"])
                    owners[row["owner"]]=owners.get(row["owner"],0)+row["amount"]
                if "paginationKey" not in value:\n                    return {**denied,"status":"missing_pagination_key","pages":page}\n                total=value.get("totalResults")\n                if total is not None and (type(total) is not int or total<0):\n                    return {**denied,"status":"invalid_total_results","pages":page}\n                next_cursor=value["paginationKey"]
                if next_cursor is None:
                    return {**denied,"status":"cursor_exhausted_unverified","pages":page,
                            "token_accounts":len(seen_accounts),"unique_owners":len(owners),
                            "accounts_total":sum(owners.values()),"slot_stable":len(set(slots))==1,
                            "first_slot":slots[0],"last_slot":slots[-1]}
                if not isinstance(next_cursor,str) or not next_cursor or next_cursor in seen_cursors:
                    return {**denied,"status":"invalid_cursor","pages":page}
                seen_cursors.add(next_cursor)\n                cursor=next_cursor
            return {**denied,"status":"page_cap_reached","pages":max_pages,"token_accounts":len(seen_accounts),
                    "slot_stable":len(set(slots))==1}
    except httpx.TimeoutException:return {**denied,"status":"timeout"}
    except (httpx.HTTPError,ValueError,TypeError,KeyError):return {**denied,"status":"invalid_provider_data"}
