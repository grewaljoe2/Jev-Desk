"""Two independently atomic RPC snapshots; bounded small-mint verification.

No exact cross-provider slot match is required: each snapshot has its own
single-slot mint supply and token account balances. Matching owner digests
and supply across snapshots are mandatory. Never authorize production CHAIN.
"""
from app.research.solana_atomic_owner_evidence import collect_atomic_small_mint

async def compare_atomic_owner_snapshots(mint, *, primary_rpc="https://api.mainnet-beta.solana.com",
                                         secondary_rpc="https://public.rpc.solanavibestation.com/",
                                         transport=None):
    denied={"status":"atomic_independent_unverified","owner_coverage_complete":False,
            "chain_pass_allowed":False}
    if primary_rpc==secondary_rpc:
        return {**denied,"status":"same_provider"}
    first=await collect_atomic_small_mint(mint,rpc_url=primary_rpc,transport=transport)
    if first.get("positive_balance_coverage_proven") is not True:
        return {**denied,"status":"primary_unverified","primary_status":first.get("status")}
    second=await collect_atomic_small_mint(mint,rpc_url=secondary_rpc,transport=transport)
    if second.get("positive_balance_coverage_proven") is not True:
        return {**denied,"status":"secondary_unverified","secondary_status":second.get("status")}
    required=("owner_balance_digest","supply_amount","holder_count","top_10_percent",
              "largest_owner_fraction","mint_authority","freeze_authority")
    if any(first.get(k)!=second.get(k) for k in required):
        return {**denied,"status":"cross_provider_atomic_mismatch"}
    if not first.get("owner_balance_digest") or first.get("supply_amount",0)<=0:
        return {**denied,"status":"missing_owner_digest"}
    return {**denied,"status":"atomic_independently_correlated_research",
            "positive_balance_coverage_proven":True,
            "cross_provider_owner_match":True,
            "primary_snapshot_slot":first["atomic_snapshot_slot"],
            "secondary_snapshot_slot":second["atomic_snapshot_slot"],
            "owner_balance_digest":first["owner_balance_digest"],
            "supply_amount":first["supply_amount"],
            "holder_count":first["holder_count"],
            "top_10_percent":first["top_10_percent"],
            "largest_owner_fraction":first["largest_owner_fraction"],
            "mint_authority":first["mint_authority"],
            "freeze_authority":first["freeze_authority"]}
