import unittest
from app.research.savip_single_eligibility import decide_single_eligibility as decide
E={"market":{"liquidity_usd":50000,"proposed_ticket_usd":36},"chain":{"chain":"eth"}}
GOOD={"worth_trading_at_all":0.8,"confidence":0.7,"size_factor":0.5}
class SingleEligibilityTests(unittest.TestCase):
    def test_accept_valid(self):
        self.assertEqual(decide(GOOD,"eth:a","eth:a",E)[1],"pass")
    def test_low_worth(self):
        self.assertEqual(decide({**GOOD,"worth_trading_at_all":0.59},"eth:a","eth:a",E)[1],"worth_trading_at_all")
    def test_low_confidence(self):
        self.assertEqual(decide({**GOOD,"confidence":0.54},"eth:a","eth:a",E)[1],"confidence")
    def test_invalid_model(self):
        self.assertEqual(decide({**GOOD,"confidence":"not-a-score"},"eth:a","eth:a",E)[1],"invalid_judgment")
    def test_identity_mismatch(self):
        self.assertEqual(decide(GOOD,"eth:a","eth:b",E)[1],"identity_mismatch")
    def test_missing_ticket(self):
        self.assertEqual(decide(GOOD,"eth:a","eth:a",{"market":{"liquidity_usd":50000},"chain":{}})[1],"missing_ticket")
    def test_missing_liquidity(self):
        self.assertEqual(decide(GOOD,"eth:a","eth:a",{"market":{"proposed_ticket_usd":36},"chain":{}})[1],"missing_liquidity")
    def test_zero_size(self):
        self.assertEqual(decide({**GOOD,"size_factor":0},"eth:a","eth:a",E)[1],"zero_size")
    def test_unknown_fields_rejected(self):
        self.assertEqual(decide({**GOOD,"winner":{"token_id":"eth:b"}},"eth:a","eth:a",E)[1],"invalid_judgment")
    def test_nonfinite_and_boolean_market_evidence(self):
        for field in ("liquidity_usd", "proposed_ticket_usd"):
            for bad in (True, False, float("nan"), float("inf"), -float("inf")):
                evidence={"market":{**E["market"],field:bad},"chain":E["chain"]}
                with self.subTest(field=field,bad=str(bad)):
                    self.assertFalse(decide(GOOD,"eth:a","eth:a",evidence)[0])
    def test_nonfinite_and_boolean_scores(self):
        for field in ("worth_trading_at_all", "confidence", "size_factor"):
            for bad in (True, False, float("nan"), float("inf"), -float("inf")):
                with self.subTest(field=field,bad=str(bad)):
                    self.assertEqual(decide({**GOOD,field:bad},"eth:a","eth:a",E)[1],"invalid_judgment")
    def test_blank_token_identity(self):
        self.assertEqual(decide(GOOD," "," ",E)[1],"identity_mismatch")
if __name__=="__main__":unittest.main()
