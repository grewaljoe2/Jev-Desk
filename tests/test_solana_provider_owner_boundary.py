"""Provider boundary refuses forged or incomplete cross-provider slot evidence."""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch
from app.providers.savip_chain import SavipChainProvider

def correlated(**changes):
    value={"status":"independently_correlated_research","cross_provider_owner_match":True,
           "positive_balance_coverage_proven":True,"cross_provider_same_slot":True,
           "primary_snapshot_slot":100,"secondary_snapshot_slot":100,
           "largest_owner_fraction":0.04,"holder_count":25,"top_10_percent":40.0}
    value.update(changes)
    return value

class ProviderOwnerBoundaryTests(unittest.TestCase):
    def check(self,evidence):
        with patch("app.providers.savip_chain.collect_independently_confirmed_owner_evidence",
                   new=AsyncMock(return_value=evidence)):
            provider=SavipChainProvider()
            try:
                return asyncio.run(provider.fetch_independent_owner_evidence("test-mint"))
            finally:
                asyncio.run(provider.client.aclose())
    def test_same_slot_can_be_verified(self):
        self.assertTrue(self.check(correlated())["owner_coverage_complete"])
    def test_different_slots_denied_even_with_matching_digest(self):
        self.assertFalse(self.check(correlated(secondary_snapshot_slot=101))["owner_coverage_complete"])
    def test_missing_same_slot_flag_denied(self):
        self.assertFalse(self.check(correlated(cross_provider_same_slot=None))["owner_coverage_complete"])
    def test_missing_slot_denied(self):
        self.assertFalse(self.check(correlated(primary_snapshot_slot=None))["owner_coverage_complete"])
    def test_missing_coverage_denied(self):
        self.assertFalse(self.check(correlated(positive_balance_coverage_proven=False))["owner_coverage_complete"])
if __name__=="__main__":
    unittest.main()
