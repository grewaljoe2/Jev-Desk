"""One-sided Solana concentration check using token-account lower bounds.

An individual token account belongs to one owner. Therefore an account exceeding
the owner limit proves its owner exceeds it. The converse is not true.
"""
import math
from app.strategy.reference_thresholds import HARD

def classify_account_lower_bound(fraction):
    if isinstance(fraction,bool) or not isinstance(fraction,(int,float)) or not math.isfinite(fraction) or fraction < 0 or fraction > 1:
        return "unverified"
    return "reject" if fraction > HARD["max_top_wallet"] else "unverified"
