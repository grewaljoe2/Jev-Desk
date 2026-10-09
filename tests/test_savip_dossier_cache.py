import asyncio
import unittest
from unittest.mock import AsyncMock, Mock
from app.providers.savip_dossier import SavipDossierProvider

class DossierCacheTests(unittest.TestCase):
    def test_success_cached_by_chain_and_address_and_not_mutable(self):
        async def check():
            response=Mock()
            response.raise_for_status=Mock()
            response.json.return_value={"data":{"attributes":{"holders":{"count":120,"distribution_percentage":{"top_10":12}}}}}
            gt=Mock(_get=AsyncMock(return_value=response))
            p=SavipDossierProvider(gt_provider=gt)
            try:
                first=await p.fetch("solana","mintA")
                first["holder_count"]=0
                second=await p.fetch("solana","mintA")
                self.assertEqual(second["holder_count"],120)
                self.assertEqual(gt._get.await_count,1)
                await p.fetch("solana","mintB")
                self.assertEqual(gt._get.await_count,2)
            finally:
                await p.client.aclose()
        asyncio.run(check())
    def test_failed_fetch_not_cached(self):
        async def check():
            gt=Mock(_get=AsyncMock(side_effect=RuntimeError("provider_rate_limited_429")))
            p=SavipDossierProvider(gt_provider=gt)
            try:
                for _ in range(2):
                    with self.assertRaises(RuntimeError):
                        await p.fetch("solana","mintA")
                self.assertEqual(gt._get.await_count,2)
            finally:
                await p.client.aclose()
        asyncio.run(check())

if __name__=="__main__":
    unittest.main()
