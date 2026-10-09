"""One-shot, bounded Helius schema research. Never authorizes CHAIN or trading.

Run only in an authorized Render shell/job with HELIUS_API_KEY already configured:
    python -m app.research.helius_schema_probe
No web route, scheduler, database writes, or key output.
"""
import asyncio
import json
import os
from app.research.solana_indexed_owner_research import collect_indexed_owner_research

MINTS = (
    "6Mix12LiHrQFojaQEnfPUC65Qkwd6X4Y5Qg93oFbordr",
    "HMYd9tosnUXuNHmq7pXmoePRVBLBBjA3JBfydq6upump",
)
FIELDS = ("status", "pages", "token_accounts", "indexed_total",
          "last_indexed_slot", "unique_owners", "accounts_total",
          "largest_owner_amount", "owner_balance_digest",
          "owner_coverage_complete", "chain_pass_allowed")

async def probe():
    key = os.environ.get("HELIUS_API_KEY", "")
    if not key:
        return {"status": "missing_credential", "chain_pass_allowed": False}
    results = []
    for mint in MINTS:
        for page_size in (50, 100):
            result = await collect_indexed_owner_research(
                mint, api_key=key, max_pages=3, page_size=page_size,
                timeout_seconds=8, max_response_bytes=500_000)
            results.append({"mint": mint, "requested_page_size": page_size,
                            **{field: result[field] for field in FIELDS if field in result}})
    return {"status": "research_only", "results": results,
            "chain_pass_allowed": False}

if __name__ == "__main__":
    print(json.dumps(asyncio.run(probe()), sort_keys=True))
