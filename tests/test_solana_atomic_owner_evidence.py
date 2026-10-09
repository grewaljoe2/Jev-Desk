"""Atomic owner evidence must conserve mint supply without enabling CHAIN."""
import asyncio
import base64
import json
import unittest
import httpx
from app.research.solana_atomic_owner_evidence import collect_atomic_small_mint, collect_full_sliced_snapshot
from app.research.solana_dual_atomic_owner_evidence import compare_atomic_owner_snapshots
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
                self.assertIn(result["status"],("invalid_mint_authority_encoding","atomic_rpc_decode_error"))
                self.assertFalse(result["owner_coverage_complete"])
                self.assertFalse(result["chain_pass_allowed"])

    def test_multi_batch_exact_slot_and_mismatch(self):
        addresses=[b58encode(i.to_bytes(32,"big")) for i in range(1,151)]
        def run(second_slot):
            calls=[]
            def handler(request):
                call=json.loads(request.content)
                method=call["method"]
                if method=="getAccountInfo":
                    result={"context":{"slot":100},"value":mint_value(supply=150)}
                elif method=="getProgramAccounts":
                    result={"context":{"slot":101},"value":[{"pubkey":a,"account":{}} for a in addresses]}
                elif method=="getMultipleAccounts":
                    batch=call["params"][0]
                    calls.append(batch)
                    slot=102 if len(calls)==1 else second_slot
                    result={"context":{"slot":slot},"value":[mint_value(supply=150) if a==MINT else token_value(amount=1) for a in batch]}
                else:
                    raise AssertionError(method)
                return httpx.Response(200,json={"jsonrpc":"2.0","id":1,"result":result})
            evidence=asyncio.run(collect_atomic_small_mint(MINT,transport=httpx.MockTransport(handler)))
            return evidence,calls
        good,calls=run(102)
        self.assertEqual(len(calls),2)
        self.assertTrue(good["positive_balance_coverage_proven"])
        self.assertEqual(good["discovered_accounts"],150)
        self.assertFalse(good["chain_pass_allowed"])
        bad,_=run(103)
        self.assertEqual(bad["status"],"multi_batch_slot_mismatch")
        self.assertFalse(bad["owner_coverage_complete"])

    def test_multi_batch_rejects_missing_account_and_rate_limit(self):
        addresses=[b58encode(i.to_bytes(32,"big")) for i in range(1,151)]
        def run(mode):
            def handler(request):
                call=json.loads(request.content)
                method=call["method"]
                if method=="getAccountInfo":
                    result={"context":{"slot":100},"value":mint_value(supply=150)}
                elif method=="getProgramAccounts":
                    result={"context":{"slot":101},"value":[{"pubkey":a,"account":{}} for a in addresses]}
                elif method=="getMultipleAccounts":
                    batch=call["params"][0]
                    if mode=="rate_limit" and MINT not in batch:
                        return httpx.Response(429,text="rate limited")
                    values=[mint_value(supply=150) if a==MINT else token_value(amount=1) for a in batch]
                    if mode=="missing" and MINT not in batch:
                        values[0]=None
                    result={"context":{"slot":102},"value":values}
                else:
                    raise AssertionError(method)
                return httpx.Response(200,json={"jsonrpc":"2.0","id":1,"result":result})
            return asyncio.run(collect_atomic_small_mint(MINT,transport=httpx.MockTransport(handler)))
        missing=run("missing")
        self.assertEqual(missing["status"],"discovered_account_missing")
        self.assertFalse(missing["chain_pass_allowed"])
        limited=run("rate_limit")
        self.assertEqual(limited["status"],"atomic_rpc_rate_limited")
        self.assertEqual(limited["rpc_method"],"getMultipleAccounts")
        self.assertFalse(limited["owner_coverage_complete"])

    def test_maximum_299_accounts_reconcile(self):
        addresses=[b58encode(i.to_bytes(32,"big")) for i in range(1,300)]
        batch_sizes=[]
        def handler(request):
            call=json.loads(request.content)
            method=call["method"]
            if method=="getAccountInfo":
                result={"context":{"slot":100},"value":mint_value(supply=299)}
            elif method=="getProgramAccounts":
                result={"context":{"slot":101},"value":[{"pubkey":a,"account":{}} for a in addresses]}
            elif method=="getMultipleAccounts":
                batch=call["params"][0]
                batch_sizes.append(len(batch))
                result={"context":{"slot":102},"value":[mint_value(supply=299) if a==MINT else token_value(amount=1) for a in batch]}
            else:
                raise AssertionError(method)
            return httpx.Response(200,json={"jsonrpc":"2.0","id":1,"result":result})
        evidence=asyncio.run(collect_atomic_small_mint(MINT,transport=httpx.MockTransport(handler)))
        self.assertEqual(batch_sizes,[100,100,100])
        self.assertEqual(evidence["discovered_accounts"],299)
        self.assertTrue(evidence["positive_balance_coverage_proven"])
        self.assertFalse(evidence["chain_pass_allowed"])

    def test_atomic_account_limit(self):
        result=self.run_case(accounts=300)
        self.assertEqual(result["status"],"atomic_account_limit")
        self.assertFalse(result["chain_pass_allowed"])

