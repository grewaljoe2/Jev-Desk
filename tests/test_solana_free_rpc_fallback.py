import asyncio
import unittest
import httpx
from app.providers.savip_chain import SavipChainProvider

class SolanaFreeFallbackTests(unittest.TestCase):
    def test_primary_429_selects_fallback_without_pass(self):
        async def check():
            calls=[]
            def handler(request):
                calls.append(str(request.url))
                if "mainnet-beta" in str(request.url):
                    return httpx.Response(429,headers={"Retry-After":"120"})
                return httpx.Response(200,json={"jsonrpc":"2.0","id":1,"result":{"value":{"amount":"100"}}})
            provider=SavipChainProvider()
            await provider.client.aclose()
            provider.client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
            try:
                with self.assertRaisesRegex(RuntimeError,"fallback_selected_429"):
                    await provider.fetch("solana","mint")
                self.assertEqual(provider._active_rpc,provider.FALLBACK_RPC)
                self.assertEqual(len(calls),1)
                self.assertFalse(provider.cooling_down())
            finally:
                await provider.client.aclose()
        asyncio.run(check())

    def test_no_verified_owner_pass_on_fallback(self):
        async def check():
            def handler(request):
                method=__import__("json").loads(request.content)["method"]
                value={"amount":"100"} if method=="getTokenSupply" else [{"amount":"4"}]
                return httpx.Response(200,json={"jsonrpc":"2.0","id":1,"result":{"value":value}})
            provider=SavipChainProvider()
            await provider.client.aclose()
            provider.client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
            provider._active_rpc=provider.FALLBACK_RPC
            provider._next_call_at=0
            try:
                result=await provider.fetch("solana","mint")
                self.assertFalse(result["owner_coverage_complete"])
                self.assertIsNone(result["top_wallet_fraction"])
                self.assertEqual(result["largest_token_account_fraction"],.04)
            finally:
                await provider.client.aclose()
        asyncio.run(check())
