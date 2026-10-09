"""Non-production Savip liquidity relaxation research arm.

The published HARD thresholds are immutable. This module evaluates the same
FREE facts under the original $25k liquidity gate and a $15k shadow candidate
gate. It does not grant CHAIN approval, write positions, or place orders.
"""
from dataclasses import dataclass
from app.strategy.reference_thresholds import HARD

EXPERIMENT_ID = "liquidity_15k_shadow_v1"
EXPERIMENT_MIN_LIQUIDITY_USD = 15000

@dataclass(frozen=True)
class LiquidityComparison:
    control_eligible: bool
    experiment_eligible: bool
    newly_admitted: bool
    reason: str

def compare_liquidity_gate(facts):
    """Compare only liquidity while retaining every other published FREE gate.

    Missing or nonnumeric facts fail closed. Token age is expressed in minutes.
    """
    fields = ("age_minutes", "liquidity_usd", "volume_h24_usd", "mcap_usd")
    try:
        values = {key: float(facts[key]) for key in fields}
    except (KeyError, ValueError, TypeError, OverflowError):
        return LiquidityComparison(False, False, False, "missing_or_invalid_fact")
    from math import isfinite
    if not all(isfinite(value) for value in values.values()):
        return LiquidityComparison(False, False, False, "nonfinite_fact")
    age, liq, vol, cap = (values[key] for key in fields)
    if not (HARD["min_age_minutes"] <= age <= HARD["max_age_hours"] * 60):
        return LiquidityComparison(False, False, False, "age")
    if not (HARD["min_mcap_usd"] <= cap <= HARD["max_mcap_usd"]):
        return LiquidityComparison(False, False, False, "market_cap")
    if vol < HARD["min_volume_h24"]:
        return LiquidityComparison(False, False, False, "volume")
    control = liq >= HARD["min_liquidity_usd"]
    experiment = liq >= EXPERIMENT_MIN_LIQUIDITY_USD
    return LiquidityComparison(control, experiment, experiment and not control,
                               "newly_admitted" if experiment and not control else
                               "control_pass" if control else "liquidity")
