import unittest
from unittest.mock import AsyncMock
from app.research import savip_pick_worker as module

class SingleSurvivorTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_survivor_never_calls_pick_or_opens_position(self):
        old=(module.open_savip_positions,module.recent_savip_soft_survivors,module.savip_pick_fingerprint_seen)
        try:
            module.open_savip_positions=AsyncMock(return_value=[])
            module.recent_savip_soft_survivors=AsyncMock(return_value=[{"id":11,"token_id":"eth:abc","payload_json":{}}])
            module.savip_pick_fingerprint_seen=AsyncMock(return_value=False)
            provider=type("Provider",(),{"configured":True,"pick":AsyncMock()})()
            worker=module.SavipPickWorker(provider)
            await worker.run_cycle()
            self.assertEqual(worker.state,"single_invalid_source")
            provider.pick.assert_not_awaited()
        finally:
            module.open_savip_positions,module.recent_savip_soft_survivors,module.savip_pick_fingerprint_seen=old
if __name__=="__main__":unittest.main()
