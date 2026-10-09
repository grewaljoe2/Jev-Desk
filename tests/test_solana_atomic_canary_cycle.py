"""Regression: atomic canary is budgeted per cycle, not per process."""
import asyncio
import unittest
from app.research.savip_chain_worker import SavipChainWorker

class AtomicCanaryCycleTests(unittest.TestCase):
    def test_one_attempt_budget_resets_before_each_cycle(self):
        worker=SavipChainWorker(dossier=None,sol_chain=None)
        observed=[]
        async def fake_evaluate():
            observed.append(getattr(worker,"_atomic_canary_used",None))
            worker._atomic_canary_used=True
        worker._evaluate_cycle=fake_evaluate
        async def run_twice():
            await worker.run_cycle()
            await worker.run_cycle()
        asyncio.run(run_twice())
        self.assertEqual(observed,[False,False])
        self.assertTrue(worker._atomic_canary_used)

if __name__=="__main__":
    unittest.main()
