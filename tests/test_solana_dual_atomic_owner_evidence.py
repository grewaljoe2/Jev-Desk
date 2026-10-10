import unittest
from unittest.mock import AsyncMock,patch
from app.research.solana_dual_atomic_owner_evidence import compare_atomic_owner_snapshots

BASE={"status":"atomic_research_reconciled_unverified",
      "positive_balance_coverage_proven":True,
      "owner_balance_digest":"abc","supply_amount":1000,
      "holder_count":100,"top_10_percent":30.0,
      "largest_owner_fraction":0.02,
      "mint_authority":False,"freeze_authority":False,
      "atomic_snapshot_slot":100}

class DualAtomicTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.research.solana_dual_atomic_owner_evidence.collect_atomic_small_mint")
    async def test_different_slots_with_identical_owner_maps(self,collect):
        collect.side_effect=[dict(BASE),{**BASE,"atomic_snapshot_slot":101}]
        result=await compare_atomic_owner_snapshots("mint")
        self.assertEqual(result["status"],"atomic_independently_correlated_research")
        self.assertFalse(result["chain_pass_allowed"])
        self.assertFalse(result["owner_coverage_complete"])

    @patch("app.research.solana_dual_atomic_owner_evidence.collect_atomic_small_mint")
    async def test_mismatched_owner_map_fails_closed(self,collect):
        collect.side_effect=[dict(BASE),{**BASE,"owner_balance_digest":"different"}]
        result=await compare_atomic_owner_snapshots("mint")
        self.assertEqual(result["status"],"cross_provider_atomic_mismatch")
        self.assertFalse(result["chain_pass_allowed"])

    @patch("app.research.solana_dual_atomic_owner_evidence.collect_atomic_small_mint")
    async def test_stale_cross_provider_slot_gap_fails_closed(self,collect):
        collect.side_effect=[dict(BASE),{**BASE,"atomic_snapshot_slot":300}]
        result=await compare_atomic_owner_snapshots("mint")
        self.assertEqual(result["status"],"cross_provider_slot_gap")
        self.assertFalse(result["chain_pass_allowed"])

    @patch("app.research.solana_dual_atomic_owner_evidence.collect_atomic_small_mint")
    async def test_secondary_failure_fails_closed(self,collect):
        collect.side_effect=[dict(BASE),{"status":"atomic_rpc_or_decode_error"}]
        result=await compare_atomic_owner_snapshots("mint")
        self.assertEqual(result["status"],"secondary_unverified")
        self.assertFalse(result["chain_pass_allowed"])

    @patch("app.research.solana_dual_atomic_owner_evidence.collect_full_sliced_snapshot")
    @patch("app.research.solana_dual_atomic_owner_evidence.collect_atomic_small_mint")
    async def test_token_2022_limit_does_not_use_classic_fallback(self,collect,sliced):
        collect.return_value={"status":"atomic_account_limit","token_program":"token_2022"}
        result=await compare_atomic_owner_snapshots("mint")
        self.assertEqual(result["status"],"primary_unverified")
        self.assertFalse(result["chain_pass_allowed"])
        sliced.assert_not_called()

    @patch("app.research.solana_dual_atomic_owner_evidence.collect_full_sliced_snapshot")
    @patch("app.research.solana_dual_atomic_owner_evidence.collect_atomic_small_mint")
    async def test_classic_limit_uses_classic_fallback(self,collect,sliced):
        collect.return_value={"status":"atomic_account_limit","token_program":"classic_spl"}
        sliced.side_effect=[dict(BASE),{**BASE,"atomic_snapshot_slot":101}]
        result=await compare_atomic_owner_snapshots("mint")
        self.assertEqual(result["status"],"atomic_independently_correlated_research")
        self.assertFalse(result["chain_pass_allowed"])
        self.assertEqual(sliced.await_count,2)

if __name__=="__main__":
    unittest.main()
