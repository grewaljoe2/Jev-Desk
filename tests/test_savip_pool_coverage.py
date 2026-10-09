import unittest
from app.research.savip_pool_coverage import summarize_pool_coverage

class PoolCoverageTests(unittest.TestCase):
    def test_pool_identity_and_no_liquidity_summing(self):
        rows=[
          {"token_id":"solana:mint","pool_id":"solana:pool1","dex_id":"raydium","liquidity_usd":12000,"newly_admitted":False},
          {"token_id":"solana:mint","pool_id":"solana:pool2","dex_id":"orca","liquidity_usd":20000,"newly_admitted":True,"experiment_eligible":True},
          {"token_id":"solana:mint","pool_id":"solana:pool2","dex_id":"orca","liquidity_usd":20000,"newly_admitted":True,"experiment_eligible":True}]
        result=summarize_pool_coverage(rows)
        self.assertEqual(result["observed_pools"],2)
        self.assertEqual(result["unique_tokens"],1)
        self.assertEqual(result["tokens"][0]["best_observed_liquidity_usd"],20000)
        self.assertEqual(result["tokens"][0]["pool_count"],2)
        self.assertTrue(result["tokens"][0]["any_newly_admitted"])
