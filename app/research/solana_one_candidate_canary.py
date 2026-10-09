"""One-candidate CHAIN canary: observable downstream eligibility, no forged approval.

Run with a real dossier and verified wallet evidence, or explicitly record why
the candidate cannot pass. Never persist or execute a synthetic CHAIN pass.
"""
from app.research.savip_chain_cut import evaluate_chain, known_chain_kill
from app.strategy.reference_thresholds import HARD

def evaluate_one_candidate(dossier, wallet_evidence):
    if not isinstance(dossier,dict) or dossier.get("chain")!="solana":
        return {"status":"invalid_candidate","chain_pass":False}
    early=known_chain_kill(dossier)
    if early:
        return {"status":"chain_kill","chain_pass":False,"reason":early}
    if not isinstance(wallet_evidence,dict):
        wallet_evidence={}
    verified=(wallet_evidence.get("owner_coverage_complete") is True
              and wallet_evidence.get("chain_pass_allowed") is True
              and wallet_evidence.get("positive_balance_coverage_proven") is True)
    if not verified:
        return {"status":"wallet_evidence_pending","chain_pass":False,
                "reason":wallet_evidence.get("status","unverified_owner_coverage")}
    fraction=wallet_evidence.get("largest_owner_fraction")
    holders=wallet_evidence.get("holder_count")
    top10=wallet_evidence.get("top_10_percent")
    if type(fraction) not in (float,int) or not 0<=fraction<=1 or type(holders) is not int or type(top10) not in (float,int) or not 0<=top10<=100:
        return {"status":"invalid_wallet_metrics","chain_pass":False}
    facts={**dossier,"solana_wallet_rpc_status":"ok",
           "top_wallet_percent":fraction,"holder_count":holders,
           "top_10_percent":top10}
    passed,reason=evaluate_chain(facts)
    return {"status":"chain_pass" if passed else "chain_kill",
            "chain_pass":passed,"reason":reason,
            "holder_count":holders,"top_wallet_fraction":fraction,
            "top_10_percent":top10,
            "max_top_wallet":HARD["max_top_wallet"]}
