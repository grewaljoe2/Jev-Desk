"""Published Savip post-entry risk rule. Pure decision logic; shadow only."""
from app.strategy.reference_thresholds import RISK

def volume_ratio(volume_6h:float|None,volume_24h:float|None):
    if volume_6h is None or volume_24h is None or volume_24h<=0:return None
    avg_6h=volume_24h/4.0
    return volume_6h/avg_6h if avg_6h>0 else None

def risk_decision(volume_6h:float|None,volume_24h:float|None,data_failures:int=1):
    """data_failures is the number of failed reads already observed, starting at 1."""
    ratio=volume_ratio(volume_6h,volume_24h)
    if ratio is None:
        if data_failures<=RISK["data_retries"]:return {"action":"retry","reason":"volume_data_missing","ratio":None,"failed_reads":data_failures,"retries_remaining":RISK["data_retries"]-data_failures}
        return {"action":"close_100","reason":"volume_data_failed","ratio":None,"failed_reads":data_failures,"deadline_seconds":60}
    if ratio<RISK["volume_ratio_close"]:
        return {"action":"close_100","reason":"volume_collapse","ratio":ratio,"deadline_seconds":60}
    return {"action":"hold","reason":"volume_ok","ratio":ratio}
