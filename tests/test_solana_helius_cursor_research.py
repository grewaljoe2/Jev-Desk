import asyncio,base64,json,unittest,httpx
from app.research.solana_helius_cursor_research import collect_cursor_owner_research
from app.research.solana_rpc_owner_decoder import TOKEN_PROGRAM,b58encode
MINT=b58encode(bytes([7])*32)
def row(account,owner,amount):
    raw=bytearray(77);raw[:32]=bytes([owner])*32;raw[32:40]=amount.to_bytes(8,"little");raw[76]=1
    return {"pubkey":account,"account":{"owner":TOKEN_PROGRAM,"data":[base64.b64encode(raw).decode(),"base64"]}}
class CursorTests(unittest.TestCase):
    def test_two_pages_never_authorize(self):
        calls=[]
        def handler(request):
            p=json.loads(request.content);calls.append(p)
            page=len(calls)
            return httpx.Response(200,json={"result":{"context":{"slot":123},"value":{"accounts":[row("a" if page==1 else "b",page,50)],"paginationKey":"next" if page==1 else None}}})
        r=asyncio.run(collect_cursor_owner_research(MINT,api_key="test",transport=httpx.MockTransport(handler)))
        self.assertEqual(r["status"],"cursor_exhausted_unverified")
        self.assertEqual(r["accounts_total"],100)
        self.assertEqual(r["token_accounts"],2)
        self.assertFalse(r["owner_coverage_complete"])
        self.assertFalse(r["chain_pass_allowed"])
        self.assertEqual(calls[1]["params"][1]["paginationKey"],"next")
    def test_duplicate_rejected(self):
        n=[0]
        def handler(request):
            n[0]+=1
            return httpx.Response(200,json={"result":{"context":{"slot":123},"value":{"accounts":[row("a",1,50)],"paginationKey":"next" if n[0]==1 else None}}})
        r=asyncio.run(collect_cursor_owner_research(MINT,api_key="test",transport=httpx.MockTransport(handler)))
        self.assertEqual(r["status"],"duplicate_account")
        self.assertFalse(r["chain_pass_allowed"])
    def test_page_cap_fails_closed(self):
        def handler(request):
            return httpx.Response(200,json={"result":{"context":{"slot":123},"value":{"accounts":[row("a",1,50)],"paginationKey":"next"}}})
        r=asyncio.run(collect_cursor_owner_research(MINT,api_key="test",max_pages=1,transport=httpx.MockTransport(handler)))
        self.assertEqual(r["status"],"page_cap_reached")
        self.assertFalse(r["owner_coverage_complete"])
if __name__=="__main__":unittest.main()
