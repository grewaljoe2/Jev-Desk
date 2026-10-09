"""SPL token account states: initialized=1 and frozen=2 both hold balances."""
import base64
import unittest
from app.research.solana_rpc_owner_decoder import TOKEN_PROGRAM, decode_sliced_rpc_snapshot, decode_token_account, b58encode

class FrozenAccountTests(unittest.TestCase):
    def setUp(self):
        self.mint = b58encode(bytes([7])*32)
        self.owner = b58encode(bytes([8])*32)
        self.account = b58encode(bytes([9])*32)

    def sliced(self, state):
        raw = bytes([8])*32 + (250).to_bytes(8, "little") + bytes(36) + bytes([state])
        item = {"pubkey": self.account, "account": {"owner": TOKEN_PROGRAM,
                "data": [base64.b64encode(raw).decode(), "base64"]}}
        return {"context": {"slot": 101}, "value": [item]}

    def full(self, state):
        raw = bytearray(165)
        raw[0:32] = bytes([7])*32
        raw[32:64] = bytes([8])*32
        raw[64:72] = (250).to_bytes(8, "little")
        raw[108] = state
        return {"pubkey": self.account, "account": {"owner": TOKEN_PROGRAM,
                "data": [base64.b64encode(raw).decode(), "base64"]}}

    def test_sliced_frozen_balance_counted(self):
        result = decode_sliced_rpc_snapshot(self.sliced(2), mint=self.mint, program=TOKEN_PROGRAM)
        self.assertEqual(result["rows"][0]["amount"], 250)
        self.assertEqual(result["rows"][0]["owner"], self.owner)

    def test_full_frozen_balance_counted(self):
        result = decode_token_account(self.full(2), mint=self.mint, program=TOKEN_PROGRAM, slot=101)
        self.assertEqual(result["amount"], 250)

    def test_uninitialized_rejected(self):
        with self.assertRaises(ValueError):
            decode_sliced_rpc_snapshot(self.sliced(0), mint=self.mint, program=TOKEN_PROGRAM)
        with self.assertRaises(ValueError):
            decode_token_account(self.full(0), mint=self.mint, program=TOKEN_PROGRAM, slot=101)

if __name__ == "__main__":
    unittest.main()
