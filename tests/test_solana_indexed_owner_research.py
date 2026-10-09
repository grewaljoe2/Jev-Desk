import asyncio
import json
import unittest
import httpx
from app.research.solana_indexed_owner_research import collect_indexed_owner_research

MINT="mint-example"
def run(pages, **kwargs):
    calls=[]
    def handler(request):
        body=json.loads(request.content)
        calls.append(body)
        page=body["params"]["page"]
        return httpx.Response(200,json={"result":{"token_accounts":pages.get(page,[]), "total":sum(len(v) for v in pages.values()), "last_indexed_slot":12345}})
    result=asyncio.run(collect_indexed_owner_research(MINT,api_key="test-key",
        page_size=2,transport=httpx.MockTransport(handler),**kwargs))
    return result,calls

def account(address,owner,amount):
    return {"address":address,"mint":MINT,"owner":owner,"amount":amount}

class IndexedResearchTests(unittest.TestCase):
    def test_aggregates_and_never_authorizes(self):
        r,c=run({1:[account("a","owner1",30),account("b","owner1",20)],
                 2:[account("c","owner2",50)]})
        self.assertEqual(r["status"],"empty_page_exhausted_unverified")
        self.assertEqual(r["accounts_total"],100)
        self.assertEqual(r["largest_owner_amount"],50)
        self.assertEqual(r["unique_owners"],2)
        self.assertEqual(len(c),3)
        self.assertFalse(r["owner_coverage_complete"])
        self.assertFalse(r["chain_pass_allowed"])
    def test_rejects_duplicate_across_pages(self):
        r,_=run({1:[account("a","owner1",30),account("b","owner1",20)],
                 2:[account("a","owner2",50)]})
        self.assertEqual(r["status"],"duplicate_or_missing_account")
    def test_rejects_wrong_mint(self):
        bad=account("a","owner1",1)
        bad["mint"]="other"
        r,_=run({1:[bad]})
        self.assertEqual(r["status"],"mint_mismatch")
    def test_cap_is_fail_closed(self):
        r,_=run({1:[account("a","o",1),account("b","o",1)]},max_pages=1)
        self.assertEqual(r["status"],"page_cap_reached")
        self.assertFalse(r["chain_pass_allowed"])
    def test_missing_index_metadata_fails_closed(self):
        def handler(request):
            return httpx.Response(200,json={"result":{"token_accounts":[]}})
        r=asyncio.run(collect_indexed_owner_research(MINT,api_key="test",
            transport=httpx.MockTransport(handler)))
        self.assertEqual(r["status"],"missing_index_metadata")
        self.assertFalse(r["chain_pass_allowed"])
    def test_full_page_reported_total_is_ambiguous(self):
        r,_=run({1:[account("a","owner1",30),account("b","owner2",20)]})
        self.assertEqual(r["status"],"empty_page_exhausted_unverified")
        self.assertFalse(r["owner_coverage_complete"])
        self.assertFalse(r["chain_pass_allowed"])
    def test_requires_key(self):
        r=asyncio.run(collect_indexed_owner_research(MINT,api_key=""))
        self.assertEqual(r["status"],"invalid_input")
if __name__=="__main__":unittest.main()
