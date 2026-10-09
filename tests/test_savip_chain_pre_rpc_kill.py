import unittest
from app.research.savip_chain_cut import known_chain_kill, evaluate_chain

class PreRpcKillTests(unittest.TestCase):
    def test_top10_rejects_without_owner_rpc(self):
        d={"chain":"solana","top_10_percent":61}
        self.assertEqual(known_chain_kill(d),"top_10")
        self.assertEqual(evaluate_chain({**d,"solana_wallet_rpc_status":"ok","top_wallet_percent":0}), (False,"top_10"))

    def test_holders_rejects_without_owner_rpc(self):
        self.assertEqual(known_chain_kill({"chain":"solana","holder_count":79}),"holders")

    def test_authority_rejects_without_owner_rpc(self):
        self.assertEqual(known_chain_kill({"chain":"solana","mint_authority":"SomeAddress"}),"authority_open")

    def test_unknown_dossier_never_proves_pass(self):
        d={"chain":"solana","top_10_percent":None,"holder_count":None}
        self.assertIsNone(known_chain_kill(d))
        self.assertEqual(evaluate_chain(d),(False,"solana_owner_unverified"))

    def test_exact_boundaries_do_not_kill(self):
        self.assertIsNone(known_chain_kill({"chain":"solana","top_10_percent":60,"holder_count":80,"mint_authority":"revoked","freeze_authority":False}))

    def test_non_solana_honeypot(self):
        self.assertEqual(known_chain_kill({"chain":"bsc","is_honeypot":True}),"honeypot")
