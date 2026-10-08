# Savip CHAIN Root-Cause Work Order — 2026-10-08

Status: investigation; no CHAIN fix merged. Authoritative production audit: PR #183 merge 66282163, Render dep-db3u5inlot8c73c22760 LIVE. Shadow only; real execution disabled.

## Evidence (72h live audit)
- Discovery cohort 6,870 (below 10,000 audit sample cap).
- Solana: 3,498 discovered; 31 FREE-qualified, all 31 have DEX; 25 TRADE-qualified; zero completed CHAIN decisions; 5 tokens with CHAIN attempt errors.
- BSC: 55 FREE, 30 TRADE, 23 unique CHAIN decisions. Base: 3 FREE, 1 TRADE, zero CHAIN. ETH: 3 FREE, 2 TRADE, 4 CHAIN (historical flags; not strict same-stage progression).
- Chain rejection audit: Solana 42 solana_wallet_check_pending_429 attempts on 5 tokens; 4 provider_rate_limited_429 attempts on 2 tokens.
- CHAIN worker savip_candidate_pool(window_minutes=4320) defaults to limit=1000, while audit uses limit=10000; worker cap=6 per 60s; sorts non-Solana first; skips Solana during RPC cooldown. These may starve candidates, but magnitude not yet measured.
- Current Solana provider calls getTokenSupply + getTokenLargestAccounts using public RPC. Largest token account is not verified owner concentration. An unmerged experimental branch fix/solana-wallet-owner-verification is NOT approved and must not be merged blindly.
- Dossier provider (GeckoTerminal) and Solana RPC have independent rate limits.

## Strict next-step sequence (complete each with evidence before advancing)
1. **Measure CHAIN visibility and eligibility, read-only.** Reconcile the 25 Solana TRADE-qualified audit cohort against worker's most-recent-1000 selection, persisted 24h CHAIN dedup, cooldown, open-position pause, and cap/non-Solana ordering. Count by chain: audit TRADE-qualified, worker-visible TRADE-qualified, excluded by reason, eligible, selected per cycle, attempted, persisted success/error. Reuse existing diagnostics/audit rather than adding redundant endpoint. First inspect existing fields and SQL query cost. No provider requests required.
2. **Repair only confirmed scheduling gap.** If worker's 1000 cap or non-Solana priority demonstrably prevents eligible Solana progression, adjust bounded fair scheduling or cohort selection with tests. Preserve cap/rate limits and no-trade while open position. Compare before/after selection on fixed fixture, including starvation cases. Do not change safety thresholds.
3. **Separate provider failures.** Quantify dossier GT 429 vs Solana RPC 429; inspect cooldown and retry timing; ensure retries are bounded and no calls during cooldown. Do not buy an API or increase paid usage without approval.
4. **Owner-aware Solana wallet verification.** Validate a provider approach that resolves token accounts to actual wallet owners, handles token programs, supply, escrow/LP exclusions only when verifiable, and preserves fail-closed semantics for missing/incomplete/429 responses. Verify semantics and sample outcomes offline before deployment. Do not merge prior experimental branch as-is.
5. **Controlled shadow-only end-to-end test.** Run unit/integration checks, review diff against frozen execution gates, merge/deploy, then verify live: eligible -> attempted -> persisted CHAIN -> Jev -> PICK -> SIZE/FILLS/BOOK. No fabricated fills; record blockers and evidence. Avoid unnecessary Jev paid calls.
6. **Update this work order and project truth/handoff** with verified results, exact commit/deploy, unresolved blockers and next step after each change. Never call a task done solely because CI passed; distinguish code merged, Render live, live behavior validated.

## Non-negotiable controls
- No live trading; no relaxing FREE/TRADE/CHAIN/Jev thresholds or concentration checks.
- No new paid API subscription or hosting upgrade without user permission.
- Do not equate historical event coverage with chronological funnel conversion.
- Do not repeatedly patch without measuring; prefer minimal, independently testable changes.
- Preserve existing UI work for later, after core shadow pipeline functions.

