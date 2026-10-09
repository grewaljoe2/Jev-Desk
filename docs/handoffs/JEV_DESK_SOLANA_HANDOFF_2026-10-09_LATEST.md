# JEV DESK HANDOFF — 2026-10-09 — SOLANA OWNER VERIFICATION

## Source of truth
Repository: grewaljoe2/Jev-Desk
Render: https://jev-desk.onrender.com
Service ID: srv-db2sp7e7bikc73as8690
Workspace ID: tea-db2snq142hec73fp839g
Strict SHADOW-ONLY, fail-closed CHAIN gates. No live trading, no paid APIs, no synthetic candidate approvals.
User wants proactive execution, minimal repeated questions, actual GitHub code/tests/PR/merge, honest deployed-vs-merged reporting.

## Latest commits
PR #247 merged 40ad5df: Solana 77-byte account slices, owner/amount/state, supply check.
PR #248 merged 6177234: classify RPC capability errors.
PR #249 merged 8f9381a: isolated read-only Helius DAS getTokenAccounts paginated mint owner research, tests; not production integrated.
PR #250 merged af72e65: require Helius DAS result total and last_indexed_slot, stable across pages; reject missing/mismatch, tests; CI passed (run 37967792880).
Previous PRs #230-#246 include Solana primary/secondary independent owner snapshots, RPC cooldowns, eligibility counters, GeckoTerminal cache and fail-closed CHAIN.

## Helius credential
HELIUS_API_KEY was set directly in Render environment using Render connector (merge preserving other variables), triggering deployment of PR #249. NEVER put its value in files, logs, messages, or source code. Key was disclosed in prior chat: recommend rotate and update Render secret. Do not reproduce it in handoff. Helius MCP for Codex is optional and not connected to app. No API purchases.
PR #250 has been MERGED, but deployment of #250 is NOT YET VERIFIED. Check Render before claiming live.

## Verified production evidence before #250
PR #249 commit 8f9381a verified live on Render.
After #247, 2 CHAIN checked, 0 passed: mint 6Mix12LiHrQFojaQEnfPUC65Qkwd6X4Y5Qg93oFbordr -> primary:response_too_large; mint HMYd9tosnUXuNHmq7pXmoePRVBLBBjA3JBfydq6upump -> primary:snapshot_slot_mismatch.
After #248, 0 checked, 0 passed because 21 persisted recent skips and 2 in-memory cooldown; DexScreener 429.
Earlier 100 free survivors, 23 trade survivors. Do not claim end-to-end CHAIN -> Jev -> PICK -> SIZE -> FILLS -> BOOK has worked. No proven genuine CHAIN pass yet.

## Architecture and critical findings
app/research/solana_owner_evidence_pipeline.py: getAccountInfo mint, getProgramAccounts with mint memcmp + dataSlice offset32 length77, getTokenSupply; requires accounts and supply exact slot; max_bytes 2 MB and max_accounts 5000; two independent RPC providers must each reconcile positive account balances to supply, identical owner digest/supply across providers. Cross-provider slot equality not required.
app/research/solana_owner_reconciliation.py: per-wallet aggregation and digest; supply conservation at same slot; never authorize by itself.
app/research/solana_indexed_owner_research.py: Helius DAS getTokenAccounts by mint, page and limit, max_pages 10, page_size1000; owner aggregation, strict mint/account/amount validation; total and last_indexed_slot stable per page; response bounded; ALWAYS owner_coverage_complete=False and chain_pass_allowed=False. Indexed slot is not an atomic proof of account snapshot consistency, so do not promote automatically.
tests/test_solana_indexed_owner_research.py covers aggregation, duplicate, wrong mint, cap, missing index metadata.
app/providers/savip_chain.py and app/research/savip_chain_worker.py remain production fail-closed. Production worker NOT integrated with Helius collector.
Dossier/GT and DexScreener 429 are separate problems. Do not weaken 5% top wallet, 60% top10, 80 minimum holders, mint/freeze/honeypot gates.

## Next work order — do not repeat old attempts
1. Check Render deployed SHA after PR #250, production CHAIN status and logs. Distinguish merge from live.
2. Validate actual Helius DAS response schema for total and last_indexed_slot (not yet proven with live requests). In particular verify actual field names and whether values are populated for getTokenAccounts. If different, correct code and tests first. Never log key.
3. Add bounded, explicit read-only Helius research probe for the two known failing mints using existing Render HELIUS_API_KEY; expose sanitized result metadata only (status, pages, total, indexed slot, account count, owner digest, supply check). Avoid adding public unauthenticated endpoint that can burn Helius credits; prefer a bounded internal/one-shot invocation.
4. Check completeness vs on-chain supply and independently verified data; Helius indexed pages are not atomic by default. Define evidence acceptance model before any production integration. If no robust model, retain fail-closed and report exact limitation.
5. Only then integrate into CHAIN as optional validated provider, with strict tests and no silent fallback passes; preserve existing safeguards.
6. Independently address DexScreener 429 without paid API or repeated hammering. Track real funnel stages through Jev, PICK, SIZE, FILLS, RISK, BOOK; do not mistake unrelated shadow systems.
7. Update this handoff after each verified milestone.

## Useful tool access
functions.exec supports tools.mcp__GitHub__fetch_file/create_branch/update_file/create_file/create_pull_request/fetch_commit_workflow_runs/fetch_workflow_run_jobs/merge_pull_request.
Render list_deploys, get_deploy, list_logs, update_environment_variables.
Firecrawl firecrawl_scrape https://jev-desk.onrender.com/savip-shadow-data (markdown fenced JSON), firecrawl_search for Helius API docs.
CI on PR #250 completed success, then merged af72e65.
Avoid reporting work as complete without live data.

## Verified continuation — PR #252
PR #252 merged as d0c12a8d30717126e136412df284603711c24e4f; GitHub Actions run 37968574408 passed. Render deployment dep-db4ihbqj9qps73cm6da0 is LIVE at this exact commit, verified via Render list_deploys. Internal one-shot script app/research/helius_schema_probe.py targets the two known failing mints using HELIUS_API_KEY, bounded to 3 pages x 100 accounts per mint, 8s timeout, 500KB/page; emits sanitized metadata only. Not a public endpoint, not executed yet, not integrated into CHAIN. Official Helius documentation https://www.helius.dev/docs/api-reference/das/gettokenaccounts confirms getTokenAccounts params mint/page/limit and response fields token_accounts/total/last_indexed_slot, but no actual provider response from our mints has been validated. Do not confuse documented schema with live response verification. Next: authorized one-shot execution inside Render credential environment; validate supply and independent evidence; retain fail-closed until robust completeness is demonstrated. Do not add public probe endpoint or paid services. Rotate previously disclosed credential.
