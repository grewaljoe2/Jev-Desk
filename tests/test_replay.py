from datetime import datetime,timezone,timedelta
from app.core.models import TokenSnapshot
from app.research.replay import ReplayPoint,replay_candidate

def test_replay_does_not_feed_future_to_strategy():
    t=datetime(2026,1,1,tzinfo=timezone.utc)
    s=TokenSnapshot(token_id="x",address="x",chain="solana",ticker="X",observed_at=t,price_usd=1.0)
    r=replay_candidate(s,[ReplayPoint(t+timedelta(minutes=5),2.0),ReplayPoint(t+timedelta(minutes=15),0.5)])
    assert r["mfe_pct"]==100.0
    assert r["mae_pct"]==-50.0
    assert r["terminal_return_pct"]==-50.0
    assert len(r["decisions"])==3
