import unittest
from datetime import datetime, timezone, timedelta
from app.research.savip_single_shadow_bridge import authorize_single_shadow

NOW=datetime(2026,10,8,tzinfo=timezone.utc)
TOKEN="eth:test"
E={"market":{"proposed_ticket_usd":36.0,"liquidity_usd":50000.0},"chain":{"chain":"eth"},"social":{}}
S={"worth_trading_at_all":0.8,"confidence":0.7,"size_factor":0.5}

def fixtures():
    jev={"id":42,"token_id":TOKEN,"created_at":NOW,"payload_json":{"result":{"ok":True,"soft_pass":True,"judgment":{}},"evidence":E}}
    eligibility={"id":51,"token_id":TOKEN,"created_at":NOW,"payload_json":{"jev_event_id":42,"accepted":True,"reason":"pass","eligibility":S,"decision_type":"standalone_eligibility","shadow_only":True}}
    return eligibility,jev

class BridgeContractTests(unittest.TestCase):
    def test_valid(self):
        a,b=fixtures()
        self.assertEqual(authorize_single_shadow(a,b,NOW)[:3],(True,"pass",0.5))
    def test_fail_closed(self):
        cases=("stale","wrong_token","wrong_event","soft_fail","rejected","low_confidence","missing_chain","nan_ticket","missing_timestamp")
        for case in cases:
            a,b=fixtures()
            if case=="stale": a["created_at"]=NOW-timedelta(seconds=901)
            if case=="wrong_token": a["token_id"]="eth:other"
            if case=="wrong_event": a["payload_json"]["jev_event_id"]=43
            if case=="soft_fail": b["payload_json"]["result"]["soft_pass"]=False
            if case=="rejected": a["payload_json"]["accepted"]=False
            if case=="low_confidence": a["payload_json"]["eligibility"]["confidence"]=0.54
            if case=="missing_chain": b["payload_json"]["evidence"].pop("chain")
            if case=="nan_ticket": b["payload_json"]["evidence"]["market"]["proposed_ticket_usd"]=float("nan")
            if case=="missing_timestamp": b["created_at"]=None
            with self.subTest(case=case):
                self.assertFalse(authorize_single_shadow(a,b,NOW)[0])
if __name__=="__main__": unittest.main()
