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
