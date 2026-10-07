"""Published Savip sizing and fill math. Simulation only; no order transport."""
from app.strategy.reference_thresholds import SIZE,FILLS

def ticket_usd(bank_usd:float,pool_liquidity_usd:float,size_factor:float=1.0,dark_data:bool=False,missing_x:bool=False):
    factor=max(0.0,min(float(size_factor),1.0))
    if dark_data:factor*=SIZE["dark_data_factor"]
    if missing_x:factor*=SIZE["missing_x_factor"]
    return max(0.0,min(bank_usd*SIZE["max_bank_fraction"]*factor,pool_liquidity_usd*SIZE["max_liquidity_fraction"]))

def fee_usd(ticket:float):
    return max(FILLS["fee_rate"]*ticket,FILLS["fee_floor_usd"]) if ticket>0 else 0.0

def simulated_market_fill(ticket:float,price:float):
    fee=fee_usd(ticket);net=max(ticket-fee,0.0)
    return {"ticket_usd":ticket,"fee_usd":fee,"net_asset_usd":net,"quantity":net/price if price and price>0 else 0.0,"fill_type":"market_shadow"}
