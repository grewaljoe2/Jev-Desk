import unittest
from app.core.models import TokenSnapshot
from app.providers.geckoterminal import GeckoTerminalDiscovery

class EarlyDiscoveryTests(unittest.TestCase):
    def sample(self,**overrides):
        facts=dict(token_id="solana:abc",address="abc",chain="solana",ticker="ABC",age_minutes=5,liquidity_usd=12000,mcap_usd=35000,volume_h24_usd=0)
        facts.update(overrides)
        return TokenSnapshot(**facts)
    def test_newborn_admitted_without_old_24h_volume(self):
        self.assertIsNone(GeckoTerminalDiscovery._discovery_gate(self.sample()))
    def test_old_60_minute_token_excluded(self):
        self.assertEqual(GeckoTerminalDiscovery._discovery_gate(self.sample(age_minutes=60)),"age")
    def test_missing_age_fails_closed(self):
        self.assertEqual(GeckoTerminalDiscovery._discovery_gate(self.sample(age_minutes=None)),"missing_age")
    def test_liquidity_and_cap_still_required(self):
        self.assertEqual(GeckoTerminalDiscovery._discovery_gate(self.sample(liquidity_usd=9999)),"liquidity")
        self.assertEqual(GeckoTerminalDiscovery._discovery_gate(self.sample(mcap_usd=29999)),"market_cap")
if __name__=="__main__":unittest.main()
