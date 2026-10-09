"""Full Solana CHAIN worker decision tests for the opt-in atomic canary."""
import asyncio
import unittest
from unittest.mock import patch
from app.research.savip_chain_worker import SavipChainWorker

TOKEN="solana:TestMint"
ROW={"token_id":TOKEN,"chain":"solana","age_minutes":10}
DOSSIER={"chain":"solana","mint_authority":False,"freeze_authority":False,
         "is_honeypot":False}

class FakeDossier:
    async def fetch(self,chain,address):
        return dict(DOSSIER)

class FakeSolana:
    def __init__(self,fraction,verified=True):
        self.fraction=fraction
        self.verified=verified
        self.preliminary_calls=0
        self.atomic_calls=0
    def cooling_down(self):
        return False
    async def fetch(self,*args):
        self.preliminary_calls+=1
        raise RuntimeError("solana_rpc_rate_limited_429")
    async def fetch_atomic_shadow_owner_evidence(self,address):
        self.atomic_calls+=1
        if not self.verified:
            return {"owner_coverage_complete":False,"status":"cross_provider_atomic_mismatch"}
        return {"owner_coverage_complete":True,"top_wallet_fraction":self.fraction,
                "holder_count":150,"top_10_percent":30.0,
                "source":"dual_atomic_classic_spl"}
    async def fetch_helius_owner_evidence(self,address):
        return {"status":"diagnostic_only"}

class ChainWorkerCanaryIntegrationTests(unittest.TestCase):
    def run_case(self,fraction,verified=True):
        sol=FakeSolana(fraction,verified)
        worker=SavipChainWorker(FakeDossier(),sol,cap=1)
        persisted=[]
        async def pool(**kwargs):
            return {"free_cut_survivors":[ROW]}
        async def trade(rows):
            return {"survivors":rows}
        async def positions():
            return []
        async def recent(**kwargs):
            return set()
        async def persist(token_id,d,ok,reason):
            persisted.append((ok,reason,d))
        worker._persist=persist
        with patch("app.research.savip_chain_worker.open_savip_positions",positions),\
             patch("app.research.savip_chain_worker.savip_candidate_pool",pool),\
             patch("app.research.savip_chain_worker.exact_trade_cut",trade),\
             patch("app.research.savip_chain_worker.savip_recent_chain_tokens",recent),\
             patch("app.research.savip_chain_worker.settings.solana_atomic_canary_enabled",True):
            asyncio.run(worker.run_cycle())
        return worker,sol,persisted

    def test_verified_eligible_wallet_passes_full_chain(self):
        worker,sol,persisted=self.run_case(0.03)
        self.assertEqual(sol.preliminary_calls,0)
        self.assertEqual(sol.atomic_calls,1)
        self.assertEqual(worker.last_passed,1)
        self.assertEqual(persisted[0][0:2],(True,"pass"))
        self.assertEqual(persisted[0][2]["solana_owner_evidence_source"],"dual_atomic_classic_spl")

    def test_verified_concentrated_wallet_rejected(self):
        worker,sol,persisted=self.run_case(0.0819)
        self.assertEqual(sol.preliminary_calls,0)
        self.assertEqual(worker.last_passed,0)
        self.assertEqual(persisted[0][0:2],(False,"top_wallet"))

    def test_unverified_wallet_cannot_pass(self):
        worker,sol,persisted=self.run_case(0.03,False)
        self.assertEqual(worker.last_passed,0)
        self.assertEqual(persisted,[])
        self.assertEqual(worker.last_candidate_results[0]["outcome"],"retry_pending")
