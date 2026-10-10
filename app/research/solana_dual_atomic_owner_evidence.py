"""Two independently atomic RPC snapshots; bounded small-mint verification.

No exact cross-provider slot match is required: each snapshot has its own
single-slot mint supply and token account balances. Matching owner digests
and supply across snapshots are mandatory. Never authorize production CHAIN.
"""
import asyncio
from app.research.solana_atomic_owner_evidence import collect_atomic_small_mint, collect_full_sliced_snapshot

async def compare_atomic_owner_snapshots(mint, *, primary_rpc="https://api.mainnet-beta.solana.com",
                                         secondary_rpc="https://public.rpc.solanavibestation.com/",
                                         transport=None):
    denied={"status":"atomic_independent_unverified","owner_coverage_complete":False,
            "chain_pass_allowed":False}
    if not isinstance(mint,str) or not mint:
        return {**denied,"status":"invalid_mint"}
    if primary_rpc==secondary_rpc:
        return {**denied,"status":"same_provider"}
    first=await collect_atomic_small_mint(mint,rpc_url=primary_rpc,transport=transport)
    if first.get("status") in ("atomic_account_limit","atomic_rpc_response_too_large") and first.get("token_program") != "token_2022":
        first=await collect_full_sliced_snapshot(mint,rpc_url=primary_rpc,transport=transport)
    if first.get("positive_balance_coverage_proven") is not True:
        return {**denied,"status":"primary_unverified","primary_status":first.get("status"),"primary_rpc_method":first.get("rpc_method"),"mint_extension_ids":first.get("mint_extension_ids"),"slot_diagnostics":first.get("slot_diagnostics")}
    second=await collect_atomic_small_mint(mint,rpc_url=secondary_rpc,transport=transport)
    if second.get("status") in ("atomic_account_limit","atomic_rpc_response_too_large") and second.get("token_program") != "token_2022":
        second=await collect_full_sliced_snapshot(mint,rpc_url=secondary_rpc,transport=transport)
    if second.get("status")=="full_snapshot_rpc_rate_limited":
        # One delayed, bounded retry on public secondary RPC; still fail closed.
        await asyncio.sleep(3)
        second=await collect_full_sliced_snapshot(mint,rpc_url=secondary_rpc,transport=transport)
    if second.get("positive_balance_coverage_proven") is not True:
        return {**denied,"status":"secondary_unverified","secondary_status":second.get("status")}
    primary_slot=first.get("atomic_snapshot_slot")
    secondary_slot=second.get("atomic_snapshot_slot")
    if (type(primary_slot) is not int or type(secondary_slot) is not int
        or abs(primary_slot-secondary_slot)>150):
        return {**denied,"status":"cross_provider_slot_gap"}
    required=("owner_balance_digest","supply_amount","holder_count","top_10_percent",
              "largest_owner_fraction","mint_authority","freeze_authority","mint_extension_ids")
    mismatched_fields=[k for k in required if first.get(k)!=second.get(k)]
    if mismatched_fields:
        return {**denied,"status":"cross_provider_atomic_mismatch",
                "mismatched_fields":mismatched_fields}
    if not first.get("owner_balance_digest") or type(first.get("supply_amount")) is not int or first["supply_amount"]<=0:
        return {**denied,"status":"missing_owner_digest"}
    # Evidence is sufficient for a bounded classic-SPL shadow eligibility
    # decision only when both providers independently conserve the supply.
    # This function still does not authorize CHAIN or live execution.
    return {**denied,"status":"atomic_independently_correlated_research",
            "shadow_owner_evidence_eligible":True,
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
