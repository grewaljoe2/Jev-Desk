import unittest
from app.research.savip_single_audit import build_single_audit
E={'market':{'liquidity_usd':50000,'proposed_ticket_usd':36},'chain':{'chain':'eth'}}
S={'worth_trading_at_all':0.8,'confidence':0.7,'size_factor':0.5}
class AuditTests(unittest.TestCase):
    def test_verified_pass(self):
        row={'id':12,'token_id':'eth:a','payload_json':{'result':{'ok':True,'soft_pass':True,'judgment':{'market':{}}},'evidence':E}}
        r=build_single_audit(row,S)
        self.assertTrue(r['accepted'])
        self.assertEqual(r['jev_event_id'],12)
        self.assertEqual(r['decision_type'],'standalone_eligibility')
    def test_unverified_fails_closed(self):
        row={'id':12,'token_id':'eth:a','payload_json':{'result':{'ok':True,'soft_pass':False},'evidence':E}}
        r=build_single_audit(row,S)
        self.assertFalse(r['accepted'])
        self.assertEqual(r['reason'],'unverified_soft_pass')
    def test_missing_ticket_fails_closed(self):
        row={'id':12,'token_id':'eth:a','payload_json':{'result':{'ok':True,'soft_pass':True,'judgment':{}},'evidence':{'market':{'liquidity_usd':50000},'chain':{}}}}
        self.assertEqual(build_single_audit(row,S)['reason'],'missing_ticket')
if __name__=='__main__':unittest.main()
