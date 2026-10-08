"""Offline-only mock collector evidence gate. No network calls."""
from app.research.solana_owner_coverage import verify_owner_concentration

def evaluate_mock_collection(pages, supply, *, mint, program, slot, expected_pages, complete):
    """Evaluate mock paginated responses; caller must independently attest completeness.

    Page fields: index, slot, accounts. Account fields: account, owner, amount,
    mint, program, slot. This is not a production RPC adapter.
    """
    if not isinstance(expected_pages, int) or isinstance(expected_pages, bool) or expected_pages <= 0:
        return "unverified", None
    if not isinstance(pages, list) or len(pages) != expected_pages:
        return "unverified", None
    if not isinstance(slot, int) or isinstance(slot, bool) or slot < 0:
        return "unverified", None
    all_accounts = []
    seen = set()
    for page in pages:
        if not isinstance(page, dict) or page.get("error") or page.get("truncated"):
            return "unverified", None
        idx = page.get("index")
        if not isinstance(idx, int) or isinstance(idx, bool) or idx < 0 or idx >= expected_pages or idx in seen:
            return "unverified", None
        seen.add(idx)
        if page.get("slot") != slot or not isinstance(page.get("accounts"), list):
            return "unverified", None
        all_accounts.extend(page["accounts"])
    if seen != set(range(expected_pages)):
        return "unverified", None
    return verify_owner_concentration(all_accounts, supply, complete=complete, expected_mint=mint, expected_program=program, expected_slot=slot)
