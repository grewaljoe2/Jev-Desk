from app.research.replay_metrics import summarize_replays

def test_replay_metrics_separate_selected_and_missed_winners():
    samples=[
        {"terminal_return_pct":20.0,"mfe_pct":40.0,"mae_pct":-5.0,"decisions":[{"arm":"reference","eligible":True}]},
        {"terminal_return_pct":-10.0,"mfe_pct":30.0,"mae_pct":-20.0,"decisions":[{"arm":"reference","eligible":False}]},
        {"terminal_return_pct":-5.0,"mfe_pct":5.0,"mae_pct":-12.0,"decisions":[{"arm":"reference","eligible":True}]},
    ]
    x=summarize_replays(samples)["reference"]
    assert x["eligible"]==2 and x["rejected"]==1
    assert x["win_rate"]==0.5
    assert x["missed_winners"]==1
    assert round(x["profit_factor_return_space"],2)==4.0
