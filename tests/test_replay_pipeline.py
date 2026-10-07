from datetime import datetime,timezone,timedelta
from app.research.replay_pipeline import run_replay_research

def test_pipeline_freezes_calibration_winner_before_holdout():
    t=datetime(2026,1,1,tzinfo=timezone.utc);samples=[]
    for i in range(80):
        samples.append({"token_id":f"t{i}","baseline_at":t+timedelta(minutes=i),"path":[{"observed_at":t+timedelta(minutes=i+15),"return_pct":5.0},{"observed_at":t+timedelta(minutes=i+60),"return_pct":10.0}]})
    r=run_replay_research(samples)
    assert r["calibration_count"]+r["holdout_count"]==80
    assert r["frozen_policy"] is not None
    assert r["holdout"] is not None
    assert r["holdout"]["policy"]==r["frozen_policy"]
