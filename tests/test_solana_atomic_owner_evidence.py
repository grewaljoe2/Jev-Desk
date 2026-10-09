"""Atomic owner evidence must conserve mint supply without enabling CHAIN."""
import asyncio
import base64
import json
import unittest
import httpx
from app.research.solana_atomic_owner_evidence import collect_atomic_small_mint
from app.research.solana_rpc_owner_decoder import TOKEN_PROGRAM, b58encode

MINT=b58encode(bytes([7])*32)
ACCOUNT=b58encode(bytes([9])*32)

def b64(raw):
    return [base64.b64encode(raw).decode(),"base64"]

def mint_value(supply=100,authority_option=0,freeze_option=0):
    raw=bytearray(82)
    raw[36:44]=supply.to_bytes(8,"little")
    raw[45]=1
    raw[0:4]=authority_option.to_bytes(4,"little")
    raw[46:50]=freeze_option.to_bytes(4,"little")
    return {"owner":TOKEN_PROGRAM,"data":b64(raw)}

def token_value(amount=100):
    raw=bytearray(165)
    raw[:32]=bytes([7])*32
    raw[32:64]=bytes([8])*32
    raw[64:72]=amount.to_bytes(8,"little")
    raw[108]=2
    return {"owner":TOKEN_PROGRAM,"data":b64(raw)}

class AtomicOwnerTests(unittest.TestCase):
    def run_case(self,amount=100,accounts=1,missing_account=False,atomic_slot=102,authority_option=0,freeze_option=0):
        def handler(request):
            call=json.loads(request.content)
            method=call["method"]
            if method=="getAccountInfo":
                result={"context":{"slot":100},"value":mint_value()}
            elif method=="getProgramAccounts":
                result={"context":{"slot":101},"value":[{"pubkey":ACCOUNT,"account":{}} for _ in range(accounts)]}
            elif method=="getMultipleAccounts":
                result={"context":{"slot":atomic_slot},"value":[mint_value(authority_option=authority_option,freeze_option=freeze_option),None if missing_account else token_value(amount)]}
            else:
                raise AssertionError(method)
            return httpx.Response(200,json={"jsonrpc":"2.0","id":1,"result":result})
        return asyncio.run(collect_atomic_small_mint(MINT,transport=httpx.MockTransport(handler)))

    def test_atomic_conservation(self):
        result=self.run_case()
        self.assertTrue(result["positive_balance_coverage_proven"])
        self.assertEqual(result["atomic_snapshot_slot"],102)
        self.assertFalse(result["chain_pass_allowed"])

    def test_atomic_missing_balance_fails_closed(self):
        result=self.run_case(amount=99)
        self.assertFalse(result["positive_balance_coverage_proven"])
        self.assertFalse(result["chain_pass_allowed"])

    def test_discovered_account_missing_fails_closed(self):
        result=self.run_case(missing_account=True)
        self.assertEqual(result["status"],"discovered_account_missing")
        self.assertFalse(result["chain_pass_allowed"])

    def test_stale_atomic_slot_fails_closed(self):
        result=self.run_case(atomic_slot=100)
        self.assertEqual(result["status"],"invalid_atomic_response")
        self.assertFalse(result["chain_pass_allowed"])

    def test_malformed_authority_discriminants_fail_closed(self):
        for mint_option,freeze_option in ((2,0),(0,2),(255,0),(0,255)):
            with self.subTest(mint_option=mint_option,freeze_option=freeze_option):
                result=self.run_case(authority_option=mint_option,freeze_option=freeze_option)
                self.assertEqual(result["status"],"invalid_mint_authority_encoding")
                self.assertFalse(result["owner_coverage_complete"])
                self.assertFalse(result["chain_pass_allowed"])

    def test_atomic_account_limit(self):
        result=self.run_case(accounts=100)
        self.assertEqual(result["status"],"atomic_account_limit")
        self.assertFalse(result["chain_pass_allowed"])

if __name__=="__main__":
    unittest.main()
