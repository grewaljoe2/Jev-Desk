"""Solana token accounts cannot certify wallet owner concentration."""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from app.providers.savip_chain import SavipChainProvider

class SolanaAccountSafetyTests(unittest.TestCase):
    def test_largest_account_is_not_verified_owner(self):
        async def check():
            p=SavipChainProvider()
            p._rpc=AsyncMock(side_effect=[
                {"value":{"amount":"1000"}},
                {"value":[{"amount":"20"},{"amount":"10"}]}
            ])
            result=await p.fetch("solana","So11111111111111111111111111111111111111112")
            self.assertIsNone(result["top_wallet_fraction"])
            self.assertFalse(result["owner_coverage_complete"])
            self.assertEqual(result["largest_token_account_fraction"],0.02)
            await p.client.aclose()
        asyncio.run(check())

if __name__=="__main__":
    unittest.main()
