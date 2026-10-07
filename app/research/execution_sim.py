"""Conservative shadow execution simulator for replay research only."""
from dataclasses import dataclass

@dataclass(frozen=True)
class ExecutionAssumptions:
    entry_slippage_bps:float=100.0
    exit_slippage_bps:float=100.0
    round_trip_fee_bps:float=100.0

def simulate_terminal_trade(sample:dict,assumptions:ExecutionAssumptions=ExecutionAssumptions()):
    """Apply explicit execution drag to a selected sample's terminal return.

    This is intentionally simple until chain/pool-specific fill models are
    calibrated from shadow observations.
    """
    raw=sample.get("terminal_return_pct")
    if raw is None:return None
    entry_mult=1.0+assumptions.entry_slippage_bps/10000.0
    exit_mult=1.0-assumptions.exit_slippage_bps/10000.0
    fee_mult=1.0-assumptions.round_trip_fee_bps/10000.0
    gross_mult=1.0+raw/100.0
    net_mult=(gross_mult*exit_mult*fee_mult)/entry_mult
    return {
        "raw_return_pct":raw,
        "net_return_pct":(net_mult-1.0)*100.0,
        "entry_slippage_bps":assumptions.entry_slippage_bps,
        "exit_slippage_bps":assumptions.exit_slippage_bps,
        "round_trip_fee_bps":assumptions.round_trip_fee_bps,
        "model":"research_placeholder_v1",
    }
