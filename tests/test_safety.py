from app.core.config import settings
from app.core.models import TokenSnapshot
from app.strategy.arms import evaluate_jev_python

def test_live_disabled():
    assert settings.shadow_only is True
    assert settings.live_execution_enabled is False

def test_jev_arm_fails_closed_without_jev():
    s=TokenSnapshot(token_id="x",address="x",chain="mock",ticker="X",age_minutes=60,liquidity_usd=50000,volume_h24_usd=100000,mcap_usd=250000,trades_h24=400,holders=500,top_wallet_fraction=.02,top10_fraction=.25)
    d=evaluate_jev_python(s)
    assert d.eligible is False
    assert "fail_closed" in d.reason
