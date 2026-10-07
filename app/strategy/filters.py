from app.core.models import TokenSnapshot
from app.strategy.reference_thresholds import HARD

def reference_fact_filter(s: TokenSnapshot)->tuple[bool,str]:
    required={"age_minutes":s.age_minutes,"liquidity_usd":s.liquidity_usd,"volume_h24_usd":s.volume_h24_usd,"mcap_usd":s.mcap_usd}
    missing=[k for k,v in required.items() if v is None]
    if missing:return False,"missing:"+",".join(missing)
    if s.age_minutes < HARD["min_age_minutes"]:return False,"age_too_young"
    if s.age_minutes > HARD["max_age_hours"]*60:return False,"age_too_old"
    if s.liquidity_usd < HARD["min_liquidity_usd"]:return False,"liquidity"
    if s.volume_h24_usd < HARD["min_volume_h24"]:return False,"volume"
    if s.mcap_usd < HARD["min_mcap_usd"]:return False,"mcap_low"
    if s.mcap_usd > HARD["max_mcap_usd"]:return False,"mcap_high"
    if s.trades_h24 is not None and s.trades_h24 < HARD["min_trades_h24"]:return False,"trades"
    if s.top_wallet_fraction is not None and s.top_wallet_fraction > HARD["max_top_wallet"]:return False,"top_wallet"
    if s.top10_fraction is not None and s.top10_fraction > HARD["max_top_10"]:return False,"top_10"
    if s.holders is not None and s.holders < HARD["min_holders"]:return False,"holders"
    if s.sells_h1 == 0 and (s.buys_h1 or 0)>20:return False,"no_sells"
    return True,"passed"


def fast_fact_filter(s: TokenSnapshot,min_age_minutes:float)->tuple[bool,str]:
    """Same objective fact gate as the 15m control, with only the cohort age floor varied."""
    required={"age_minutes":s.age_minutes,"liquidity_usd":s.liquidity_usd,"volume_h24_usd":s.volume_h24_usd,"mcap_usd":s.mcap_usd}
    missing=[k for k,v in required.items() if v is None]
    if missing:return False,"missing:"+",".join(missing)
    if s.age_minutes < min_age_minutes:return False,"age_too_young"
    if s.age_minutes > HARD["max_age_hours"]*60:return False,"age_too_old"
    if s.liquidity_usd < HARD["min_liquidity_usd"]:return False,"liquidity"
    if s.volume_h24_usd < HARD["min_volume_h24"]:return False,"volume"
    if s.mcap_usd < HARD["min_mcap_usd"]:return False,"mcap_low"
    if s.mcap_usd > HARD["max_mcap_usd"]:return False,"mcap_high"
    if s.trades_h24 is not None and s.trades_h24 < HARD["min_trades_h24"]:return False,"trades"
    if s.top_wallet_fraction is not None and s.top_wallet_fraction > HARD["max_top_wallet"]:return False,"top_wallet"
    if s.top10_fraction is not None and s.top10_fraction > HARD["max_top_10"]:return False,"top_10"
    if s.holders is not None and s.holders < HARD["min_holders"]:return False,"holders"
    if s.sells_h1 == 0 and (s.buys_h1 or 0)>20:return False,"no_sells"
    return True,"passed"
