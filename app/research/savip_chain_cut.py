"""Exact published Savip CHAIN CUT. Facts only; null does not mean failure."""
from app.strategy.reference_thresholds import HARD

def known_chain_kill(d):
    """One-sided deterministic CHAIN rejection before optional Solana RPC.

    Unknown facts never become a pass. Match the published CHAIN kill order
    after the top-wallet check, without claiming owner verification.
    """
    t10=d.get("top_10_percent")
    if t10 is not None and float(t10)/100>HARD["max_top_10"]:
        return "top_10"
    hc=d.get("holder_count")
    if hc is not None and int(hc)<HARD["min_holders"]:
        return "holders"
    if d.get("chain")=="solana" and (_authority_open(d.get("mint_authority")) or _authority_open(d.get("freeze_authority"))):
        return "authority_open"
    if d.get("chain")=="bsc" and d.get("is_honeypot") is True:
        return "honeypot"
    return None

def evaluate_chain(d):
    if d.get("chain")=="solana" and (d.get("solana_wallet_rpc_status")!="ok" or d.get("top_wallet_percent") is None):
        return False,"solana_owner_unverified"
    tw=d.get("top_wallet_percent")
    if tw is not None and float(tw)>HARD["max_top_wallet"]:return False,"top_wallet"
    t10=d.get("top_10_percent")
    if t10 is not None and float(t10)/100>HARD["max_top_10"]:return False,"top_10"
    hc=d.get("holder_count")
    if hc is not None and int(hc)<HARD["min_holders"]:return False,"holders"
    if d.get("chain")=="solana" and (_authority_open(d.get("mint_authority")) or _authority_open(d.get("freeze_authority"))):
        return False,"authority_open"
    if d.get("chain")=="bsc" and d.get("is_honeypot") is True:
        return False,"honeypot"
    return True,"pass"


def _authority_open(v):
    if v is None:return False
    if isinstance(v,bool):return v
    return str(v).strip().lower() not in ("","no","none","null","false","0","disabled","revoked")
