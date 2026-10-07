# Jev Desk — Project Source of Truth
Last updated: 2026-10-07
Status: active build; SHADOW ONLY. Live execution must remain disabled.

## Product
Mobile-first managed-cloud crypto research/trading desk. iPhone is the control/dashboard; managed cloud performs discovery, deterministic filtering, research judgments, persistence, shadow simulation, outcome tracking, risk research and reporting. User should not need to operate a Mac/VPS.

## Core architecture
Collection -> deterministic/free kills -> trade checks -> chain/dossier checks -> Jev question-set judgments where validated -> soft gates -> multi-candidate PICK -> SIZE -> FILLS -> RISK -> persistent BOOK -> 15-minute SHIFT/main loop.
Principle: code fetches facts; model judges ambiguous questions; deterministic code validates/applies calibrated thresholds; execution never reinterprets judgment.
SOCIAL uses only the exact on-chain x_handle; never substitute similar handles.
PICK is for multiple survivors. One survivor still must pass worth-trading/confidence/common risk modifiers.
One held position prevents scanning; RISK alone releases the book after confirmed close.

## Research methodology
Three arms on identical observations:
A supplied/reference architecture (all supplied constants are reference-only)
B deterministic Python-only
C Jev + Python
Preserve rejected/no-order candidates as counterfactuals.
Forward shadow and historical replay are separate datasets. Historical replay accelerates research but never replaces untouched forward validation.
Outcome horizons: 5m,15m,30m,1h,3h,6h,12h,24h,48h,72h.
Measure executable results after fees/slippage, not just mark price: expectancy, PF, median return, win rate, MFE/MAE, drawdown, rug/tail loss, selection frequency, missed winners and execution-cost drag.
Progression: audit -> state machine -> collection -> outcome labeling -> replay -> optimization -> frozen out-of-sample forward validation -> simulated execution -> only then consider tightly controlled live validation.
No profitability promises.

## Safety invariants
SHADOW ONLY. No wallet/private keys. No autonomous real-money orders. Any future live capability requires a separate explicit decision after validation.
Jev/system unavailable => fail closed, not continue around it.
Incomplete/invalid Jev response => fail closed.
Unknown order state after timeout => reconcile exposure; do not assume failure and resume scans.

## Forensic fixes that must not regress
- BOOK only records confirmed filled exposure: judgment -> SIZE -> nonzero -> FILLS -> confirmed fill -> BOOK.take(actual fill) -> RISK -> confirmed close -> BOOK.release.
- Apply common ticket/risk modifiers to both single and multi-survivor paths.
- Preserve model ID/provenance with every judgment.
- Do not use tid PRIMARY KEY style storage that destroys bench/history.
- Persistent DB/state must be concurrency-safe; do not use destructive replace semantics for live position state.
- Define/validate any sizing edge before using Kelly; never invent missing semantics.
- Resolve execution/risk priority conflicts explicitly.
- Generic exception handling must not defeat fail-closed, 422 stop-cycle, or 429 backoff behavior.
- Rejected candidates must be logged for counterfactual analysis.
- 15-minute cadence is start-to-start, not sleep-15-min-after-work.

## Current implementation
Repository: grewaljoe2/Jev-Desk
Managed service: Render web service jev-desk
Durable research DB: private Render PostgreSQL jev-desk-research.
Current merged main at creation of this file: v0.5.1 / commit e1292f41da0691df15e0ec226a861b13deaddf03.
v0.5.1 schedules outcome jobs for each observed token at all ten horizons and exposes durable research counts on the mobile dashboard.
Discovery: GeckoTerminal new-pool feed across configured networks.
Strategy arms currently exist but Python-only is not yet a calibrated finished strategy and Jev arm intentionally fails closed until configured/validated.
Real trades remain OFF.

## Known technical work remaining
1. Verify v0.5.1 deployment and Postgres storage from app-side health/counts.
2. Build outcome worker that revisits the same pool/token, stores actual elapsed horizon observations and handles retries/rate limits.
3. Add current price/pool identity and sufficient normalized observations.
4. Harden provider diagnostics, 429 backoff, scheduler exception survival and shutdown.
5. Reduce per-event DB connection churn (pool/batching).
6. Build historical replay/simulated-trade pipeline, clearly separated from forward data.
7. Add realistic fills/fees/slippage, MFE/MAE and strategy comparison metrics.
8. Build clean mobile research dashboard around real metrics; keep debug detail secondary.
9. Freeze candidates only after adequate evidence, then untouched forward validation.
10. Do not enable live execution as part of these steps.

