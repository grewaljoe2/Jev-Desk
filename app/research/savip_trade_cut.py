"""Exact published Savip TRADE CUT normalization. Shadow only."""

def normalize_trade_cut(funnel):
    """Promote explicit DEX no-pair evidence to the published no_pair rejection."""
    rows=list(funnel.get("free_cut_survivors",[]))
    existing=list(funnel.get("trade_cut_survivors",[]))
    kills=dict(funnel.get("trade_cut_kills",{}))
    missing=dict(funnel.get("trade_cut_missing_fields",{}))
    no_pair=[r for r in rows if r.get("pair_found") is False]
    if not no_pair:
        return funnel
    ids={r.get("token_id") for r in no_pair}
    funnel=dict(funnel)
    funnel["trade_cut_survivors"]=[r for r in existing if r.get("token_id") not in ids]
    kills["no_pair"]=kills.get("no_pair",0)+len(no_pair)
    funnel["trade_cut_kills"]=kills
    return funnel
