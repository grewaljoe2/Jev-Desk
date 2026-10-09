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

## Persisted Jev evidence access boundary — 2026-10-08
- Verified `log_savip_jev` persists both full typed `result` and exact `evidence` in SAVIP_JEV payload_json. Existing public `/savip-jev-outcomes` and `/savip-pipeline-diagnostics` intentionally expose only outcome metadata, not raw evidence or numeric judgment fields.
- Attempted read-only Render Postgres query for Jev event IDs 59956 and 57049. Render connector explicitly refused connection because DB external IP allowlist is empty. **Do not alter database network allowlist or expose sensitive evidence via unauthenticated public endpoint.** An attempted endpoint-writing tool action was blocked; no endpoint created.
- Existing code shows correct gate directions but live numeric judgments are still **not audited**. NEXT: use an authorized secure internal DB inspection route (or existing authenticated operations surface) to compare stored market/chain evidence and judgment fields for the two events; redact social/private data. If unavailable, mark numeric audit blocked, do not pretend rejection correctness verified. Continue checking other live shadow pipeline diagnostics safely.

## Jev numeric audit completed — 2026-10-08
- PR #191 merged 0d57bb3, Render dep-db411g942hec73fc2hig LIVE. Private startup logs returned exact persisted numeric scores without exposing a public endpoint.
- ETH SAVIP_JEV event 57049: concentration 0.33, liquidity_fits_ticket 0.55 (< frozen min 0.60), liquidity USD 211933.9098, volume 1027766.13458894, top10 18.0027%, holders 461. Deterministic rejection reason liquidity_fits_ticket correctly follows frozen comparison.
- BSC SAVIP_JEV event 59956: concentration_is_exit_risk 0.65 (> frozen max 0.55), liquidity_fits_ticket 0.54 (< min 0.60), liquidity USD 70993.0926, volume 195750.525144753, top10 49.1726%, holders 500. First failing reason concentration_is_exit_risk correctly follows frozen comparison. Numeric evidence present; cannot independently certify model judgment quality, only correct mapping/comparison.
- PR #192 cleanup merged f17e33d, CI success; cleanup Render deploy dep-db413d7lot8c73cb3lv0 triggered, verify LIVE. No changes to thresholds or real execution.
- NEXT: confirm cleanup deploy LIVE; then audit whether model's ticket-fit judgment is calibrated to actual shadow sizing/liquidity and whether evidence missing or misrepresented, WITHOUT relaxing safety gates. Independently inspect PICK→SIZE→FILLS→BOOK behavior for correctly qualified candidates. No fabricated trade.

## Post-audit architecture review — 2026-10-08
- Cleanup Render deploy dep-db413d7lot8c73cb3lv0 confirmed LIVE, commit f17e33d. Temporary private Jev logging removed.
- Exact SIZE code: bank $1000, max_bank_fraction .06 => maximum $60 ticket, or $36 if missing X (.60 multiplier); liquidity cap 2%. Both audited pools (ETH ~$211934; BSC ~$70993) far exceed ticket sizes, but model `liquidity_fits_ticket` probabilities were .55 and .54. This is **calibration/evidence question**, not proven gate bug: Jev evidence contains liquidity, not explicit proposed ticket/bank/factor; model may be judging unspecified ticket. NEXT: isolate contract to pass explicit conservative maximum proposed ticket to model, with unit tests and no changed thresholds, then evaluate new candidates rather than retroactively changing historical decisions.
- `SavipPickWorker.run_cycle` currently calls provider.pick whenever rows is nonempty, including exactly one survivor; `single_survivor` helper exists but unused. This violates intended multi-candidate PICK policy. NEXT: verify existing tests and exact single-survivor no-PICK requirement, then implement deterministic worth_trading_at_all / confidence policy without inventing acceptance or spending a needless model call. Do not auto-trade a single survivor.
- Keep shadow-only; verify real BOOK fills only from genuinely qualified fresh candidates, not synthetic ones.

## Ticket evidence implementation — 2026-10-08
- PR #193 opened (head 7d08f970) with MarketEvidence.proposed_ticket_usd from existing ticket_usd($1000, pool liquidity, factor 1.0, missing_x flag), Jev question clarified to judge the explicit proposed ticket; thresholds unchanged. Test file added. CI run 37851595867 in progress at last check; NOT merged/deployed yet.
- Caution: verify tests actually discovered by CI and full test pass; no new live judgment or calibration claim until deployment and fresh candidate. Single-survivor PICK issue remains separate and unresolved.

