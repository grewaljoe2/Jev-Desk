import unittest
from app.research.solana_owner_reconciliation import reconcile_owner_balances
from app.research.solana_rpc_owner_decoder import TOKEN_PROGRAM

class PositiveBalanceCoverageTests(unittest.TestCase):
    def snapshot(self, amounts):
        return {"slot": 100, "owner_coverage_complete": False, "rows": [
            {"mint":"mint","program":TOKEN_PROGRAM,"slot":100,"account":f"account{i}","owner":f"owner{i}","amount":n}
            for i,n in enumerate(amounts)
        ]}
    def test_exact_conservation_is_coverage_evidence_not_chain_pass(self):
        r=reconcile_owner_balances(self.snapshot([45,55]),mint="mint",program=TOKEN_PROGRAM,supply_amount=100,supply_slot=100)
        self.assertTrue(r["positive_balance_coverage_proven"])
        self.assertFalse(r["owner_coverage_complete"])
        self.assertFalse(r["chain_pass_allowed"])
    def test_missing_balance_cannot_prove_coverage(self):
        r=reconcile_owner_balances(self.snapshot([45,54]),mint="mint",program=TOKEN_PROGRAM,supply_amount=100,supply_slot=100)
        self.assertFalse(r["positive_balance_coverage_proven"])
    def test_slot_mismatch_cannot_prove_coverage(self):
        r=reconcile_owner_balances(self.snapshot([45,55]),mint="mint",program=TOKEN_PROGRAM,supply_amount=100,supply_slot=101)
        self.assertFalse(r.get("positive_balance_coverage_proven",False))
