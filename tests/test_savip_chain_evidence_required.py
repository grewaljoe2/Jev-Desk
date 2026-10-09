import unittest
from app.research.savip_chain_cut import evaluate_chain

class RequiredChainEvidenceTests(unittest.TestCase):
    def test_missing_holder_or_top10_never_passes(self):
        d={"chain":"solana","solana_wallet_rpc_status":"ok","top_wallet_percent":.02,
           "holder_count":100,"top_10_percent":20,"mint_authority":False,
           "freeze_authority":False}
        self.assertEqual(evaluate_chain(d),(True,"pass"))
        for field in ("holder_count","top_10_percent","mint_authority","freeze_authority"):
            bad={**d,field:None}
            self.assertEqual(evaluate_chain(bad),(False,"missing_chain_evidence"))
    def test_bsc_honeypot_missing_is_not_safe(self):
        d={"chain":"bsc","top_wallet_percent":.02,"holder_count":100,"top_10_percent":20,"is_honeypot":None}
        self.assertEqual(evaluate_chain(d),(False,"missing_chain_evidence"))
        self.assertEqual(evaluate_chain({**d,"is_honeypot":False}),(True,"pass"))

if __name__=="__main__":
    unittest.main()
