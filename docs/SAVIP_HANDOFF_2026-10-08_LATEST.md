# Savip / Jev Desk — latest handoff (2026-10-08)

## User intent and invariants
Continue implementing the existing Jev Desk/Savip **shadow-only** memecoin trading pipeline, no reset or repeated plans. Repo: grewaljoe2/Jev-Desk; Render service srv-db2sp7e7bikc73as8690, workspace tea-db2snq142hec73fp839g; managed Postgres dpg-db2sq2qd0e5s73ea0dd0-a. Dashboard https://jev-desk.onrender.com. No real trades, no new paid APIs, no changing frozen thresholds, no opening Postgres allowlists or exposing evidence. User wants genuine candidates passing the whole funnel and a genuine shadow fill; **none yet verified**. Don't claim merged code is live unless Render deploy confirms.

## Authoritative work order
docs/SAVIP_CHAIN_ROOT_CAUSE_WORK_ORDER_2026-10-08.md (previously updated on main at 65ff255333dff60689308f37dab6735e801a026f; should update again).

## Completed and merged in this chat
- PR #196 https://github.com/grewaljoe2/Jev-Desk/pull/196 — merged b5bce288a0ee8e33e68c49b961f7e6d497495f7f; adds TypeSafeJevProvider.judge_single_eligibility(token_id,judgment,evidence), three independent typed noul scores. CI previously SUCCESS.
- PR #197 https://github.com/grewaljoe2/Jev-Desk/pull/197 — merged 50674e862d6dda773e0c0bcf50c310ea96e62412; adds app/research/savip_single_audit.py build_single_audit, verified soft-pass check, typed eligibility and audit payload, tests; CI 37854397790 SUCCESS.
- PR #198 https://github.com/grewaljoe2/Jev-Desk/pull/198 — merged eafc6d1dd6d8f8b423a2975a80cb37bd9afd0d0d; adds app/storage/db.py savip_single_eligibility_seen and log_savip_single_eligibility, separate SAVIP_SINGLE_ELIGIBILITY event, transactional advisory-lock dedup by Jev event ID; tests; CI 37857785933 SUCCESS.
- PR #199 https://github.com/grewaljoe2/Jev-Desk/pull/199 — merged c15e7fa99372d21f2e8f826556e3e1a004d86b9a; wires single survivor in app/research/savip_pick_worker.py run_single to standalone provider, typed audit and DB log. Validates Jev event ID and created_at, max 900 seconds, verified soft-pass, prior event seen, configured provider; catches provider errors. **SAVIP_SINGLE_ELIGIBILITY_ENABLED=false by default**; only true/1/yes enables new API calls. NO comparative PICK call and NO on_accept for single survivors. Tests tests/test_savip_single_worker_audit.py (valid, stale, duplicate, low confidence, disabled), legacy single survivor test adjusted; CI 37858232630 SUCCESS.

## Important current behavior
Multi-candidate PICK unchanged. One survivor now run_single; with default flag off state single_eligibility_disabled and NO model spending. With flag on and valid survivor, standalone judgment stored in SAVIP_SINGLE_ELIGIBILITY. Accepted single eligibility is NOT yet bridged to shadow entry, by design. app/research/savip_shadow_lifecycle.py currently only consumes latest accepted SAVIP_PICK with PickResult.winner, not SAVIP_SINGLE_ELIGIBILITY. Do NOT forge comparative PICK or silently relax thresholds. Do not enable new API spending without user approval, even if flag is opt-in.

