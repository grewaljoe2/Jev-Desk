"""Offline fail-closed owner reconciliation; never authorizes CHAIN pass."""
from collections import defaultdict
from app.research.solana_rpc_owner_decoder import SUPPORTED

def reconcile_owner_balances(snapshot, *, mint, program, supply_amount, supply_slot, cap_fraction=0.20):
    result = {"status": "invalid_evidence", "owner_coverage_complete": False,
              "chain_pass_allowed": False, "provable_concentration_reject": False}
    if program not in SUPPORTED or not isinstance(mint, str) or not mint:
        return result
    if type(supply_amount) is not int or supply_amount <= 0 or type(supply_slot) is not int or supply_slot < 0:
        return result
    if type(cap_fraction) not in (int, float) or not (0 < cap_fraction < 1):
        return result
    if not isinstance(snapshot, dict) or type(snapshot.get("slot")) is not int or not isinstance(snapshot.get("rows"), list):
        return result
    if snapshot["slot"] != supply_slot or snapshot.get("owner_coverage_complete") is not False:
        return result
    owners = defaultdict(int)
    accounts = set()
    total = 0
    for row in snapshot["rows"]:
        if not isinstance(row, dict) or row.get("mint") != mint or row.get("program") != program or row.get("slot") != supply_slot:
            return result
        account, owner, amount = row.get("account"), row.get("owner"), row.get("amount")
        if not isinstance(account, str) or not account or account in accounts or not isinstance(owner, str) or not owner:
            return result
        if type(amount) is not int or amount < 0 or amount > 2**64-1:
            return result
        accounts.add(account)
        owners[owner] += amount
        total += amount
        if total > supply_amount:
            return {**result, "status": "amount_exceeds_supply"}
    largest = max(owners.values(), default=0)
    matching = total == supply_amount
    fraction = largest / supply_amount
    return {**result, "status": "reconciled_unverified" if matching else "supply_mismatch",
            "token_accounts": len(accounts), "unique_owners": len(owners),
            "accounts_total": total, "supply_amount": supply_amount,
            "largest_owner_amount": largest, "largest_owner_fraction": fraction,
            "same_slot": True, "amounts_match": matching,
            "provable_concentration_reject": fraction > cap_fraction}