## Step 1 code-path verification (2026-10-08)
- Confirmed from main: CHAIN calls savip_candidate_pool(window_minutes=72*60) **without limit override**, so limit=1000; the audit uses 10000. This is a real mismatch, but the count of missed TRADE survivors is **not yet measured**.
- Confirmed CHAIN sequence: open_savip_positions early return; pool FREE; exact_trade_cut; dossier cooldown early return; in-memory recent-token exclusions; persisted SAVIP_CHAIN 24h exclusions; Solana RPC cooldown exclusion; non-Solana-first sort; cap=6; dossier fetch; Solana wallet RPC; evaluate_chain; persist.
- Confirmed persistence semantics: successful *and rejected* evaluated CHAIN records are SAVIP_CHAIN; errors are SAVIP_CHAIN_ATTEMPT; a 429 attempt is not a completed CHAIN decision. Persisted dedup checks SAVIP_CHAIN only.
- Confirmed public RPC's getTokenLargestAccounts yields token accounts, not verified owners. Do not treat an RPC 200 as owner-verification success until semantics are fixed.
- Next evidence requirement: quantify how many current TRADE survivors lie outside latest 1000 unique discoveries; then measure remaining exclusions and selected/attempted counts. Do not assert the 1000 cap is the dominant cause without this measurement.

## Step 1 LIVE measurement — confirmed 2026-10-08
- PR #184 merge 1d24382c16b7bf22587db8811c6f51130e5fef6f; Render dep-db3uikh42hec73f49etg LIVE. Endpoint /savip-chain-visibility-audit?hours=72 returned HTTP 200.
- 6870 discoveries scanned by full cohort; worker sees latest 1000.
- Solana 25 TRADE qualified: **15 outside worker 1000**, 10 visible with no persisted CHAIN in 24h.
- BSC 28 TRADE qualified: **28 outside worker 1000**.
- Base 1 TRADE qualified: **1 outside worker 1000**.
- ETH 2 TRADE qualified: 2 visible, both already persisted CHAIN in last 24h.
- This CONFIRMS discovery-window truncation excludes valid TRADE candidates. Snapshot is not a measure of actual attempts, open-position gating, or cooldown effects.
- **NEXT: Step 2** repair worker candidate selection to include qualified 72h cohort without unbounded provider calls; preserve cap 6 per cycle, cooldowns, 24h dedup, position lock, no gate changes. Test fairness and dedup, then CI/merge/deploy/re-audit. Investigate remaining Solana 10 visible separately after this repair.

## Step 2 deployment and first live check — 2026-10-08
- PR #185 merge 9e13ef2d09c4a77c85ba57724c50b8ae594d71ea; Render dep-db3vjd67bikc73aih2eg **LIVE** (finished 20:15:44Z). Worker pool now limit=10000; six-per-cycle provider cap, dedup, cooldown, position lock, safety gates unchanged.
- Postdeploy /savip-chain-rejection-audit?hours=72: BSC top_10 rejects 88 decisions / 29 unique tokens (previous 82 / 23); Solana solana_wallet_check_pending_429 86 attempts / 5 tokens (previous 42 / 5); dossier provider_rate_limited_429 6 attempts / 2 tokens (previous 4 / 2). Rolling historical window, not a clean postdeploy attribution.
- No Solana CHAIN decisions observed; repeated 429 attempts remain the blocking symptom. ETH chain passes in diagnostics have unclaimed historical events; separate downstream concern.
- /savip-chain-visibility-audit still **intentionally compares 1000 vs 10000**, so outside_worker_1000 is a legacy counterfactual, NOT the newly deployed worker configuration. Do not misreport it as current exclusions.
- **Next:** measure postdeploy worker cycles/selected and fresh errors; inspect Solana RPC cooldown and dossier cooldown behavior and why 5 tokens repeat. Before any further provider changes, confirm rate-limit-safe approach; no paid APIs, no safety relaxation. Check DB scan latency under new 10000 worker query.

## Step 3 targeted live diagnosis — 2026-10-08
- Current /savip-pipeline-diagnostics reports CHAIN checked_last_cycle=1, passed=0, last_error=RuntimeError: solana_wallet_check_pending_429; token solana:DZaQRdmPHNaqNsMVqRU8P4q5f2mErab4GipPghowFvaz retry_pending. No shadow positions; Jev checked=0. Confirms worker reaches Solana but provider rate limiting prevents completed CHAIN.
- Code: Solana provider uses public https://api.mainnet-beta.solana.com with getTokenSupply then getTokenLargestAccounts, serial lock, >=2s spacing, 429 Retry-After 60-900s cooldown; worker converts RPC failures to fail-closed pending_429 and records attempt, 300s per-token retry. Provider cooldown excludes Solana before selecting eligible tokens, but dossier can be fetched first when RPC becomes available and subsequently rate-limits.
- Crucial semantic issue: getTokenLargestAccounts returns token accounts, not resolved wallet owners. A successful RPC response does NOT validate largest-wallet ownership concentration; do not mark the owner check complete on this basis.
- **NEXT**: verify no-cost, owner-aware approach offline (mint/token program, parsed token accounts, owner grouping, supply, LP/escrow exclusion only with evidence) and fail-closed 429 semantics. Avoid repeated public RPC traffic and avoid paid API subscriptions. Separately check CHAIN 10000 cohort query latency and per-cycle selected/attempted counters before further scheduling changes. No code fix merged at this stage.

