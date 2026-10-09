import asyncio
import unittest
from unittest.mock import AsyncMock, patch
from app.providers.savip_chain import SavipChainProvider

class ProductionIndependentOwnerGateTests(unittest.TestCase):
    def test_two_provider_verified_owner_fraction(self):
        async def check():
            p=SavipChainProvider()
            try:
                evidence={"status":"independently_correlated_research",
                          "cross_provider_owner_match":True,
                          "positive_balance_coverage_proven":True,
                          "largest_owner_fraction":.04}
                with patch("app.providers.savip_chain.collect_independently_confirmed_owner_evidence",new=AsyncMock(return_value=evidence)):
                    result=await p.fetch_independent_owner_evidence("mint")
                self.assertTrue(result["owner_coverage_complete"])
                self.assertEqual(result["top_wallet_fraction"],.04)
            finally:
                await p.client.aclose()
        asyncio.run(check())

    def test_unverified_or_single_source_never_passes(self):
        async def check():
            p=SavipChainProvider()
            try:
                for evidence in (
                    {"status":"reconciled_unverified","largest_owner_fraction":.01},
                    {"status":"independently_correlated_research","cross_provider_owner_match":True,
                     "positive_balance_coverage_proven":False,"largest_owner_fraction":.01},
                    {"status":"independently_correlated_research","cross_provider_owner_match":True,
                     "positive_balance_coverage_proven":True,"largest_owner_fraction":None},
                ):
                    with patch("app.providers.savip_chain.collect_independently_confirmed_owner_evidence",new=AsyncMock(return_value=evidence)):
                        result=await p.fetch_independent_owner_evidence("mint")
                    self.assertFalse(result["owner_coverage_complete"])
            finally:
                await p.client.aclose()
        asyncio.run(check())
