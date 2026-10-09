import asyncio
import base64
import json
import unittest
import httpx
from app.research.solana_owner_evidence_pipeline import collect_owner_evidence
from app.research.solana_rpc_owner_decoder import TOKEN_PROGRAM, b58encode

MINT=b58encode(bytes([3])*32)

class RPCErrorClassificationTests(unittest.TestCase):
    def test_errors_fail_closed_with_specific_status(self):
        cases={-32005:"rpc_node_unhealthy",-32601:"rpc_method_unsupported",
               -32602:"rpc_invalid_params",-32015:"rpc_version_unsupported",
               -32000:"rpc_error"}
        for code,status in cases.items():
            with self.subTest(code=code):
                def handler(request):
                    return httpx.Response(200,json={"jsonrpc":"2.0","id":1,
                        "error":{"code":code,"message":"private provider detail"}})
                r=asyncio.run(collect_owner_evidence(MINT,transport=httpx.MockTransport(handler)))
                self.assertEqual(r["status"],status)
                self.assertFalse(r["chain_pass_allowed"])
                self.assertFalse(r["owner_coverage_complete"])
                self.assertNotIn("private provider detail",str(r))
if __name__=="__main__":unittest.main()
