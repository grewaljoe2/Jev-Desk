"""Offline-only conservative owner concentration calculation; no network calls."""
from collections import defaultdict

def verify_owner_concentration(accounts, supply, *, complete, max_fraction=0.05):
    """Return (status, fraction): pass/reject/unverified. Supply and balances are raw units.

    'complete' must be proven by the data collector, never inferred from a nonempty list.
    Unknown account owners, mint mismatches, unsupported programs, or incomplete
    enumeration never produce a pass.
    """
    if not isinstance(supply, int) or isinstance(supply, bool) or supply <= 0:
        return "unverified", None
    by_owner = defaultdict(int)
    for row in accounts:
        if not isinstance(row, dict):
            return "unverified", None
        owner = row.get("owner")
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