## Step 4 offline design finding — 2026-10-08
- Frozen HARD max_top_wallet=0.05 fraction. evaluate_chain compares top_wallet_percent as a **fraction**, despite misleading key name. Do not multiply by 100 on provider/worker boundary.
- getTokenLargestAccounts alone is insufficient: each entry is a **token account**, not an owner. Need account-owner resolution (e.g. getMultipleAccounts with jsonParsed) and aggregation by owner. However, top-20 token accounts cannot prove global top owner when one owner controls many smaller token accounts outside the top-20. Thus this is a *lower-bound / possible reject signal*, not a safe proof of <=5% ownership.
- Full proof requires complete owner-aware distribution across all token accounts for mint (or a trustworthy indexed provider with explicit coverage/completeness). Public RPC getProgramAccounts can be large/rate-limited or unavailable; Token-2022 layout and account parsing require separate validation. Do not issue large public RPC scans without capacity checks.
- LP/escrow exclusion must require verifiable account classification; unknown owners must not be silently excluded. Supply and owner-account balances must use same mint and raw integer units; verify parsed program IDs and snapshot consistency.
- **Decision:** no production wallet-verification patch yet. A getMultipleAccounts-only patch would still allow false passes. Next: inspect feasible zero-cost indexed complete-holder data and test offline fixtures for split owner accounts, omitted accounts, 429, incomplete results, Token-2022 and LP/escrow ambiguity. Maintain fail-closed behavior for incomplete evidence and no paid subscription.

## Offline ownership fixtures — 2026-10-08
- PR #186 merged as 353964e3cde9b4ce147f9e4ab3f2aecf7f5d7d69; GitHub workflow success on head fb7bce11. Added offline owner aggregation and seven fixture test cases, not connected to production. Workflow success alone does not prove the new tests were discovered.
- Owner verifier groups raw balances by owner and enforces 5% limit. It permits pass only when caller attests complete enumeration and observed sum matches supply. The collector must independently prove completeness; sum equality alone cannot prove that no accounts were omitted.
- Solana standard getProgramAccounts has mint filtering but no native cursor pagination; large scans may be resource intensive. Token-2022 account extensions make fixed 165-byte account size filters unsafe for full coverage. Alchemy documents a paginated variant, but free allowance is unverified; do not buy API access.
- NEXT: verify seven tests are actually collected, expand cases for duplicates, wrong mint, incomplete slot consistency and Token-2022, and design completeness attestation before production RPC changes.

## CI fixture correction — 2026-10-08
- PR #187 merged as 936c2b3d494bbaa6f30f214f12d93ad3b34213d1. Workflow run 37843532613 SUCCESS. Workflow now explicitly runs unittest discover -s tests -p test_solana_owner_coverage.py -v; converted seven pytest-style functions to unittest.TestCase and added two adversarial cases (nine total). The previous PR #186 workflow had NOT run those tests.
- Remaining verifier gap: caller-provided complete=True cannot itself establish complete enumeration; must require independently validated collector attestation, mint/program/slot checks, duplicate-account rejection, and supply consistency before any production integration.
- NEXT: strengthen offline verifier and tests for these invariants; assess cost and feasibility of owner-complete Solana data without paid API. No production RPC changes.

## Offline evidence invariants verified — 2026-10-08
- PR #188 initial run 37844046096 FAILED: literal escaped newlines caused SyntaxError. Corrected on head 87ece6314aebcfb112aa193f8ccc920fb85fda67.
- GitHub workflow run 37844228791 SUCCESS, verified job log explicitly executed **14 Solana owner tests, all OK**. PR #188 merged dc5ae97cac33fcc0467e6f7f87efc4577247bd03.
- Offline verifier optionally requires expected mint, token program and slot; duplicate token account IDs fail closed when evidence expectations supplied. It still accepts caller-provided complete=True, which is not a proof of completeness. Tests are synthetic and not a validation of live RPC or Token-2022 parsing.
- NEXT: design independently verifiable complete-holder collector with consistent mint/program/snapshot and bounded no-cost provider usage; evaluate whether it is operationally feasible before any production integration. No live RPC/worker changes.

