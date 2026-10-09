"""Offline decoding of Solana getProgramAccounts token accounts.

This is NOT a completeness attestation or a production RPC collector.
The account.owner field is the token PROGRAM; token-wallet owner is bytes 32:64.
"""
import base64
import binascii

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022 = "TokenzQdBNbLqP5VEhdkAS6EPFzDzzMbaK6r3nW4u"
SUPPORTED = frozenset((TOKEN_PROGRAM, TOKEN_2022))

def b58encode(data):
    number = int.from_bytes(data, "big")
    chars = ""
    while number:
        number, digit = divmod(number, 58)
        chars = ALPHABET[digit] + chars
    return "1" * (len(data) - len(data.lstrip(bytes([0])))) + chars

def decode_token_account(item, *, mint, program, slot):
    """Decode one full base64 SPL token account; raise ValueError on any ambiguity."""
    if program not in SUPPORTED or not isinstance(slot, int) or isinstance(slot, bool) or slot < 0:
        raise ValueError("unsupported_program_or_slot")
    if not isinstance(item, dict) or not isinstance(item.get("pubkey"), str):
        raise ValueError("missing_account_identity")
    account = item.get("account")
    if not isinstance(account, dict) or account.get("owner") != program:
        raise ValueError("wrong_token_program")
    encoded = account.get("data")
    if not isinstance(encoded, list) or len(encoded) != 2 or encoded[1] != "base64":
        raise ValueError("missing_full_base64")
    try:
        raw = base64.b64decode(encoded[0], validate=True)
    except (TypeError, ValueError, binascii.Error) as exc:
        raise ValueError("invalid_base64") from exc
    if len(raw) < 165:
        raise ValueError("truncated_token_account")
    if program == TOKEN_PROGRAM and len(raw) != 165:
        raise ValueError("invalid_classic_token_account_size")
    decoded_mint = b58encode(raw[0:32])
    if decoded_mint != mint:
        raise ValueError("mint_mismatch")
    if raw[108] != 1:
        raise ValueError("token_account_not_initialized")
    return {"account": item["pubkey"], "owner": b58encode(raw[32:64]),
            "amount": int.from_bytes(raw[64:72], "little"),
            "mint": decoded_mint, "program": program, "slot": slot}

def decode_rpc_snapshot(result, *, mint, program, max_accounts=10000):
    """Decode a bounded, withContext response; NEVER attest completeness."""
    if not isinstance(result, dict) or not isinstance(result.get("context"), dict):
        raise ValueError("missing_context")
    slot = result["context"].get("slot")
    if not isinstance(slot, int) or isinstance(slot, bool) or slot < 0:
        raise ValueError("invalid_context_slot")
    values = result.get("value")
    if not isinstance(values, list) or len(values) > max_accounts:
        raise ValueError("invalid_or_oversize_response")
    seen = set()
    rows = []
    for item in values:
        row = decode_token_account(item, mint=mint, program=program, slot=slot)
        if row["account"] in seen:
            raise ValueError("duplicate_token_account")
        seen.add(row["account"])
        rows.append(row)
    return {"slot": slot, "rows": rows, "owner_coverage_complete": False}
