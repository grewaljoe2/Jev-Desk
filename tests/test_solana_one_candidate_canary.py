import unittest
from app.research.solana_one_candidate_canary import evaluate_one_candidate

class SingleCandidateCanaryTests(unittest.TestCase):
    def setUp(self):
        self.dossier={"chain":"solana","mint_authority":False,"freeze_authority":False}
        self.evidence={"owner_coverage_complete":True,"chain_pass_allowed":True,
                       "positive_balance_coverage_proven":True,
                       "largest_owner_fraction":0.02,"holder_count":100,
                       "top_10_percent":30.0}

    def test_verified_candidate_reaches_chain_pass(self):
        result=evaluate_one_candidate(self.dossier,self.evidence)
        self.assertTrue(result["chain_pass"])
        self.assertEqual(result["status"],"chain_pass")

    def test_unverified_cannot_pass(self):
        evidence={**self.evidence,"chain_pass_allowed":False}
        self.assertFalse(evaluate_one_candidate(self.dossier,evidence)["chain_pass"])

    def test_concentration_rejects(self):
        evidence={**self.evidence,"largest_owner_fraction":0.06}
        self.assertEqual(evaluate_one_candidate(self.dossier,evidence)["reason"],"top_wallet")

    def test_open_authority_rejects(self):
        dossier={**self.dossier,"mint_authority":True}
        self.assertFalse(evaluate_one_candidate(dossier,self.evidence)["chain_pass"])

if __name__=="__main__":
    unittest.main()
