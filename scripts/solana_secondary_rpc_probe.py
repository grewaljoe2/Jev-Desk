"""Bounded, read-only secondary RPC capability check; research only."""
import asyncio
import json
from app.research.solana_owner_evidence_pipeline import collect_owner_evidence, collect_independently_confirmed_owner_evidence

MINT="2JxdiEFs3K8tVtWp4Q3SK6RGNwLJaRRNmX63y3Xnpump"
ENDPOINTS=(
    ("ankr_public","https://rpc.ankr.com/solana"),
    ("solana_vibe","https://public.rpc.solanavibestation.com/"),
    ("publicnode","https://solana-rpc.publicnode.com"),
)

async def main():
    for name,url in ENDPOINTS:
        result=await collect_owner_evidence(MINT,rpc_url=url,timeout_seconds=8,max_bytes=750000)
        print("SECONDARY_RPC_PROBE="+json.dumps({"endpoint":name,"status":result.get("status"),
            "supply_conserved":result.get("positive_balance_coverage_proven",False),
            "chain_pass_allowed":False},sort_keys=True),flush=True)

    confirmed=await collect_independently_confirmed_owner_evidence(MINT)
    print("CROSS_PROVIDER_RETEST="+json.dumps({k:v for k,v in confirmed.items() if k!="owner_balance_digest"},sort_keys=True),flush=True)
    assert confirmed["chain_pass_allowed"] is False

if __name__=="__main__":
    asyncio.run(main())
