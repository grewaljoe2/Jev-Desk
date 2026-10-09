"""Cross-provider slot consistency regression. Runs without network."""
import unittest
from unittest.mock import AsyncMock, patch
import asyncio
from app.research.solana_owner_evidence_pipeline import collect_independently_confirmed_owner_evidence

def evidence(slot):
    return {"status":"positive_balance_coverage_proven","positive_balance_coverage_proven":True,
            "accounts_slot":slot,"supply_amount":100,"owner_balance_digest":"same-digest",
            "largest_owner_fraction":0.04,"holder_count":25,"top_10_percent":40.0}

class IndependentOwnerSlotTests(unittest.TestCase):
    def run_pair(self,first,second):
        with patch("app.research.solana_owner_evidence_pipeline.collect_owner_evidence",
                   new=AsyncMock(side_effect=[first,second])):
            return asyncio.run(collect_independently_confirmed_owner_evidence("test-mint"))
    def test_different_slots_fail_closed_despite_same_owner_digest(self):
        result=self.run_pair(evidence(100),evidence(101))
        self.assertEqual(result["status"],"cross_provider_slot_mismatch")
        self.assertFalse(result["owner_coverage_complete"])
        self.assertFalse(result["chain_pass_allowed"])
    def test_matching_slots_can_correlate_but_still_no_chain_pass(self):
        result=self.run_pair(evidence(100),evidence(100))
        self.assertEqual(result["status"],"independently_correlated_research")
        self.assertFalse(result["chain_pass_allowed"])
        self.assertFalse(result["owner_coverage_complete"])
    def test_mint_account_mismatch_retries_once_then_denies(self):
        failure={"status":"mint_accounts_slot_mismatch","positive_balance_coverage_proven":False}
        with patch("app.research.solana_owner_evidence_pipeline.collect_owner_evidence",
                   new=AsyncMock(side_effect=[failure,failure])) as collector:
            result=asyncio.run(collect_independently_confirmed_owner_evidence("test-mint"))
        self.assertEqual(result["failed_provider"],"primary")
        self.assertEqual(result["primary_status"],"mint_accounts_slot_mismatch")
        self.assertEqual(collector.await_count,2)
    def test_mint_account_mismatch_retry_can_recover(self):
        failure={"status":"mint_accounts_slot_mismatch","positive_balance_coverage_proven":False}
        with patch("app.research.solana_owner_evidence_pipeline.collect_owner_evidence",
                   new=AsyncMock(side_effect=[failure,evidence(100),evidence(100)])) as collector:
            result=asyncio.run(collect_independently_confirmed_owner_evidence("test-mint"))
        self.assertEqual(result["status"],"independently_correlated_research")
        self.assertFalse(result["chain_pass_allowed"])
        self.assertEqual(collector.await_count,3)
    def test_same_provider_is_denied(self):
        result=asyncio.run(collect_independently_confirmed_owner_evidence(
            "test-mint",primary_rpc="https://same",secondary_rpc="https://same"))
        self.assertEqual(result["status"],"same_provider")
if __name__=="__main__":
    unittest.main()
