import unittest
from unittest.mock import AsyncMock, patch
from app.research.solana_owner_evidence_pipeline import collect_independently_confirmed_owner_evidence

def evidence(slot=100,digest="a",supply=100):
    return {"status":"reconciled_unverified","positive_balance_coverage_proven":True,
            "accounts_slot":slot,"supply_amount":supply,"owner_balance_digest":digest,
            "largest_owner_fraction":.04}

class IndependentConfirmationTests(unittest.IsolatedAsyncioTestCase):
    async def test_identical_snapshots_remain_research_only(self):
        with patch("app.research.solana_owner_evidence_pipeline.collect_owner_evidence",new=AsyncMock(side_effect=[evidence(),evidence()])):
            r=await collect_independently_confirmed_owner_evidence("mint")
        self.assertEqual(r["status"],"independently_correlated_research")
        self.assertTrue(r["cross_provider_owner_match"])
        self.assertFalse(r["owner_coverage_complete"])
        self.assertFalse(r["chain_pass_allowed"])

    async def test_owner_disagreement_fails_closed(self):
        with patch("app.research.solana_owner_evidence_pipeline.collect_owner_evidence",new=AsyncMock(side_effect=[evidence(),evidence(digest="b")])):
            r=await collect_independently_confirmed_owner_evidence("mint")
        self.assertEqual(r["status"],"cross_provider_owner_mismatch")

    async def test_slot_disagreement_fails_closed(self):
        with patch("app.research.solana_owner_evidence_pipeline.collect_owner_evidence",new=AsyncMock(side_effect=[evidence(),evidence(slot=101)])):
            r=await collect_independently_confirmed_owner_evidence("mint")
        self.assertEqual(r["status"],"independently_correlated_research")\n        self.assertFalse(r["owner_coverage_complete"])

    async def test_same_rpc_is_not_independent(self):
        r=await collect_independently_confirmed_owner_evidence("mint",primary_rpc="same",secondary_rpc="same")
        self.assertEqual(r["status"],"same_provider")

