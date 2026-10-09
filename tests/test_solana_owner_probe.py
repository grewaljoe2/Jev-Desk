"""No external RPC traffic. Mock one-shot owner enumeration responses."""
import asyncio
import base64
import json
import unittest
import httpx
from app.research.solana_owner_probe import probe_owner_accounts
from app.research.solana_rpc_owner_decoder import TOKEN_PROGRAM,b58encode

MINT=b58encode(bytes([7])*32)

def run(handler, **kw):
    return asyncio.run(probe_owner_accounts(MINT,TOKEN_PROGRAM,
        transport=httpx.MockTransport(handler),**kw))

def token_account():
    raw=bytearray(165)
    raw[:32]=bytes([7])*32
    raw[32:64]=bytes([9])*32
    raw[64:72]=(5).to_bytes(8,"little")
    raw[108]=1
    return {"pubkey":"account1","account":{"owner":TOKEN_PROGRAM,
            "data":[base64.b64encode(raw).decode(),"base64"]}}

class OwnerProbeTests(unittest.TestCase):
    def test_valid_response_is_still_unverified(self):
        calls=[]
        def handler(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200,json={"jsonrpc":"2.0","result":
                {"context":{"slot":123},"value":[token_account()]},"id":1})
        result=run(handler)
        self.assertEqual(result["status"],"decoded_unverified")
        self.assertFalse(result["owner_coverage_complete"])
        self.assertEqual(result["token_accounts"],1)
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]["method"],"getProgramAccounts")
        self.assertIn({"dataSize":165}, calls[0]["params"][1]["filters"])
    def test_rate_limit_no_retry(self):
        calls=[]
        def handler(request):
            calls.append(1)
            return httpx.Response(429)
        self.assertEqual(run(handler)["status"],"rate_limited")
        self.assertEqual(len(calls),1)
    def test_response_cap(self):
        self.assertEqual(run(lambda req:httpx.Response(200,content=b"x"*200),
                             max_bytes=20)["status"],"response_too_large")
    def test_rpc_error(self):
        self.assertEqual(run(lambda req:httpx.Response(200,json={"error":{"code":-32005}}))["status"],"rpc_error")
    def test_timeout_distinguished(self):
        def handler(request):
            raise httpx.ReadTimeout("simulated")
        self.assertEqual(run(handler)["status"],"timeout")
    def test_connection_error_distinguished(self):
        def handler(request):
            raise httpx.ConnectError("simulated")
        self.assertEqual(run(handler)["status"],"connection_error")
    def test_invalid_rpc_response_distinguished(self):
        self.assertEqual(run(lambda req:httpx.Response(200,content=b"not-json"))["status"],
                         "invalid_rpc_response")
    def test_invalid_program_no_network(self):
        result=asyncio.run(probe_owner_accounts(MINT,"invalid"))
        self.assertEqual(result["status"],"invalid_request")

if __name__=="__main__":
    unittest.main()
