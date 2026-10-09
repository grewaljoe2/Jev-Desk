import unittest
from app.research.solana_account_lower_bound import classify_account_lower_bound as classify
from app.strategy.reference_thresholds import HARD

class LowerBoundTests(unittest.TestCase):
    def test_over_limit_proves_rejection(self):
        self.assertEqual(classify(HARD["max_top_wallet"]+0.01),"reject")
    def test_under_limit_does_not_prove_pass(self):
        self.assertEqual(classify(0.001),"unverified")
    def test_equal_limit_not_rejected(self):
        self.assertEqual(classify(HARD["max_top_wallet"]),"unverified")
    def test_bad_numbers_fail_closed(self):
        for x in [None,True,-0.1,1.1,float("nan"),float("inf"),"0.5"]:
            self.assertEqual(classify(x),"unverified")

if __name__=="__main__":
    unittest.main()