## Solana complete-holder collector feasibility contract — 2026-10-08
- Drafted docs/SOLANA_OWNER_COMPLETE_COLLECTOR_FEASIBILITY_2026-10-08.md (research only). Separates token-program ownership from token-account authority, warns standard getProgramAccounts lacks pagination and minContextSlot is NOT a snapshot pin, and identifies Token-2022 extensions/withheld fees and LP ambiguity.
- No new provider selected or paid. Public RPC has observed 429s; no large scans authorized. Existing 14 verifier tests do not validate collector completeness.
- NEXT: verify provider free-tier and consistent snapshot feasibility; build MOCK collector adapter with 429/partial/duplicate/slot/Token-2022 cases before any production wiring. Keep Solana fail-closed, continue separate downstream pipeline diagnosis.

## Mock Solana collector verified — 2026-10-08
- PR #189 documentation merged as 6f3a7927ed923bae0773f92b5e03c7c00a3b3451 after workflow SUCCESS.
- PR #190 mock collector merged as 4f0914aa7c98c850c9c00cdac8ad7cdc4f4f4be6. GitHub Actions run 37845081887 SUCCESS; job logs explicitly show **10 mock collector tests OK**. Separate 14 owner verification tests also remain in CI. No production integration.
- Mock tests cover complete pages, missing/duplicate pages, duplicate accounts, slot inconsistency, rate limit, truncated response, wrong program, unknown owner, and incomplete attestation. Mock 'complete=True' is still caller-provided, NOT independent proof of real provider completeness.
- NEXT: evaluate whether existing no-cost RPC/provider offers bounded complete mint-account enumeration and consistent snapshots. If infeasible, preserve Solana fail-closed and shift attention to non-Solana CHAIN->Jev->shadow pipeline evidence instead of endlessly adding synthetic tests. Do not buy APIs or relax gates.

## Live pipeline checkpoint — 2026-10-08 ~21:15 UTC
- Verified production /savip-pipeline-diagnostics: BSC CHAIN pass event 59955 at 20:18 UTC claimed and Jev completed 20:18:02 UTC; Jev judgment_ok=true, soft_pass=false, soft_reason=concentration_is_exit_risk. ETH event 57048 also claimed/Jev completed, soft_pass=false, soft_reason=liquidity_fits_ticket. PICK state=no_survivors; shadow_positions empty. Therefore **CHAIN -> Jev is working for some non-Solana candidates**; the current observed stop is Jev soft rejection, not an absolute handoff failure.
- /savip-chain-rejection-audit?hours=72: BSC 1 unique CHAIN pass, 30 unique top10 rejects; ETH 4 unique pass tokens across 60 repeated pass events; Base 1 top10 reject; Solana 125 wallet pending_429 attempts over 7 tokens. Counts are rolling and repeat-heavy; not per-deploy attribution.
- Solana feasibility: official getProgramAccounts documents program-owned account listing with filters and withContext, but no cursor pagination; getTokenSupply returns a separate context slot. Neither proves a coherent complete owner snapshot on current public RPC; do not deploy large scans. Decision: no free complete-holder source verified; retain Solana fail-closed.
- NEXT priority: inspect Jev soft gate rules and recorded judgment inputs/decision reason for BSC concentration_is_exit_risk and ETH liquidity_fits_ticket. Determine if these are correctly enforced vs parsing/mapping errors. Do not relax gates or increase paid calls merely to produce a trade. Independently investigate repeat CHAIN pass claim history without assuming all unclaimed duplicates indicate broken handoff.

## Jev soft gate code audit — 2026-10-08
- Inspected app/research/savip_jev_schema.py, savip_jev_adapter.py, savip_jev_evidence.py, savip_jev_candidate.py and reference_thresholds.py. Typed Pydantic judgment then deterministic soft_gate. BSC concentration_is_exit_risk max 0.55; ETH liquidity_fits_ticket min 0.60. Directions in code correct; no threshold change.
- Production /savip-pipeline-diagnostics confirms BSC Jev event 59956 soft_pass=false reason concentration_is_exit_risk and ETH event 57049 soft_pass=false reason liquidity_fits_ticket. Both judgment_ok=true. No shadow positions, PICK=no_survivors. Dashboard does NOT expose actual numeric judgment values or complete evidence; cannot conclude judgment correctness from reason alone.
- NEXT: read-only examine persisted SAVIP_JEV payload/evidence for these exact event IDs and assess data mapping; if no safe existing read path, implement narrowly scoped diagnostic with redaction and tests, avoiding new paid model calls. Do not weaken SOFT thresholds or force a shadow trade.
