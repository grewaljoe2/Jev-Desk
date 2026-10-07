"""Published Savip Jev question contract. Typed answers only."""
QUESTION_SETS={
 "market":{
   "concentration_is_exit_risk":"Probability holder concentration creates meaningful exit risk.",
   "momentum_already_spent":"Probability the current move is already substantially spent.",
   "liquidity_fits_ticket":"Probability liquidity safely fits the proposed ticket.",
   "shape":"Classify market shape: healthy, fading, one_buyer, or unclear.",
   "sell_side_risk":"Classify sell-side evidence: clean, flagged, suspicious, or unclear.",
 },
 "chain":{
   "dev_still_loaded":"Probability the developer remains materially loaded.",
   "sellable_by_evidence":"Probability available evidence supports that the token is sellable.",
   "crowd_probability":"Probability ownership/activity reflects a real crowd rather than concentrated control.",
 },
 "social":{
   "account_is_the_project":"Probability the supplied exact X account is genuinely the project account.",
   "recycled_account":"Probability the supplied X account is recycled/reused from another project.",
   "audience_is_real":"Probability the observed audience is authentic.",
   "effort":"Numeric project/social effort score.",
 },
}
RULES=(
 "Return only the typed fields requested; do not return prose.",
 "Judge ambiguity from supplied evidence only; do not invent missing facts.",
 "SOCIAL may inspect only the exact supplied x_handle; never substitute or search a similar handle.",
 "Do not apply trading thresholds; deterministic code applies gates after judgment.",
)
