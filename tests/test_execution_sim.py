from app.research.execution_sim import ExecutionAssumptions,simulate_terminal_trade

def test_execution_drag_reduces_return():
    s={"terminal_return_pct":20.0}
    x=simulate_terminal_trade(s,ExecutionAssumptions(100,100,100))
    assert x["net_return_pct"]<20.0
    assert x["net_return_pct"]>15.0

def test_execution_drag_can_turn_small_gain_negative():
    s={"terminal_return_pct":1.0}
    x=simulate_terminal_trade(s,ExecutionAssumptions(100,100,100))
    assert x["net_return_pct"]<0.0
