"""Offline-only conservative owner concentration calculation; no network calls."""
from collections import defaultdict

def verify_owner_concentration(accounts, supply, *, complete, max_fraction=0.05, expected_mint=None, expected_program=None, expected_slot=None):
    """Return (status, fraction): pass/reject/unverified. Supply and balances are raw units.

    'complete' must be proven by the data collector, never inferred from a nonempty list.
    Unknown account owners, mint mismatches, unsupported programs, or incomplete
    enumeration never produce a pass.
    """
    if not isinstance(supply, int) or isinstance(supply, bool) or supply <= 0:
        return "unverified", None
    if expected_mint is not None and (not isinstance(expected_mint, str) or not expected_mint):\n        return "unverified", None\n    if expected_program is not None and (not isinstance(expected_program, str) or not expected_program):\n        return "unverified", None\n    if expected_slot is not None and (not isinstance(expected_slot, int) or isinstance(expected_slot, bool) or expected_slot < 0):\n        return "unverified", None\n    seen_accounts = set()\n    by_owner = defaultdict(int)
    for row in accounts:
        if not isinstance(row, dict):
            return "unverified", None
        if expected_mint is not None and row.get("mint") != expected_mint:\n            return "unverified", None\n        if expected_program is not None and row.get("program") != expected_program:\n            return "unverified", None\n        if expected_slot is not None and row.get("slot") != expected_slot:\n            return "unverified", None\n        account_id = row.get("account")\n        if any(v is not None for v in (expected_mint, expected_program, expected_slot)):\n            if not isinstance(account_id, str) or not account_id or account_id in seen_accounts:\n                return "unverified", None\n            seen_accounts.add(account_id)\n        owner = row.get("owner")
        amount = row.get("amount")
        if not isinstance(owner, str) or not owner or not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
            return "unverified", None
        by_owner[owner] += amount
    if not by_owner:
        return "unverified", None
    largest = max(by_owner.values())
    if largest > supply:
        return "unverified", None
    fraction = largest / supply
    if fraction > max_fraction:
        return "reject", fraction
    if complete is not True or sum(by_owner.values()) != supply:
        return "unverified", fraction
    return "pass", fraction