## Next work, priority order
1. Review and harden fail-closed validation in app/research/savip_single_eligibility.py: reject NaN/Infinity and booleans for ticket/liquidity and nonfinite scores; validate identity/provenance and social/missing X sizing without relaxing thresholds.
2. Build a distinct shadow-entry authorization path for SAVIP_SINGLE_ELIGIBILITY, explicitly revalidate accepted decision, matching Jev token/event, freshness, chain/market evidence, and frozen confidence/worth gates, reuse existing ticket_usd and simulated_market_fill, check held position and idempotent pick/eligibility event entry. Do not convert it into a fabricated comparative PICK. Ensure existing multi-candidate behavior unchanged. Mock regression tests for positive, rejected, stale, duplicate, missing evidence, invalid token, held position, missing X, fee/size and no real execution.
3. Add diagnostics for single-eligibility audit status and blocked reasons; protect private evidence. Make only necessary PRs, run CI and merge green.
4. Verify Render deploy and read-only diagnostics, plus real shadow-only observation, after code is safely deployed. **No verified shadow fills currently.**
5. Update authoritative work order and latest handoff. User specifically wants a handoff prompt.

## Caution / known possible race
savip_single_eligibility_seen is a pre-check before a provider call; DB logging deduplicates events under advisory lock, but concurrent workers could still issue duplicate paid API requests before the insert. For default-off no calls. Add per-process or DB claim/reservation if enabling paid calls. Avoid enabling until controlled.

## Other history
#193 proposed ticket evidence; #194 single survivor comparative PICK guard; #195 standalone typed decision model; #180 shadow lifecycle. Frozen PICK thresholds worth_trading_at_all=0.60, winner_confidence=0.55. SIZE max bank 0.06, max pool 0.02, missing_x_factor=0.60. No X paid API. Recent prod deploy was dep-db41dkbl550s73c8rkog, commit 00dfdc001a5fbd94c1aedfff7ba993486012b214, **not known current**. Verify current before claims.

## Paste into new chat
Continue Savip/Jev Desk from docs/SAVIP_HANDOFF_2026-10-08_LATEST.md in GitHub grewaljoe2/Jev-Desk and docs/SAVIP_CHAIN_ROOT_CAUSE_WORK_ORDER_2026-10-08.md. PRs #196–#199 are merged; #199 CI 37858232630 SUCCESS. No reset. New single-survivor Jev audit path is default OFF (SAVIP_SINGLE_ELIGIBILITY_ENABLED=false), so no extra API spending; no accepted single-survivor shadow entry yet. Finish fail-closed validation and build distinct safe single-eligibility→shadow BOOK bridge, add tests, merge green, verify deploy and genuine end-to-end shadow fill if available. Keep multi-PICK unchanged, frozen gates, shadow-only, no new paid API or real execution. Update work order and handoff with exact truth.

## 2026-10-08 continuation after PR #201
- #200 merged 1113285, CI 37858662824 SUCCESS: fail-closed finite/boolean numeric evidence and score validation.
- #201 merged 23a3963d1c29ff7affee02318acd37f7cd47a1fa, CI 37859454267 SUCCESS: standalone accepted eligibility -> simulated SIZE/FILLS -> atomic Postgres shadow BOOK transaction, source revalidation and provenance, duplicate and held-position guards, regression tests. This is NOT a comparative PICK and has no real order transport.
- Standalone entry explicitly requires SAVIP_SINGLE_SHADOW_ENTRY_ENABLED=true (default false). Model judgment separately requires SAVIP_SINGLE_ELIGIBILITY_ENABLED=true (default false). Neither was enabled or authorized for paid API spend. No genuine shadow fill yet; CI mocks are not live Postgres verification.
- Render auto-deploys main. Verify latest deploy commit, startup, read-only diagnostics and shadow event evidence before any claim of live behavior. Known pre-model-call duplicate race remains; fix before enabling paid single eligibility.
- Next: verify Render deploy and safe read-only database status; implement DB-backed atomic integration tests and prevent pre-call duplicate spend before enabling eligibility provider. Keep frozen thresholds, missing-X 0.60, multi-PICK, one held position, no real execution.
- Handoff prompt: Continue Jev-Desk from this file and docs/SAVIP_CHAIN_ROOT_CAUSE_WORK_ORDER_2026-10-08.md. PRs #200/#201 merged, CI passed. Verify actual Render deployment and genuine shadow-only status; do not enable standalone paid eligibility calls, real execution or alter gates. Fix duplicate paid-call race and add real Postgres transaction integration coverage. Update truth files with verified results.

