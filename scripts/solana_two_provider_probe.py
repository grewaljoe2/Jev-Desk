"""One-shot research probe. Read-only; no production CHAIN integration."""
import asyncio
import json
from app.research.solana_owner_evidence_pipeline import collect_independently_confirmed_owner_evidence

MINT="2JxdiEFs3K8tVtWp4Q3SK6RGNwLJaRRNmX63y3Xnpump"

async def main():
    result=await collect_independently_confirmed_owner_evidence(MINT)
    print("SOLANA_TWO_PROVIDER_PROBE="+json.dumps({
        k:v for k,v in result.items() if k not in ("owner_balance_digest",)
    },sort_keys=True))
    assert result["chain_pass_allowed"] is False
    assert result["owner_coverage_complete"] is False

if __name__=="__main__":
    asyncio.run(main())
