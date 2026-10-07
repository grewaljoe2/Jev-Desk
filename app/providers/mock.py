from app.providers.base import DiscoveryProvider
from app.core.models import TokenSnapshot

class MockDiscovery(DiscoveryProvider):
    async def discover(self) -> list[TokenSnapshot]:
        return [TokenSnapshot(token_id="mock:demo",address="0xDEMO",chain="mock",ticker="DEMO",age_minutes=60,liquidity_usd=50000,volume_h24_usd=100000,mcap_usd=250000,trades_h24=400,buys_h1=40,sells_h1=20,holders=500,top_wallet_fraction=.02,top10_fraction=.25)]
