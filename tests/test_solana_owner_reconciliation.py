import unittest
from app.research.solana_owner_reconciliation import reconcile_owner_balances
from app.research.solana_rpc_owner_decoder import TOKEN_2022

MINT="test-mint"
def row(account,owner,amount,slot=12):
    return {"account":account,"owner":owner,"amount":amount,"mint":MINT,"program":TOKEN_2022,"slot":slot}
def check(rows,supply=100,slot=12,cap=0.20):
    return reconcile_owner_balances({"slot":12,"rows":rows,"owner_coverage_complete":False},
                                    mint=MINT,program=TOKEN_2022,supply_amount=supply,supply_slot=slot,cap_fraction=cap)
class ReconciliationTests(unittest.TestCase):
    def test_aggregate_same_wallet_and_reject(self):
        result=check([row("a","wallet1",30),row("b","wallet1",50),row("c","wallet2",20)])
        self.assertEqual(result["unique_owners"],2)
        self.assertEqual(result["largest_owner_amount"],80)
        self.assertTrue(result["amounts_match"])
        self.assertTrue(result["provable_concentration_reject"])
        self.assertFalse(result["chain_pass_allowed"])
    def test_small_owner_no_pass(self):
        result=check([row(str(i),str(i),10) for i in range(10)])
        self.assertFalse(result["provable_concentration_reject"])
        self.assertFalse(result["chain_pass_allowed"])
    def test_partial_sum_cannot_pass(self):
        result=check([row("a","wallet",10)])
        self.assertEqual(result["status"],"supply_mismatch")
        self.assertFalse(result["chain_pass_allowed"])
    def test_slot_mismatch_rejected(self):
        self.assertEqual(check([row("a","wallet",100)],slot=13)["status"],"invalid_evidence")
    def test_duplicate_account_rejected(self):
        self.assertEqual(check([row("a","wallet",50),row("a","wallet",50)])["status"],"invalid_evidence")
    def test_wrong_mint_rejected(self):
        bad=row("a","wallet",100);bad["mint"]="wrong"
        self.assertEqual(check([bad])["status"],"invalid_evidence")
    def test_sum_exceeds_supply(self):
        self.assertEqual(check([row("a","wallet",101)])["status"],"amount_exceeds_supply")
    def test_zero_supply_invalid(self):
        self.assertEqual(check([],supply=0)["status"],"invalid_evidence")
    def test_unverified_flag_cannot_be_forged(self):
        snap={"slot":12,"rows":[row("a","wallet",100)],"owner_coverage_complete":True}
        result=reconcile_owner_balances(snap,mint=MINT,program=TOKEN_2022,supply_amount=100,supply_slot=12)
        self.assertEqual(result["status"],"invalid_evidence")
if __name__=="__main__":
    unittest.main()
