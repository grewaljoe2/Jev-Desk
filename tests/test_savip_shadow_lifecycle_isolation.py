"""Isolated shadow lifecycle checks. No database, API calls or production trades."""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.research.savip_shadow_lifecycle import SavipShadowRiskWorker
from app.research.savip_shadow_execution import simulated_market_fill, ticket_usd
from app.research.savip_risk import risk_decision
from app.strategy.reference_thresholds import RISK


class FakeMarket:
    def __init__(self, observation):
        self.observation = observation

    async def observe(self, token):
        return self.observation


class ShadowLifecycleIsolationTests(unittest.TestCase):
    def test_sizing_and_fill(self):
        ticket = ticket_usd(1000, 50000, 0.8, missing_x=True)
        self.assertGreater(ticket, 0)
        fill = simulated_market_fill(ticket, 0.02)
        self.assertGreater(fill["quantity"], 0)
        self.assertLess(fill["net_asset_usd"], ticket)
        self.assertEqual(fill["fill_type"], "market_shadow")

    def test_risk_decisions(self):
        self.assertEqual(risk_decision(250, 1000)["action"], "hold")
        self.assertEqual(risk_decision(0, 1000)["action"], "close_100")
        self.assertEqual(risk_decision(None, None, RISK["data_retries"] + 1)["action"], "close_100")

    def test_worker_hold_and_close_without_production_writes(self):
        async def scenario():
            pos = {"id": 123, "token_id": "test-only:token"}
            observations = {"price_usd": 0.02, "volume_6h": 250, "volume_24h": 1000}
            events = []
            async def record(kind, token, payload):
                events.append((kind, token, payload))
            with patch("app.research.savip_shadow_lifecycle.open_savip_positions", new=AsyncMock(return_value=[pos])), \
                 patch("app.research.savip_shadow_lifecycle.log_savip_lifecycle", new=record), \
                 patch("app.research.savip_shadow_lifecycle.close_book_position", new=AsyncMock(return_value=True)) as close:
                worker = SavipShadowRiskWorker(FakeMarket(observations))
                await worker.run_cycle()
                self.assertEqual(worker.state, "hold")
                close.assert_not_awaited()
                worker.market_provider.observation = {"price_usd": 0.018, "volume_6h": 0, "volume_24h": 1000}
                await worker.run_cycle()
                self.assertEqual(worker.state, "closed")
                close.assert_awaited_once_with(123, 0.018)
            self.assertEqual([x[0] for x in events], ["SAVIP_RISK", "SAVIP_RISK", "SAVIP_SHADOW_EXIT"])
            self.assertFalse(events[-1][2]["real_execution"])
        asyncio.run(scenario())

    def test_restart_reloads_position(self):
        async def scenario():
            pos = {"id": 456, "token_id": "test-only:restart"}
            with patch("app.research.savip_shadow_lifecycle.open_savip_positions", new=AsyncMock(return_value=[pos])) as lookup, \
                 patch("app.research.savip_shadow_lifecycle.log_savip_lifecycle", new=AsyncMock()), \
                 patch("app.research.savip_shadow_lifecycle.close_book_position", new=AsyncMock(return_value=True)):
                first = SavipShadowRiskWorker(FakeMarket({"price_usd": 1, "volume_6h": 250, "volume_24h": 1000}))
                await first.run_cycle()
                restarted = SavipShadowRiskWorker(FakeMarket({"price_usd": 1, "volume_6h": 250, "volume_24h": 1000}))
                await restarted.run_cycle()
                self.assertEqual(lookup.await_count, 2)
                self.assertEqual(restarted.state, "hold")
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
