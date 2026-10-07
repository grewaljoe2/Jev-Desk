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

## New-chat protocol
Read this file first, then NEXT_CHAT.md, then inspect the current main branch and current deployment state. The code and current DB/deployment state outrank stale prose. Do not reset research, repeat rejected branches, blindly copy reference thresholds, or make the user reconstruct prior work. Continue from the first unfinished verified milestone. Update this file whenever architecture, benchmark, validation status or roadmap materially changes.
