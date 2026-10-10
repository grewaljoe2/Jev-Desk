"""Token-2022 mint TLV diagnostics never authorize owner coverage."""
import unittest
from app.research.solana_atomic_owner_evidence import token2022_mint_extension_ids

class Token2022MintExtensionDiagnosticTests(unittest.TestCase):
    def test_base_mint(self):
        self.assertEqual(token2022_mint_extension_ids(bytes(82)), ())

    def test_padded_mint_with_one_extension(self):
        raw=bytes(165)+bytes([1])+(12).to_bytes(2,"little")+(3).to_bytes(2,"little")+b"abc"
        self.assertEqual(token2022_mint_extension_ids(raw),(12,))

    def test_wrong_account_type_and_padding_rejected(self):
        self.assertIsNone(token2022_mint_extension_ids(bytes(165)+bytes([2,12,0,0,0])))
        self.assertIsNone(token2022_mint_extension_ids(bytes(82)+b"x"+bytes(82)+bytes([1,12,0,0,0])))

    def test_truncated_tlv_rejected(self):
        self.assertIsNone(token2022_mint_extension_ids(bytes(165)+bytes([1,12,0,5,0,1])))

if __name__=="__main__":
    unittest.main()
