import unittest
from unittest.mock import patch
from app.providers.typesafe_jev import TypeSafeJevProvider
from app.research.savip_single_eligibility import decide_single_eligibility

class Response:
    status_code=200
    def json(self):return {"answers":{"worth_trading_at_all":{"noul":0.8},"confidence":{"noul":0.7},"size_factor":{"noul":0.5}},"model":"mock"}
class Client:
    def __init__(self):self.body=None
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    async def post(self,url,headers,json):
        self.body=json
        assert "candidates" not in json["state"]
        assert json["state"]["token_id"]=="eth:a"
        assert set(json["questions"])=={"worth_trading_at_all","confidence","size_factor"}
        return Response()
class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_is_not_multi_pick(self):
        p=TypeSafeJevProvider();p.api_key="test"
        with patch("app.providers.typesafe_jev.httpx.AsyncClient",return_value=Client()):
            r=await p.judge_single_eligibility("eth:a",{"market":{}},{"market":{"liquidity_usd":50000,"proposed_ticket_usd":36},"chain":{"chain":"eth"}})
        self.assertEqual(r["eligibility"]["confidence"],0.7)
        self.assertTrue(decide_single_eligibility(r["eligibility"],"eth:a","eth:a",{"market":{"liquidity_usd":50000,"proposed_ticket_usd":36},"chain":{"chain":"eth"}})[0])
    async def test_missing_evidence_fails_without_request(self):
        p=TypeSafeJevProvider();p.api_key="test"
        with self.assertRaises(ValueError):
            await p.judge_single_eligibility("eth:a",{},None)
if __name__=="__main__":unittest.main()
