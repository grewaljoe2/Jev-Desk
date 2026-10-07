"""Exact published Savip CHAIN CUT. Facts only; null does not mean failure."""
from app.strategy.reference_thresholds import HARD

def evaluate_chain(d):
    tw=d.get("top_wallet_percent")
    if tw is not None and float(tw)>HARD["max_top_wallet"]:return False,"top_wallet"
    t10=d.get("top_10_percent")
    if t10 is not None and float(t10)/100>HARD["max_top_10"]:return False,"top_10"
    hc=d.get("holder_count")
    if hc is not None and int(hc)<HARD["min_holders"]:return False,"holders"
    if d.get("chain")=="solana" and (d.get("mint_authority") or d.get("freeze_authority")):
        return False,"authority_open"
    if d.get("chain")=="bsc" and d.get("is_honeypot") is True:
        return False,"honeypot"
    return True,"pass"
