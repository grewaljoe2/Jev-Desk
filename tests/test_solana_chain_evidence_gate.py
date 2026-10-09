import unittest
from app.research.savip_chain_cut import evaluate_chain

class SolanaChainEvidenceTests(unittest.TestCase):
    def test_unverified_owner_never_passes(self):
        self.assertEqual(evaluate_chain({"chain":"solana","solana_wallet_rpc_status":"unverified_owner_coverage","top_wallet_percent":None}),(False,"solana_owner_unverified"))
    def test_missing_owner_status_never_passes(self):
        self.assertEqual(evaluate_chain({"chain":"solana","top_wallet_percent":0.01}),(False,"solana_owner_unverified"))
    def test_other_chains_unaffected(self):
        self.assertEqual(evaluate_chain({"chain":"eth","top_wallet_percent":0.01}),(False,"missing_chain_evidence"))

if __name__=="__main__":
    unittest.main()
