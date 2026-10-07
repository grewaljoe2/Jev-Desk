"""Deterministic calibration/holdout split for replay research."""
import hashlib

def cohort_partition(sample:dict,calibration_fraction:float=0.70):
    if not 0<calibration_fraction<1:raise ValueError("calibration_fraction must be between 0 and 1")
    key=f'{sample.get("token_id","")}|{sample.get("baseline_at","")}'
    bucket=int(hashlib.sha256(key.encode()).hexdigest()[:8],16)/0xFFFFFFFF
    return "calibration" if bucket<calibration_fraction else "holdout"

def split_samples(samples:list[dict],calibration_fraction:float=0.70):
    calibration=[];holdout=[]
    for s in samples:
        (calibration if cohort_partition(s,calibration_fraction)=="calibration" else holdout).append(s)
    return calibration,holdout