## Ticket/PICK rollout — 2026-10-08
- PR #193 merged a2eeeff, focused ticket-evidence CI run 37851667874 passed with newly added test step; Render dep-db41bmk9v7es738o7e4g LIVE. Ticket evidence now includes a conservative explicit max shadow ticket ($1000 bank) for future Jev judgments; no thresholds altered. Historical Jev scores remain historical.
- PR #194 merged 7e7a747, CI run 37852347831 SUCCESS, adds guard to avoid invoking multi-candidate PICK when exactly one survivor; state single_survivor_awaiting_independent_eligibility; no auto-accept, no model spend. Render deploy trigger was blocked by tool safety checks; as of last verification latest LIVE commit is a2eeeff. Verify whether auto-deploy happens; otherwise #194 remains merged but not live.
- Important: single-survivor now waits, so an independent worth-trading-at-all/confidence decision path is still required; do not fabricate a winner or shadow trade. Continue investigating true qualifying candidate funnel and model calibration.

## Deployment verification and eligibility design — 2026-10-08
- Render dep-db41dkbl550s73c8rkog finished LIVE, deployed main commit 00dfdc001a5fbd94c1aedfff7ba993486012b214 (includes merged #193/#194).
- Current single-survivor guard intentionally returns `single_survivor_awaiting_independent_eligibility`; it avoids model PICK calls but is a **functional blocker** for legitimate single-candidate shadow entries until a separate eligibility path is implemented. Do not misrepresent this as end-to-end completion.
- Preserve PICK thresholds worth_trading_at_all >=0.60, confidence >=0.55, and no winner fabrication. Proposed next work: independent typed single-candidate worth-trading and confidence judgment using the same verified Jev evidence, then deterministic acceptance and persistent audit; avoid reusing multi-candidate comparison or silently bypassing confidence. Require offline isolated tests of negative, invalid, positive, duplicate, stale and missing-data outcomes before deployment. Do not spend provider calls or change thresholds without validation.

## Single-survivor eligibility offline contract — 2026-10-08
- PR #195 merged 0b4b03c, CI 37853383702 SUCCESS; adds `app/research/savip_single_eligibility.py` with strict typed scores and deterministic frozen PICK threshold checks; 9 regression tests included in workflow. This code is NOT wired to the worker/provider/BOOK; no independent model call, persistent decision, or trade occurs from it.
- NEXT: implement independent single-candidate Jev eligibility provider contract and persist audited decisions, validate positive/negative/stale/duplicate/error paths offline before wiring to shadow PICK/BOOK. Do not bypass soft gates or generate synthetic accepted trades.

## Independent single-candidate provider — 2026-10-08
- PR #196 open, head 6028462fb0cc400d082f097d44dd4b5e5046384a, CI 37853699941 SUCCESS. Adds TypeSafeJevProvider.judge_single_eligibility with independent typed worth_trading_at_all, confidence, size_factor questions and mock provider tests; not wired to live worker or trading.
- Merge tool was blocked by safety checks; do not claim merged or deployed. NEXT: review provider contract and safe fail-closed validation, merge after permitted review, then independently implement persistent single-candidate audit and only then gated worker integration with end-to-end shadow-only tests. Avoid extra paid API calls or threshold relaxation.

## Standalone eligibility audit builder — 2026-10-08
- PR #196 merged b5bce288; independent TypeSafe provider method available but unwired.
- PR #197 merged 50674e862d6dda773e0c0bcf50c310ea96e62412, CI 37854397790 SUCCESS. Adds pure `build_single_audit` with verified soft-pass and typed eligibility checks, plus three offline regression tests. Audit builder does not persist events and cannot open BOOK positions; it is NOT end-to-end integration.
- NEXT: add persistent SAVIP_SINGLE_ELIGIBILITY event storage and dedup keyed to Jev event ID, validate stale/error paths, then integrate worker/provider without bypassing PICK confidence gates; verify real shadow-only lifecycle. No real execution.

## Single-survivor worker cost guard — 2026-10-08
- PR #198 merged eafc6d1; idempotent Postgres SAVIP_SINGLE_ELIGIBILITY audit storage, CI successful after mock fix.
- PR #199 merged c15e7fa99372d21f2e8f826556e3e1a004d86b9a; CI 37858232630 SUCCESS. Worker can independently judge verified, fresh single survivors, audit to SAVIP_SINGLE_ELIGIBILITY and deduplicate by Jev event, but **SAVIP_SINGLE_ELIGIBILITY_ENABLED defaults false** and therefore incurs NO additional standalone model calls by default. No SAVIP_PICK event/on_accept is emitted from single path, so no shadow entry.
- NEXT: develop separately validated shadow-only bridge from eligible standalone audit to existing SIZE/FILLS/BOOK, preserving threshold, source freshness, no-position and dedup constraints; do not enable opt-in API calls without explicit user cost approval. No real trading.

## 2026-10-08 final session update
- PR #196 merged b5bce288 (independent Jev provider); PR #197 merged 50674e86 (typed audit builder); PR #198 merged eafc6d1d (idempotent SAVIP_SINGLE_ELIGIBILITY storage); PR #199 merged c15e7fa9 (worker wiring default OFF). PR #199 CI 37858232630 SUCCESS.
- Single eligibility calls require SAVIP_SINGLE_ELIGIBILITY_ENABLED=true; default false avoids new API costs. Single accepted decisions remain audit-only, never a comparative PICK or shadow entry. No genuine shadow fill verified.
- Exact continuation and prompt: docs/SAVIP_HANDOFF_2026-10-08_LATEST.md. Next: harden nonfinite evidence/scores, build and test separate single-eligibility shadow BOOK bridge, verify Render deployment/read-only diagnostics. No real execution.

## 2026-10-08 PR #200–#201 verified checkpoint
- PR #200 merged 1113285dc41e39a4003dbaf42734cd0cf98cd27e. Finite and boolean invalid numeric scores/evidence now fail closed. CI run 37858662824 SUCCESS.
- PR #201 merged 23a3963d1c29ff7affee02318acd37f7cd47a1fa. Independent accepted SAVIP_SINGLE_ELIGIBILITY -> SIZE/FILLS/BOOK shadow route with source identity, age and soft-pass revalidation; atomic Postgres transaction with eligibility provenance, held-position and duplicate-event guard; missing-X 0.60 size factor. CI run 37859454267 SUCCESS.
- SAVIP_SINGLE_SHADOW_ENTRY_ENABLED defaults false, independent of SAVIP_SINGLE_ELIGIBILITY_ENABLED (also false). Neither opt-in was enabled. No new paid eligibility calls and no real trades. Existing multi-candidate PICK route retained. These CI tests use mocks, not a live Postgres transactional integration or genuine end-to-end shadow fill.
- Render autoDeploy is enabled on main. Verify actual new deployment and logs before claiming production live; previous verified live was dep-db41dkbl550s73c8rkog at 00dfdc0. Do not enable paid single-eligibility model calls without explicit cost approval; known duplicate-provider-call race before DB dedup remains unresolved. No genuine shadow fill verified.

## 2026-10-09 owner-aware collector feasibility — researched, NOT deployed
- Official Solana getProgramAccounts supports mint memcmp at offset 0, program ownership, dataSlice and withContext, allowing enumeration of SPL token accounts for a mint (not automatically wallet owners). Reference: https://solana.com/docs/rpc/http/getprogramaccounts
- Candidate architecture: determine Tokenkeg vs Token-2022 mint owner using getAccountInfo; request filtered getProgramAccounts for that program and mint with withContext and base64 data; decode account owner pubkey (bytes 32:64) and raw amount (bytes 64:72 little endian); group balances by owner. Request supply at coherent snapshot; note minContextSlot is a lower bound, NOT a guarantee of identical slot, and a cross-call sum equal to supply alone is NOT sufficient to attest a coherent snapshot.
- Production pass MUST remain blocked until tests demonstrate completeness, mint/program matching, snapshot consistency, duplicate-account rejection, unknown-owner handling, closed-account and supply races, RPC truncation/size limits and 429 cooldown. getProgramAccounts is unpaginated and heavy; the public RPC may disallow or throttle it. Never mark owner_coverage_complete true based merely on nonempty result or matching summed balances.
- Cheap one-sided account lower-bound rejection already live; don't add high-volume RPC enumeration to every candidate until a limited, read-only, opt-in feasibility probe proves provider availability and bounded cost. No paid API or threshold relaxation.

## Solana owner RPC feasibility evidence — 2026-10-09
- PR #213 merged, CI passed: one-shot probe now separates timeout, connection_error, transport_error and invalid_rpc_response. This was diagnostic only; not a verified owner pass.
- PR #214 merged, CI passed: classic SPL getProgramAccounts now adds dataSize=165 alongside mint memcmp. Token-2022 does not get the classic fixed-size filter.
- PR #215 merged, CI passed: corrected official Token-2022 program ID in decoder and manual workflow.
- Initial real GitHub Actions feasibility invocation: status unavailable_or_invalid, owner_coverage_complete=false, ~13 seconds. Original probe did not distinguish failure category; cannot assert timeout as fact.
- Temporary PR #216 GitHub Actions run 37867824288, job 113618703193: bounded 12-second read-only query against synthetic empty mint returned decoded_unverified, slot 454712816, token_accounts=0, owner_coverage_complete=false. CI passed. PR closed WITHOUT MERGE; temporary CI step is not in main.
- Interpretation: public endpoint can handle the exact filtered request and decode an empty account set. This does NOT prove enumeration of a real mint, complete owner coverage, coherent supply, or CHAIN approval. Large-mint failure cause remains unknown.
- Render Postgres read-only query via connector blocked by database's empty external IP allowlist. Do not weaken database networking solely for this test. Obtain a real, low-account-count candidate mint from existing approved diagnostics or code evidence before further RPC probe; avoid inventing mint IDs or rerunning high-cardinality WSOL.
- Next: validate a real mint's token program and bounded enumeration, measure returned accounts, bytes, slot, and failure reason; then separately prove completeness and same-slot supply before any production owner verification. Keep fail-closed and shadow-only.

## 2026-10-09 owner-aware Solana research checkpoint (PR #222–#225)
- PR #222 merged afb701e380dce97abc6c0dcc5ed0a540f6f56b79: offline wallet-owner aggregation, supply reconciliation and provable concentration rejection; never permits CHAIN pass. Nine new tests passed.
- PR #223 merged 8f03cd231231c1bfeac59abf8bf2444bf5ec2f6a: bounded research-only getAccountInfo -> getProgramAccounts -> getTokenSupply collector with actual mint program detection and mock tests. Six new tests passed. Not wired to production CHAIN.
- PR #224 merged eb12477513f5267c7e8b8f68c9dcfa687d73c8be: minContextSlot and monotonic mint/account checks; seven tests passed.
- Real mint 2JxdiEFs3K8tVtWp4Q3SK6RGNwLJaRRNmX63y3Xnpump was independently confirmed as Token-2022 with 993459019665614 raw supply (6 decimals). Classic SPL query falsely showed 0 accounts; corrected Token-2022 query decoded 2 accounts.
- One-off PR #221 GitHub run 37869714606: 2 accounts, 2 distinct wallet owners, account sum = supply 993459019665614, largest owner = entire supply, account and supply slot both 454717923. Evidence strongly supports a concentration reject for that mint; does not prove general account completeness. Temporary PR closed unmerged.
- One-off PR #225 GitHub run 37872018708: end-to-end pipeline returned invalid_evidence, accounts slot 454724415, supply slot 454724414, mint slot 454724414. Correctly FAIL CLOSED. Even with minContextSlot, RPC calls are not guaranteed to share a slot. PR closed unmerged.
- Current status: no verified complete-owner pass and no genuine Solana CHAIN -> PICK -> shadow BOOK fill. No paid APIs, flags, thresholds, or real execution enabled.
- Critical next decision: same-slot multi-call reads cannot be assumed on public RPC. A reliable production completeness attestation requires a proven RPC/provider contract or independently auditable full-state source with bounded cost and rate limits. Do not infer completeness from matching balances, do not repeatedly fire large unpaginated queries, and do not weaken Solana CHAIN gates to create passes.
- Continue measuring live funnel separately for BSC/ETH; fresh Jev soft-pass and PICK thresholds still govern genuine shadow fills. Standalone eligibility and entry are default OFF to avoid extra model calls.