## Deployment caveats
Free Render service may sleep; do not claim exact always-on 5-minute observations until hosting guarantees it.
The current free Render PostgreSQL database is development infrastructure and was reported to expire 2026-11-06; upgrade/migrate before expiry if project continues. Never expose DATABASE_URL/password. Do not open external DB networking merely for inspection.


## 2026-10-07 live research lifecycle update
Authoritative current state after PRs #33-#36; this section supersedes older implementation-status bullets above where they conflict.
- Production remains SHADOW ONLY; live execution is disabled.
- PR #33 bound proper qualification snapshots to their own clean outcome cohorts and made discovery/manual scans schedule qualification without early strategy evaluation.
- PR #34 made the original >=15m qualification target immutable across retries by separating retry time into next_attempt_at. Lateness is measured against the original target.
- PR #35 fixed the qualification capacity bottleneck by batching same-network GeckoTerminal pool observations (up to 30 per request) and pacing the public API conservatively. Observed production recovery: due queue fell from 103 to 0 while checked rose from 102 to 238; later 13 due / 247 checked and reported on schedule.
- PR #36 separated corrected qualification-entry evidence from old discovery-era replay evidence. Qualification diagnostics now select snapshots carrying raw.qualification_job_id; old cohorts remain stored and are not rewritten/deleted.
- Latest observed mobile state after PR #36: Outcomes 299; Due Now outcome backlog 3884; snapshots with age 828; qualification queue 77 waiting / 13 due / 247 checked; Market Samples 61; scoreable strategy evidence 60; Q0/U1/R60 in all three arms. The one unscorable reason is missing:liquidity_usd. The 60 rejected samples still report age_too_young.
- IMPORTANT: those 60 age_too_young corrected-entry samples are not trusted strategy evidence yet. QualificationWorker explicitly checks snap.age_minutes >=15 before process_snapshot, so this contradiction must be traced before allowing them into the evidence gate. Do not lower thresholds, relabel old data, or count these 60 toward validation until provenance is resolved.
- Qualification throughput is currently healthy after batching; do not undo batching or add concurrent workers blindly. The separate outcome backlog remains large and lower priority than time-sensitive qualification.
- Next task: trace one qualification_job_id end-to-end (job due_at -> provider pool_created_at/age_minutes -> SNAPSHOT raw qualification metadata -> evaluate_all/filter reason -> outcome cohort -> qualification dataset). Determine why qualification-tagged snapshots can diagnose age_too_young despite the >=15m worker guard. Add a fail-closed invariant so an entry cohort with age_minutes <15 cannot become strategy evidence. Then re-verify production Q/U/R and evidence counts.
- After the age/provenance contradiction: add qualification-processing idempotency for crash/retry, harden scheduler exception survival/restart, terminal handling for disappeared/404 pools, then mature outcome evidence and persistent shadow trade lifecycle.
- Provider note: current GeckoTerminal public documentation describes an approximate 10 calls/minute limit that may fluctuate; current code uses 6.5s global pacing plus multi-pool batching.

## New-chat protocol
Read this file first, then NEXT_CHAT.md, then inspect the current main branch and current deployment state. The code and current DB/deployment state outrank stale prose. Do not reset research, repeat rejected branches, blindly copy reference thresholds, or make the user reconstruct prior work. Continue from the first unfinished verified milestone. Update this file whenever architecture, benchmark, validation status or roadmap materially changes.


## 2026-10-07 latest handoff — shadow lifecycle + deployment failure
This section supersedes earlier live-state bullets where they conflict.

### Last VERIFIED production
- Render service `jev-desk`, service id `srv-db2sp7e7bikc73as8690`, workspace `tea-db2snq142hec73fp839g`.
- Last verified LIVE commit is PR #46, `df762b8542b12caf4bab225133b143c6da040a7d`.
- Deploy `dep-db319n49v7es73ak7ql0` completed LIVE at 2026-10-07 09:46:58Z. Startup completed and /, /status, /research-health and /qualification-data returned 200.
- Production is SHADOW ONLY and real execution remains disabled.
- #46 makes discovery yield while qualification batches are actively due. OutcomeWorker already yields when qualification is due/soon. This is intended to protect scarce GeckoTerminal free API capacity.
- Provider 429s were still observed before #46; do not claim the rate-limit bottleneck is solved until post-#46 queue/log evidence proves it.

