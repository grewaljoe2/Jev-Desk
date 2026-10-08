"""Offline fixtures; never touch Solana RPC."""
from app.research.solana_owner_coverage import verify_owner_concentration as check

def test_split_accounts_reject():
    assert check([{"owner":"A","amount":30},{"owner":"A","amount":30},{"owner":"B","amount":940}],1000,complete=True)[0]=="reject"

def test_incomplete_never_passes():
    assert check([{"owner":"A","amount":20},{"owner":"B","amount":20}],1000,complete=False)[0]=="unverified"

def test_complete_distribution_pass():
    assert check([{"owner":str(i),"amount":50} for i in range(20)],1000,complete=True)==("pass",0.05)

def test_unknown_owner_fail_closed():
    assert check([{"owner":None,"amount":1000}],1000,complete=True)[0]=="unverified"

def test_missing_supply_fail_closed():
    assert check([{"owner":"A","amount":100}],None,complete=True)[0]=="unverified"

def test_supply_mismatch_fail_closed():
    assert check([{"owner":str(i),"amount":40} for i in range(20)],1000,complete=True)[0]=="unverified"

def test_oversupply_fail_closed():
    assert check([{"owner":"A","amount":1001}],1000,complete=True)[0]=="unverified"