if __name__=="__main__":
    unittest.main()

class FullSlicedSnapshotTests(unittest.TestCase):
    def test_large_sliced_same_slot_reconciles(self):
        count=350
        rows=[]
        for i in range(count):
            raw=bytearray(77)
            raw[:32]=i.to_bytes(32,"big")
            raw[32:40]=(1).to_bytes(8,"little")
            raw[76]=2
            rows.append({"pubkey":b58encode((i+1000).to_bytes(32,"big")),
                         "account":{"owner":TOKEN_PROGRAM,"data":b64(raw)}})
        def handler(request):
            call=json.loads(request.content)
            if call["method"]=="getProgramAccounts":
                result={"context":{"slot":120},"value":rows}
            elif call["method"]=="getAccountInfo":
                result={"context":{"slot":120},"value":mint_value(supply=count)}
            else:
                raise AssertionError(call["method"])
            return httpx.Response(200,json={"jsonrpc":"2.0","id":1,"result":result})
        result=asyncio.run(collect_full_sliced_snapshot(MINT,transport=httpx.MockTransport(handler)))
        self.assertTrue(result["positive_balance_coverage_proven"])
        self.assertEqual(result["holder_count"],count)
        self.assertEqual(result["discovered_accounts"],count)
        self.assertFalse(result["chain_pass_allowed"])

    def test_bracketed_supply_across_distinct_slots(self):
        raw=bytearray(77)
        raw[:32]=bytes([8])*32
        raw[32:40]=(100).to_bytes(8,"little")
        raw[76]=2
        calls=[0]
        def handler(request):
            method=json.loads(request.content)["method"]
            if method=="getProgramAccounts":
                result={"context":{"slot":121},"value":[{"pubkey":ACCOUNT,
                    "account":{"owner":TOKEN_PROGRAM,"data":b64(raw)}}]}
            else:
                calls[0]+=1
                result={"context":{"slot":120 if calls[0]==1 else 122},
                        "value":mint_value(supply=100)}
            return httpx.Response(200,json={"jsonrpc":"2.0","id":1,"result":result})
        result=asyncio.run(collect_full_sliced_snapshot(MINT,transport=httpx.MockTransport(handler)))
        self.assertTrue(result["positive_balance_coverage_proven"])
        self.assertEqual((result["mint_before_slot"],result["atomic_snapshot_slot"],result["mint_after_slot"]),(120,121,122))
        self.assertFalse(result["chain_pass_allowed"])

    def test_sliced_slot_mismatch_fails_closed(self):
        raw=bytearray(77)
        raw[32:40]=(100).to_bytes(8,"little")
        raw[76]=2
        def handler(request):
            call=json.loads(request.content)
            if call["method"]=="getProgramAccounts":
                result={"context":{"slot":120},"value":[{"pubkey":ACCOUNT,
                    "account":{"owner":TOKEN_PROGRAM,"data":b64(raw)}}]}
            else:
                result={"context":{"slot":121},"value":mint_value()}
            return httpx.Response(200,json={"jsonrpc":"2.0","id":1,"result":result})
        result=asyncio.run(collect_full_sliced_snapshot(MINT,transport=httpx.MockTransport(handler)))
        self.assertEqual(result["status"],"full_snapshot_slot_mismatch")
        self.assertFalse(result["owner_coverage_complete"])

class DualFullSnapshotIntegrationTests(unittest.TestCase):
    def test_large_mint_dual_provider_shadow_evidence(self):
        count=350
        sliced=[]
        for i in range(count):
            raw=bytearray(77)
            raw[:32]=i.to_bytes(32,"big")
            raw[32:40]=(1).to_bytes(8,"little")
            raw[76]=2
            sliced.append({"pubkey":b58encode((i+1000).to_bytes(32,"big")),
                           "account":{"owner":TOKEN_PROGRAM,"data":b64(raw)}})
        def handler(request):
            call=json.loads(request.content)
            method=call["method"]
            provider_offset=0 if "primary" in str(request.url) else 2
            if method=="getAccountInfo":
                # Initial small-mint probe, then full-snapshot before/after.
                result={"context":{"slot":120+provider_offset},
                        "value":mint_value(supply=count)}
            elif method=="getProgramAccounts":
                if call["params"][1]["dataSlice"]["length"]==0:
                    result={"context":{"slot":120+provider_offset},
                            "value":[{"pubkey":row["pubkey"],"account":{}} for row in sliced]}
                else:
                    result={"context":{"slot":120+provider_offset},"value":sliced}
            else:
                raise AssertionError(method)
            return httpx.Response(200,json={"jsonrpc":"2.0","id":1,"result":result})
        result=asyncio.run(compare_atomic_owner_snapshots(
            MINT,primary_rpc="https://primary.invalid",secondary_rpc="https://secondary.invalid",
            transport=httpx.MockTransport(handler)))
        self.assertEqual(result["status"],"atomic_independently_correlated_research")
        self.assertTrue(result["cross_provider_owner_match"])
        self.assertTrue(result["shadow_owner_evidence_eligible"])
        self.assertEqual(result["holder_count"],count)
        self.assertFalse(result["chain_pass_allowed"])
        self.assertFalse(result["owner_coverage_complete"])
