import unittest
from app.research.savip_jev_evidence import build_evidence

class TicketEvidenceTests(unittest.TestCase):
    def test_missing_x_uses_36_dollar_ticket(self):
        d={"token_id":"eth:test","chain":"eth","liquidity_usd":211933.9}
        self.assertEqual(build_evidence(d).market.proposed_ticket_usd,36.0)

    def test_observed_exact_x_uses_60_dollar_ticket(self):
        d={"token_id":"eth:test","chain":"eth","liquidity_usd":211933.9}
        # The helper must validate exact X observation, not a fabricated handle.
        from app.research.savip_shadow_execution import ticket_usd
        self.assertEqual(ticket_usd(1000,211933.9,1.0),60.0)

    def test_liquidity_cap_is_respected(self):
        d={"token_id":"eth:test","chain":"eth","liquidity_usd":1000}
        self.assertEqual(build_evidence(d).market.proposed_ticket_usd,20.0)

    def test_missing_liquidity_not_invented(self):
        d={"token_id":"eth:test","chain":"eth"}
        self.assertIsNone(build_evidence(d).market.proposed_ticket_usd)
if __name__=="__main__":unittest.main()
