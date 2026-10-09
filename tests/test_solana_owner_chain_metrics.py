import unittest
from unittest.mock import AsyncMock,patch
from app.research.solana_owner_reconciliation import reconcile_owner_balances
from app.providers.savip_chain import SavipChainProvider
from app.research.solana_rpc_owner_decoder import TOKEN_PROGRAM
MINT="mint-test"
def snapshot(amounts):
    return {"slot":123,"owner_coverage_complete":False,
            "rows":[{"account":"account"+str(i),"owner":"owner"+str(i),"amount":v,
                     "mint":MINT,"program":TOKEN_PROGRAM,"slot":123}
                    for i,v in enumerate(amounts)]}
class OwnerMetricsTests(unittest.IsolatedAsyncioTestCase):
    def test_positive_holders_and_top_ten(self):
        result=reconcile_owner_balances(snapshot([20]+[8]*10+[0]),mint=MINT,
                 program=TOKEN_PROGRAM,supply_amount=100,supply_slot=123)
        self.assertEqual(result["holder_count"],11)
        self.assertAlmostEqual(result["top_10_percent"],92)
        self.assertEqual(result["unique_owners"],12)
        self.assertFalse(result["chain_pass_allowed"])
    async def test_provider_propagates_complete_metrics(self):
        proof={"status":"independently_correlated_research","cross_provider_owner_match":True,
               "positive_balance_coverage_proven":True,"largest_owner_fraction":0.04,
               "holder_count":90,"top_10_percent":32.5}
        with patch("app.providers.savip_chain.collect_independently_confirmed_owner_evidence",new=AsyncMock(return_value=proof)):
            provider=SavipChainProvider()
            try:result=await provider.fetch_independent_owner_evidence("mint")
            finally:await provider.client.aclose()
        self.assertTrue(result["owner_coverage_complete"])
        self.assertEqual(result["holder_count"],90)
        self.assertEqual(result["top_10_percent"],32.5)
    async def test_provider_rejects_missing_metrics(self):
        proof={"status":"independently_correlated_research","cross_provider_owner_match":True,
               "positive_balance_coverage_proven":True,"largest_owner_fraction":0.04}
        with patch("app.providers.savip_chain.collect_independently_confirmed_owner_evidence",new=AsyncMock(return_value=proof)):
            provider=SavipChainProvider()
            try:result=await provider.fetch_independent_owner_evidence("mint")
            finally:await provider.client.aclose()
        self.assertFalse(result["owner_coverage_complete"])
if __name__=="__main__":unittest.main()
