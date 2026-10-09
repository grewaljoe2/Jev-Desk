"""No-network tests for owner extraction from Solana RPC token accounts."""
import base64
import unittest
from app.research.solana_rpc_owner_decoder import (
    TOKEN_PROGRAM, b58encode, decode_rpc_snapshot, decode_token_account
)

MINT = bytes([7]) * 32
OWNER = bytes([9]) * 32

def item(amount=50, owner=OWNER, mint=MINT, program=TOKEN_PROGRAM, account="acct1"):
    raw = bytearray(165)
    raw[:32] = mint
    raw[32:64] = owner
    raw[64:72] = amount.to_bytes(8, "little")
    raw[108] = 1
    return {"pubkey": account, "account": {"owner": program,
            "data": [base64.b64encode(raw).decode(), "base64"]}}

class DecoderTests(unittest.TestCase):
    def test_owner_is_token_data_not_program_owner(self):
        row=decode_token_account(item(),mint=b58encode(MINT),program=TOKEN_PROGRAM,slot=12)
        self.assertEqual(row["owner"],b58encode(OWNER))
        self.assertNotEqual(row["owner"],TOKEN_PROGRAM)
        self.assertEqual(row["amount"],50)
    def test_no_complete_attestation(self):
        result=decode_rpc_snapshot({"context":{"slot":12},"value":[item()]},
                                   mint=b58encode(MINT),program=TOKEN_PROGRAM)
        self.assertFalse(result["owner_coverage_complete"])
    def test_duplicate_account_rejected(self):
        with self.assertRaisesRegex(ValueError,"duplicate"):
            decode_rpc_snapshot({"context":{"slot":12},"value":[item(),item()]},
                                mint=b58encode(MINT),program=TOKEN_PROGRAM)
    def test_wrong_mint_rejected(self):
        with self.assertRaisesRegex(ValueError,"mint_mismatch"):
            decode_token_account(item(mint=bytes([4])*32),mint=b58encode(MINT),program=TOKEN_PROGRAM,slot=12)
    def test_program_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError,"wrong_token_program"):
            decode_token_account(item(program="wrong"),mint=b58encode(MINT),program=TOKEN_PROGRAM,slot=12)
    def test_truncated_data_rejected(self):
        broken=item()
        broken["account"]["data"]=[base64.b64encode(b"short").decode(),"base64"]
        with self.assertRaisesRegex(ValueError,"truncated"):
            decode_token_account(broken,mint=b58encode(MINT),program=TOKEN_PROGRAM,slot=12)
    def test_missing_context_rejected(self):
        with self.assertRaisesRegex(ValueError,"missing_context"):
            decode_rpc_snapshot({"value":[item()]},mint=b58encode(MINT),program=TOKEN_PROGRAM)
    def test_bounded_collection(self):
        with self.assertRaisesRegex(ValueError,"oversize"):
            decode_rpc_snapshot({"context":{"slot":12},"value":[item(),item(account="acct2")]},
                                mint=b58encode(MINT),program=TOKEN_PROGRAM,max_accounts=1)

if __name__=="__main__":
    unittest.main()
