import asyncio,base64,json,unittest,httpx
from app.research.solana_owner_evidence_pipeline import collect_owner_evidence
from app.research.solana_rpc_owner_decoder import TOKEN_2022,b58encode
MINT_RAW=bytes([7])*32
MINT=b58encode(MINT_RAW)
def token(owner,amount,account):
    raw=bytearray(165);raw[:32]=MINT_RAW;raw[32:64]=bytes([owner])*32
    raw[64:72]=amount.to_bytes(8,"little");raw[108]=1
    return {"pubkey":account,"account":{"owner":TOKEN_2022,"data":[base64.b64encode(raw).decode(),"base64"]}}
def run(*,supply_slot=123,account_slot=123,mint_slot=122,supply="100",program=TOKEN_2022,rate_limit=False,decimals=6):
    calls=[]
    def handler(request):
        data=json.loads(request.content);method=data["method"];calls.append(data)
        if rate_limit:return httpx.Response(429)
        if method=="getAccountInfo":
            raw=bytearray(82);raw[36:44]=(100).to_bytes(8,"little");raw[44]=6;raw[45]=1
            return httpx.Response(200,json={"result":{"context":{"slot":mint_slot},"value":{"owner":program,"data":[base64.b64encode(raw).decode(),"base64"]}}})
        elif method=="getProgramAccounts":return httpx.Response(200,json={"result":{"context":{"slot":account_slot},"value":[token(9,80,"a"),token(8,20,"b")]}})
        else:return httpx.Response(200,json={"result":{"context":{"slot":supply_slot},"value":{"amount":supply,"decimals":decimals}}})
        return httpx.Response(200,json={"result":{"value":value}})
    result=asyncio.run(collect_owner_evidence(MINT,transport=httpx.MockTransport(handler)))
    return result,calls
class PipelineTests(unittest.TestCase):
    def test_reconciles_but_never_passes(self):
        r,c=run()
        self.assertEqual(len(c),3)
        self.assertEqual(r["status"],"reconciled_unverified")
        self.assertTrue(r["amounts_match"])
        self.assertTrue(r["provable_concentration_reject"])
        self.assertFalse(r["chain_pass_allowed"])
        self.assertFalse(r["owner_coverage_complete"])
        self.assertEqual(c[1]["params"][0],TOKEN_2022)
        self.assertEqual(c[1]["params"][1]["minContextSlot"],122)
        self.assertEqual(c[2]["params"][1]["minContextSlot"],123)
    def test_supply_slot_mismatch_fails_closed(self):
        r,c=run(supply_slot=124)
        self.assertEqual(r["status"],"snapshot_slot_mismatch")
        self.assertFalse(r["chain_pass_allowed"])
    def test_stale_supply_slot_is_diagnosed(self):
        r,c=run(supply_slot=122)
        self.assertEqual(r["status"],"stale_supply_snapshot")
        self.assertFalse(r["chain_pass_allowed"])
        self.assertEqual(r["accounts_slot"],123)
        self.assertEqual(r["supply_slot"],122)
    def test_supply_mismatch_fails_closed(self):
        r,c=run(supply="101")
        self.assertEqual(r["status"],"supply_mismatch")
        self.assertFalse(r["chain_pass_allowed"])
    def test_unsupported_program_stops_early(self):
        r,c=run(program="unsupported")
        self.assertEqual(len(c),1)
        self.assertEqual(r["status"],"unsupported_or_missing_mint")
    def test_rate_limit_no_retry(self):
        r,c=run(rate_limit=True)
        self.assertEqual(len(c),1)
        self.assertEqual(r["status"],"rate_limited")
    def test_stale_account_snapshot_fails_closed(self):
        r,c=run(mint_slot=124)
        self.assertEqual(r["status"],"stale_accounts_snapshot")
        self.assertEqual(len(c),2)
        self.assertFalse(r["chain_pass_allowed"])
    def test_wrong_decimals_fail_closed(self):
        r,c=run(decimals=9)
        self.assertEqual(r["status"],"invalid_supply")
        self.assertFalse(r["chain_pass_allowed"])
    def test_bad_supply_fails_closed(self):
        r,c=run(supply="not-a-number")
        self.assertEqual(r["status"],"invalid_supply")
if __name__=="__main__":unittest.main()