## 2026-10-08 PR #202 completed
- PR #202 merged 8c6290784b0d102f616f4aaa36bfd655337628c2; CI run 37861403737 SUCCESS. Durable Postgres savip_single_eligibility_claims keyed by originating Jev event is acquired before any standalone paid model call. Claims persist on failed/ambiguous outcomes to prevent duplicate spending; completion records audited/duplicate/failed. No automatic retries.
- PR #201 was verified live on Render at dep-db42kfaj9qps73fubrh0, commit ac56baf2ec6baf03d17e17c673c1552b135878d2. Startup complete and GET / HTTP 200. PR #202 requires separate deploy verification.
- Both SAVIP_SINGLE_ELIGIBILITY_ENABLED and SAVIP_SINGLE_SHADOW_ENTRY_ENABLED remain default false; no approval to enable paid model calls. No real trading. No genuine standalone shadow BOOK fill verified.
- NEXT: verify deployment of #202, read-only diagnostics, and Postgres-backed concurrency/transaction integration; preserve multi-PICK and frozen thresholds. Do not claim end-to-end success from mocks.

## 2026-10-08 PR #203
- PR #203 merged 6b99a5a0c308f87b81fc29b6a9e3658495d8edc5, CI 37861719642 SUCCESS. Comparative BOOK opening now uses same pg_advisory_xact_lock(734101,1) as standalone BOOK and checks any open savip_reference position inside transaction, preventing concurrent cross-token opening by the two routes. Static regression test added; no live DB concurrency test performed.
- Render read-only SQL tool cannot connect to free Postgres dpg-db2sq2qd0e5s73ea0dd0-a because external IP allowlist is empty. Preserve security; do not open IP access just for inspection.
- Last verified live Render deployment dep-db42npmb7d7c73a57ej0 at 4c59eab, startup success and GET / 200. #203 deployment needs verification.
- Both standalone switches remain default OFF, no paid model calls enabled, no real trading. Genuine shadow BOOK fill still unverified.

## 2026-10-08 PR #204
- PR #204 merged cde9cc227a7b1fcfb183c1114ce534c1da62f483; CI 37862904641 SUCCESS. Standalone atomic BOOK commit now receives validated fresh observed liquidity and rechecks ticket against it rather than stale Jev dossier liquidity. Malformed evidence/social fail closed. No flags enabled.
- PR #203 deployment dep-db42pdad0e5s73fjrkig confirmed LIVE at e536b85331345940fe889037bc63e537edbc55d9; app startup complete, GET / HTTP 200.
- Next: deploy #204 and verify startup, investigate internal-only read-only DB observability, then genuine end-to-end shadow fill and Postgres concurrency tests. Do not change external DB allowlist, enable paid eligibility, or turn on real execution.

## Live verification 2026-10-09 UTC
- Render dep-db42vkui0phs73eq7qo0 LIVE commit 2108afca3ad49160f3e84c0fb0f96323d746fad5; application startup complete 00:06:23 UTC; GET / HTTP 200 at 00:06:32 UTC.
- Read-only public /savip-pipeline-diagnostics returned Jev configured=true, BSC SAVIP_JEV event 61601 soft_pass=true at 2026-10-08 23:14:14 UTC, PICK state=no_survivors, shadow entry state=single_entry_disabled, risk=no_open_position, shadow_positions=[].
- Read-only /savip-shadow-data returned scanned=1000 (UI recent sample, not worker 10000 cohort), FREE=14, TRADE=14 (12 Solana, 2 ETH), CHAIN last cycle checked=0, passed=0; no SAVIP trades. This is a momentary diagnostic snapshot, not a 72h cohort funnel conversion.
- NEXT: investigate why latest Jev soft pass did not progress to accepted standalone or comparative PICK, while preserving default-disabled paid standalone calls; verify whether a valid candidate is still within 15-minute freshness. Fix upstream Solana wallet owner verification separately and fail closed. Do not enable model calls or fake fills to manufacture conversion.
- External Render Postgres SQL is blocked by empty IP allowlist; do not weaken DB networking. Internal app read-only diagnostics are accessible.
