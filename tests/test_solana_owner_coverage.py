"""Offline owner-coverage tests collected by unittest in CI."""
import unittest
from app.research.solana_owner_coverage import verify_owner_concentration as check

class OwnerCoverageTests(unittest.TestCase):
    def test_split_accounts_reject(self):
        self.assertEqual(check([{"owner":"A","amount":30},{"owner":"A","amount":30},{"owner":"B","amount":940}],1000,complete=True)[0],"reject")

    def test_incomplete_never_passes(self):
        self.assertEqual(check([{"owner":"A","amount":20},{"owner":"B","amount":20}],1000,complete=False)[0],"unverified")

    def test_complete_distribution_pass(self):
        self.assertEqual(check([{"owner":str(i),"amount":50} for i in range(20)],1000,complete=True),("pass",0.05))

    def test_unknown_owner_fail_closed(self):
        self.assertEqual(check([{"owner":None,"amount":1000}],1000,complete=True)[0],"unverified")

    def test_missing_supply_fail_closed(self):
        self.assertEqual(check([{"owner":"A","amount":100}],None,complete=True)[0],"unverified")

    def test_supply_mismatch_fail_closed(self):
        self.assertEqual(check([{"owner":str(i),"amount":40} for i in range(20)],1000,complete=True)[0],"unverified")

    def test_oversupply_fail_closed(self):
        self.assertEqual(check([{"owner":"A","amount":1001}],1000,complete=True)[0],"unverified")

    def test_duplicate_owner_accounts_aggregate(self):
        self.assertEqual(check([{"owner":"A","amount":26},{"owner":"A","amount":26},{"owner":"B","amount":948}],1000,complete=True)[0],"reject")

    def test_incomplete_even_when_sum_matches_supply(self):
        self.assertEqual(check([{"owner":"A","amount":1000}],1000,complete=False)[0],"reject")