### Forward shadow trading code
- PR #43 introduced future-only research shadow entries. A genuine future Reference-qualified >=15m qualification snapshot opens a normalized $100 virtual position using the contemporaneous provider-observed price proxy. Existing earlier qualifiers are NOT retroactively filled. No wallet/broker action exists.
- PR #47, commit `5c50ff7626591573776b051ab642d4e8f68eeeb5`, added mark-to-market updates by reusing OutcomeWorker observations, intentionally adding no provider calls. It adds last_price/last_marked_at and unrealized shadow P&L.
- PR #48, commit `6b23252a21ccaa3b47a7334089b0d0142a126257`, added parallel research-only exit arms for future entries: `tp20_sl10_v1`, `trail15_after10_v1`, and `time24h_v1`. These are experiments sharing the same entry, not a selected live exit policy. Exit arms are marked only from existing outcome observations.
- The primary virtual position is intentionally separate from experimental exit arms; do not silently treat an exit-arm result as the primary/live-style position close.
- Real trading remains OFF. Do not add wallet keys, broker execution, or real-money sizing.

### CURRENT FAILURE — fix before any more feature work
- Deploy `dep-db31cvc9v7es73akiivg` for PR #48 FAILED (`update_failed`) at 2026-10-07 09:53:35Z. Build succeeded; application import/startup failed.
- Exact failure is again malformed dashboard source in `app/main.py`, line 77: `SyntaxError: unmatched '}'`.
- Render traceback shows the JS around `shadowpnl.textContent` was corrupted so the Python triple-quoted HTML closes in the middle of the JS and a duplicate tail follows. The log contains the broken shape `shadowpnl.textContent='... </html>\"\"\"+Number((sp.realized_pnl_usd||0)+(sp.unrealized_pnl_usd||0)).toFixed(2);...`.
- This was introduced while PR #47 changed the dashboard P&L line. Do NOT keep doing fragile substring replacements inside the giant one-line DASHBOARD string.
- Production should still be serving the previously verified #46 instance because Render rejected #48. Verify deploy state before assuming.
- FIRST NEXT ACTION: repair `app/main.py` structurally, re-read the full relevant dashboard tail, and run a Python syntax/import check if possible before merging/deploying. Prefer rewriting the complete affected JS/DASHBOARD tail cleanly rather than another narrow quote-sensitive replacement. Then deploy and verify startup, /research-health, DB schema migration for shadow_exit_arms, and qualification health.
- Do not claim PR #47/#48 features are live until a newer deploy than #46 is verified LIVE.

### Research/queue state before this handoff
- Recent mobile screenshots before #46 showed Reference/Python qualification increasing from Q6 to Q9 while checked increased 419 -> 521, so qualification was functioning but bursty.
- At that time queue was roughly 51 waiting / 4 due / 521 checked and UI said 15-minute checks on schedule.
- Outcomes increased roughly 299 -> 625 while outcome backlog still grew to ~5353 due / ~13780 pending.
- Fresh pre-#46 logs showed GeckoTerminal 429s affecting both qualification and outcome batches. Preserve priority order: due qualification first; active/qualified shadow evidence next; qualified outcomes; sampled rejected controls; discovery/background last.
- Do not loosen qualification thresholds to manufacture trades.

### Important next engineering items after deployment repair
1. Verify #47/#48 schema and lifecycle in production with a future genuine qualifier; never fabricate an old entry.
2. Add explicit API/UI detail for open shadow positions and the three exit arms (entry/current/exit/P&L/reason) once lifecycle is proven.
3. Fix qualification replay's current 500-sample cap using aggregation/pagination rather than silently truncating strategy evidence.
4. Deal with the old ~13k outcome backlog using an explicit versioned terminal/superseded policy for low-value rejected horizons; never delete completed evidence.
5. Add exact decision provenance (baseline_event_id/qualification_job_id) rather than token-only qualified-priority joins.
6. Harden qualification idempotency/transactionality and scheduler exception survival.
7. Historical backtesting remains desired but not yet implemented; keep it strictly separate from untouched forward evidence and never use current fields as historical point-in-time facts.
