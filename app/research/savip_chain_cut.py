"""Exact published Savip CHAIN CUT. Facts only; null does not mean failure."""
from app.strategy.reference_thresholds import HARD

def evaluate_chain(d):
    # Unknown required safety evidence is not a verified safety pass.
    required=("top_wallet_percent","top_10_percent","holder_count")
    missing=[k for k in required if d.get(k) is None]
    if d.get("chain")=="bsc" and d.get("is_honeypot") is None:missing.append("is_honeypot")
    if d.get("chain")=="solana":
        missing.extend(k for k in ("mint_authority","freeze_authority") if d.get(k) is None)
    if missing:return False,"missing_chain_evidence:"+",".join(missing)
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
