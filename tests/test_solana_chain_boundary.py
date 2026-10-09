"""Solana CHAIN must fail closed even if caller bypasses the worker."""
import unittest
from app.research.savip_chain_cut import evaluate_chain

class SolanaChainBoundaryTests(unittest.TestCase):
    def test_unverified_owner_cannot_pass(self):
        for status in (None,"pending","unverified_owner_coverage","unavailable_rate_limited"):
            with self.subTest(status=status):
                self.assertEqual(evaluate_chain({"chain":"solana","top_wallet_percent":0.01,"solana_wallet_rpc_status":status}),(False,"solana_owner_unverified"))
    def test_missing_owner_fraction_cannot_pass(self):
        self.assertEqual(evaluate_chain({"chain":"solana","solana_wallet_rpc_status":"ok"}),(False,"solana_owner_unverified"))
    def test_verified_owner_still_subject_to_threshold(self):
        ok,reason=evaluate_chain({"chain":"solana","solana_wallet_rpc_status":"ok","top_wallet_percent":0.99})
        self.assertFalse(ok)
        self.assertEqual(reason,"top_wallet")
    def test_other_chains_unaffected(self):
        self.assertEqual(evaluate_chain({"chain":"bsc","top_wallet_percent":0.01}),(False,"missing_chain_evidence"))

if __name__=="__main__":
    unittest.main()
