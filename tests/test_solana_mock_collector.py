"""Synthetic collector fixtures only. No provider traffic."""
import unittest
from app.research.solana_mock_collector import evaluate_mock_collection as evaluate

def rows():
    return [{"account":str(i),"owner":str(i),"amount":50,"mint":"M","program":"token2022","slot":100} for i in range(20)]

def page(index, accounts, slot=100, **kwargs):
    return {"index":index,"accounts":accounts,"slot":slot,**kwargs}

def run(pages, **kwargs):
    return evaluate(pages,1000,mint="M",program="token2022",slot=100,expected_pages=2,complete=True,**kwargs)[0]

class MockCollectorTests(unittest.TestCase):
    def test_complete(self):
        r=rows()
        self.assertEqual(run([page(0,r[:10]),page(1,r[10:])]),"pass")
    def test_missing_page(self):
        self.assertEqual(run([page(0,rows())]),"unverified")
    def test_duplicate_page(self):
        self.assertEqual(run([page(0,rows()[:10]),page(0,rows()[10:])]),"unverified")
    def test_duplicate_account(self):
        r=rows()
        self.assertEqual(run([page(0,r[:10]),page(1,r[:10])]),"unverified")
    def test_wrong_snapshot(self):
        r=rows()
        self.assertEqual(run([page(0,r[:10]),page(1,r[10:],slot=101)]),"unverified")
    def test_rate_limited(self):
        r=rows()
        self.assertEqual(run([page(0,r[:10]),page(1,[],error="429")]),"unverified")
    def test_truncated(self):
        r=rows()
        self.assertEqual(run([page(0,r[:10]),page(1,r[10:],truncated=True)]),"unverified")
    def test_wrong_program(self):
        r=rows()
        r[0]={**r[0],"program":"token"}
        self.assertEqual(run([page(0,r[:10]),page(1,r[10:])]),"unverified")
    def test_unknown_owner(self):
        r=rows()
        r[0]={**r[0],"owner":None}
        self.assertEqual(run([page(0,r[:10]),page(1,r[10:])]),"unverified")
    def test_incomplete_attestation(self):
        r=rows()
        self.assertEqual(evaluate([page(0,r[:10]),page(1,r[10:])],1000,mint="M",program="token2022",slot=100,expected_pages=2,complete=False)[0],"unverified")
