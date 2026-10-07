"""Exact Savip CHAIN CUT evaluation. Shadow research only."""
from app.strategy.reference_thresholds import HARD

def evaluate_chain(row,facts):
    if not facts:return False,"missing_chain_fact"
    required=("top_wallet_fraction","top10_fraction","holders")
    if any(facts.get(k) is None for k in required):return False,"missing_chain_fact"
    if facts["top_wallet_fraction"]>HARD["max_top_wallet"]:return False,"top_wallet"
    if facts["top10_fraction"]>HARD["max_top_10"]:return False,"top_10"
    if facts["holders"]<HARD["min_holders"]:return False,"holders"
    chain=row.get("chain")
    if chain=="solana":
        if facts.get("authority_open") is None:return False,"missing_chain_fact"
        if facts["authority_open"]:return False,"authority_open"
    if chain=="bsc":
        if facts.get("honeypot") is None:return False,"missing_chain_fact"
        if facts["honeypot"]:return False,"honeypot"
    return True,"pass"
