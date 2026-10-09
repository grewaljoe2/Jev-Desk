"""Fail-closed tests for dual-atomic shadow owner promotion."""
import unittest
from unittest.mock import AsyncMock
from app.providers.savip_chain import SavipChainProvider

VALID={"status":"atomic_independently_correlated_research",
"shadow_owner_evidence_eligible":True,"cross_provider_owner_match":True,
"positive_balance_coverage_proven":True,"holder_count":85,"supply_amount":100000,
"mint_authority":False,"freeze_authority":False,"owner_balance_digest":"a"*64,
"primary_snapshot_slot":101,"secondary_snapshot_slot":103,
"largest_owner_fraction":0.03,"top_10_percent":40.0}

class AtomicPromotionTests(unittest.IsolatedAsyncioTestCase):
    async def evaluate(self,data):
        provider=SavipChainProvider.__new__(SavipChainProvider)
        provider.fetch_atomic_owner_research=AsyncMock(return_value=data)
        return await provider.fetch_atomic_shadow_owner_evidence("mint")

    async def test_verified_evidence(self):
        result=await self.evaluate(dict(VALID))
        self.assertTrue(result["owner_coverage_complete"])
        self.assertEqual(result["top_wallet_fraction"],0.03)

    async def test_missing_proofs_rejected(self):
        for key,value in (("cross_provider_owner_match",False),
                          ("positive_balance_coverage_proven",False),
                          ("shadow_owner_evidence_eligible",False),
                          ("mint_authority",True),("freeze_authority",True),
                          ("owner_balance_digest","bad"),("holder_count",None)):
            with self.subTest(key=key):
                result=await self.evaluate({**VALID,key:value})
                self.assertFalse(result["owner_coverage_complete"])

    async def test_invalid_concentration_rejected(self):
        for key,value in (("largest_owner_fraction",float("nan")),
                          ("top_10_percent",101.0),("largest_owner_fraction",-0.1)):
            with self.subTest(key=key):
                result=await self.evaluate({**VALID,key:value})
                self.assertFalse(result["owner_coverage_complete"])
