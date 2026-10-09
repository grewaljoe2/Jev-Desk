"""Offline HTTP-mocked tests against actual Helius cursor collector. No network."""
import asyncio
import base64
import unittest
import httpx
from app.research.solana_helius_cursor_research import collect_cursor_owner_research
from app.research.solana_rpc_owner_decoder import TOKEN_PROGRAM, TOKEN_2022, b58encode

MINT=b58encode(bytes([3])*32)
def acct(name,owner,amount,program=TOKEN_PROGRAM):
    raw=bytearray(77);raw[:32]=bytes([owner])*32;raw[32:40]=amount.to_bytes(8,"little");raw[76]=1
    return {"pubkey":name,"account":{"owner":program,"data":[base64.b64encode(raw).decode(),"base64"]}}
def page(slot,accounts,cursor):
    return {"result":{"context":{"slot":slot},"value":{"accounts":accounts,"paginationKey":cursor}}}

class HeliusCollectorRPCTests(unittest.TestCase):
    def collect(self,pages,**opts):
        calls=[]
        def handler(request):
            calls.append(request)
            response=pages[len(calls)-1]
            return httpx.Response(response) if isinstance(response,int) else httpx.Response(200,json=response)
        result=asyncio.run(collect_cursor_owner_research(MINT,api_key="offline-test-only",transport=httpx.MockTransport(handler),page_size=opts.pop("page_size",2),max_pages=opts.pop("max_pages",3),**opts))
        self.assertIs(result["owner_coverage_complete"],False)
        self.assertIs(result["chain_pass_allowed"],False)
        return result,calls
    def test_same_slot_still_not_certified(self):
        r,_=self.collect([page(100,[acct("A",1,40)],"next"),page(100,[acct("B",2,60)],None)])
        self.assertEqual(r["status"],"cursor_exhausted_unverified")
        self.assertTrue(r["slot_stable"])
        self.assertEqual(r["accounts_total"],100)
    def test_mixed_slot_conserved_supply_still_not_certified(self):
        r,_=self.collect([page(100,[acct("A",1,50)],"next"),page(101,[acct("B",1,50)],None)])
        self.assertEqual(r["status"],"cursor_exhausted_unverified")
        self.assertEqual(r["largest_owner_amount"],100)
        self.assertFalse(r["slot_stable"])
    def test_duplicate_fails_closed(self):
        r,_=self.collect([page(100,[acct("A",1,40)],"next"),page(101,[acct("A",1,40)],None)])
        self.assertEqual(r["status"],"duplicate_account")
    def test_missing_cursor_fails_closed(self):
        p=page(100,[acct("A",1,40)],None);del p["result"]["value"]["paginationKey"]
        r,_=self.collect([p]);self.assertEqual(r["status"],"missing_pagination_key")
    def test_page_cap_fails_closed(self):
        r,_=self.collect([page(100,[acct("A",1,40)],"next")],max_pages=1)
        self.assertEqual(r["status"],"page_cap_reached")
    def test_rate_limit_fails_closed(self):
        r,_=self.collect([429]);self.assertEqual(r["status"],"rate_limited")
    def test_wrong_program_fails_closed(self):
        r,_=self.collect([page(100,[acct("A",1,40,TOKEN_2022)],None)])
        self.assertEqual(r["status"],"invalid_provider_data")
    def test_token_2022_diagnostic_only(self):
        r,_=self.collect([page(100,[acct("A",1,40,TOKEN_2022)],None)],program=TOKEN_2022)
        self.assertEqual(r["status"],"cursor_exhausted_unverified")
    def test_research_page_size_10000(self):
        r,_=self.collect([page(100,[acct("A",1,40)],None)],page_size=10000)
        self.assertEqual(r["status"],"cursor_exhausted_unverified")

if __name__=="__main__":unittest.main()
