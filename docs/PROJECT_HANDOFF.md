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


## 2026-10-07 verified update — evidence accounting, author comparison, active monitoring
This section supersedes the stale deployment-failure state above where it conflicts.

### Current verified production
- PR #50 repaired the #48 dashboard corruption and deployed successfully.
- PR #51 removed the 500-sample qualification aggregate cap and improved 429 Retry-After handling.
- PR #52 added explicit forward-vs-legacy shadow provenance and the real Trades ledger. Existing pre-forward rows remain `legacy_pre_forward`; new valid entries are `forward_qualification_v1`.
- PR #53 changed Home to forward-only counts/P&L but hit the recurring giant-DASHBOARD corruption. PR #54 structurally repaired it.
- PR #55, merge commit `2e1a49e05233ce2bc2521261e46c67fb0ef0fc85`, makes exit evidence interpretable: per-policy closed/open counts, wins/losses, realized and unrealized P&L, average closed return, gross profit/loss, win rate and profit factor. Trades renders each exit arm's state/return/reason. The primary never-sell position is explicitly a Hold benchmark, not strategy P&L. Home headline is TP/SL realized P&L.
- PR #56, merge commit `ead05c485492fbcfb41679279a87014fb5e9b6a8`, adds a dedicated ActiveTradeWorker. Render deploy `dep-db32g17avr4c739ie690` is VERIFIED LIVE (finished 2026-10-07 11:08:37Z).
- ActiveTradeWorker targets a 15-second loop, batches up to 30 same-chain pools, uses only actual provider-observed prices, and never fabricates threshold fills. Qualification due jobs retain first priority. While forward positions are open, background OutcomeWorker traffic yields so scarce provider capacity is used for active marks. Actual observation frequency is still constrained by GeckoTerminal shared pacing/rate limits.
- Real execution remains OFF.

### First untouched forward trades / why accounting changed
- Legacy Solana position is excluded from forward validation and has no retroactive exit arms.
- First two `forward_qualification_v1` $100 entries demonstrated that Hold benchmark P&L is not a valid headline for exit-strategy performance.
- One forward trade was observed around +26.08% before later collapsing near zero. Its `tp20_sl10_v1` arm closed at the actual observed profitable price; the later primary hold collapse must not overwrite that realized exit evidence.
- The other forward trade crossed the nominal -10% stop between observations and the first observed exit price was near zero. The system correctly records the observed executable proxy rather than inventing a -10% fill. This is important evidence about microcap gap/rug risk and motivates faster active monitoring.
- Do not choose an exit-policy winner from two trades. Preserve untouched forward evidence and grow the sample.

### Newly verified author/reference-strategy distinction
- Jarrod Watts' public `jev-trader` architecture is NOT a 15-minute new-token buy-and-hold strategy. It is a very high-frequency Kuru MON/USDC order-book/liquidity-provision experiment: decisions/requotes are approximately per ~300 ms block, with a model question on roughly a 100-block/~30-second horizon. It repeatedly posts/replaces post-only orders, seeks spread capture, and manages inventory rather than making one $100 all-in trade and waiting.
- The public project uses a $100-style bankroll/configuration, but do NOT state that large real-money profit from $100 is verified. Public materials support dry-run/simulated fills and a mock/default model unless Jev is configured; headline/demo performance is not equivalent to audited live-money performance.
- Jev Desk's >=15m minimum qualification was OUR microcap research design, not inherited from the author. This explains a major architectural divergence from the user's original intent of frequent opportunities and rapid bankroll recycling.
- Preserve the existing >=15m strategy as a clean control. Next research branch should add a separately versioned sub-15m/high-frequency entry experiment (candidate ages such as ~1m/3m/5m/10m versus 15m control) rather than silently changing historical evidence. Compare executable expectancy, rug/tail loss, MFE/MAE, realized exit-policy P&L, trade frequency and bankroll recycling.
- Younger entries must be paired with fast active-position monitoring. Do not loosen age/filter rules merely to create more trades, and do not contaminate the existing 15m cohort.
- Important conceptual point: matching the author's frequency principle does not mean pretending Jev Desk's current DEX microcap/provider environment can reproduce 300 ms order-book market making. Treat author-style high frequency as a separate architecture/research arm and measure what is actually achievable with the available point-in-time data and API budget.

### Immediate roadmap
1. Verify #55/#56 behavior on additional untouched forward entries and expose active-monitor health in UI if useful.
2. Design and implement versioned sub-15m cohorts without modifying the existing 15m control evidence.
3. Keep realized exit-policy performance as the strategy headline; Hold benchmark stays a research comparator.
4. Improve active monitoring/provider capacity if evidence shows observation gaps materially distort exits; preserve actual observed-fill accounting.
5. Harden baseline-event idempotency/transactionality and refactor the giant inline DASHBOARD into a safer template/static file before more UI-heavy changes.
6. Update this handoff after each material architecture/validation change.


<!-- deploy-sync: 2026-10-07 PR70 fresh-first outcome policy -->


### 2026-10-07 — Fresh-first outcome scheduling
Production policy changed so fresh 1m/3m/5m/10m and 15m entry observations outrank historical outcome traffic. Historical outcome checks are spare-capacity only; stale point-in-time checks are retained as missed rather than fetched late, and remaining usable historical checks are newest-first. Real execution remains disabled.


### 2026-10-07 — Fresh-first production deployment verified
- Fresh-token scheduling policy from PR #70 is now in production. The policy protects fresh 1m/3m/5m/10m Fast entry windows and the 15m control before background historical outcomes; active forward positions remain higher value than background outcome replay.
- Historical outcome selection is newest-first rather than oldest-first. Stale point-in-time historical jobs are marked `missed` with `missed_observation_window` instead of spending provider requests and pretending late observations were on time. The expiry tolerance scales at 20% of requested horizon, minimum 5 minutes and maximum 60 minutes.
- No entry thresholds changed. Real execution remains disabled / shadow only.
- PR #70 squash merge: `167d0752c968debb8bb98866b8f54e95901a0428`.
- Render's normal GitHub commit sync failed to create a deployment even though service configuration was correct (repo grewaljoe2/Jev-Desk, branch main, autoDeploy=yes, trigger=commit). A fresh documentation commit/PR #71 produced main commit `13f035f6f1958a6171315c1e5777fc54f76b3864`.
- To force Render to consume current main without changing trading behavior or paid infrastructure, environment variable `JEV_DEPLOY_SYNC` was merged/set to the current main commit SHA. Render reported this triggered deployment `dep-db33kjflk1mc739aq29g`.
- Deployment `dep-db33kjflk1mc739aq29g` finished LIVE at 2026-10-07T12:26:26.763589Z on commit `13f035f6f1958a6171315c1e5777fc54f76b3864`. Therefore the fresh-first #70 code is now live.
- If future Render auto-deploy again stalls behind GitHub main, first verify main/service branch; an innocuous merged main commit plus updating `JEV_DEPLOY_SYNC` can force a deployment without touching strategy behavior. Do not claim deployed until get_deploy/list_deploys reports the intended main commit live.

### Next-session priority
Verify production behavior after the fresh-first deployment: Fast/15m timing lateness, 429 frequency, discovery continuity, active-position marking, and whether the historical due backlog falls as stale jobs become missed. Do not change filters merely to manufacture Fast trades. If provider contention remains, continue the planned centralized shared REST observation/batching architecture rather than returning to per-worker sleep/priority patches. Keep 15m control alive and real trading OFF.

## 2026-10-07 current authoritative Savip/Jev checkpoint
This section supersedes older deployment/status/roadmap sections above where they conflict.

### Verified production
- Current verified LIVE main commit: `2791d58c971d6ce5236b64fa9bf42289bf68ada0` (PR #126, Restore Savip shadow trades card).
- Render deployment `dep-db3bd58m7kps73dn6skg` finished LIVE at 2026-10-07T21:16:54.240874Z.
- Production remains SHADOW ONLY. Real execution is OFF.
- PR #123 removed the orphaned JavaScript tail after the DASHBOARD triple quote that caused repeated Render startup SyntaxErrors.
- PR #124 made the Savip path event-driven: one completed DEX cycle wakes CHAIN once; a successful CHAIN pass immediately wakes Jev; a Jev soft-pass immediately wakes PICK. Published thresholds were not loosened.
- PR #124 also fixes the earlier callback-per-enriched-row behavior that could invoke CHAIN repeatedly inside one DEX cycle. The dossier cap remains 3 per bounded CHAIN cycle.
- Current entry worker already has a held-position guard: if any Savip reference position is open, a second accepted token cannot open.
- PR #126 restored the missing `svtrades` dashboard container. The missing DOM node had caused the Savip refresh JavaScript to throw, making FREE CUT evidence appear unavailable even while upper metrics loaded. Savip now has a BOOK trade card for status, filled size, entry, last price and P&L.

### Savip published-reference architecture currently being preserved
COLLECT -> FREE CUT -> TRADE CUT -> CHAIN/dossier -> typed Jev judgments -> soft gates -> PICK -> PRICE/SIZE -> FILLS -> persistent BOOK -> 5-minute RISK -> exit -> fresh cycle/re-entry.
- Published hard FREE rules: age 15m-72h; liquidity >= $12k; volume24 >= $40k; mcap $60k-$8m.
- TRADE CUT: pair required; trades24 >=150; reject no-sells condition when sells_h1==0 and buys_h1>20.
- CHAIN: top wallet <=5%; top10 <=60%; holders >=80; Solana mint/freeze authority checks; BSC honeypot check.
- Dossier cap 3/cycle; DEX target cap 25/cycle; main Savip cycle 15 minutes.
- One held position blocks the Savip decision/entry path. Re-entry requires exit plus a fresh cycle/win.
- Multiple soft survivors use Jev PICK plus worth-trading/confidence gates. Do not loosen gates to manufacture trades.
- Exact-X boundary remains strict: SOCIAL may only use the exact project/on-chain X handle; no similar-handle substitution.
- Actual X collection is not yet active; missing-X handling must remain explicit rather than fabricated.
- The TypeSafe/Jev adapter is configured server-side; never expose its API key. Do not claim a paid Jev judgment completed unless production evidence confirms it.

### Current observed pipeline evidence
- A genuine CHAIN pass has previously been observed in production (checked 1 / passed 1), proving the deterministic path can reach the Jev boundary.
- A later mobile observation showed SCANNED 200, FREE CUT 3, WAITING AGE 54, CHAIN checked 1 / passed 0, Jev ARMED and PICK ARMED. This is valid no-trade behavior; do not loosen filters.
- A FREE-vs-TRADE age discrepancy has been observed on the same token (FREE age about 37m versus enriched TRADE age about 6.5m). Audit the age source/provenance before trusting downstream age display/evidence.

### Open reliability/fidelity work
1. Persist Savip RISK market-data failure counts. They are currently in memory, so a process restart can reset the published retry-twice/third-failure close sequence. Also ensure a third failure can resolve a safe close price without fabricating one.
2. Audit DexScreener 429 handling/pacing. Do not invent undocumented rate limits.
3. Audit Jev claim failure/retry semantics: failed claims currently risk becoming permanently excluded rather than safely retried.
4. Verify PICK fingerprint IDs are the intended Jev event IDs and preserve fresh-cycle/re-entry idempotency.
5. Audit the hardcoded shadow bank `bank_usd=1000.0` against the intended persistent capital/BOOK source before changing it.
6. Fix stale readiness/status reporting such as hardcoded paid-call state; status must reflect observed truth.
7. Audit SQLite/dev uniqueness versus repeated closed positions/re-entry semantics.
8. Add holder-count fallback only from a trustworthy point-in-time source; never fabricate missing holder facts.
9. Guard the Savip-specific earliest scan/enrichment stage while a position is held if strict published “entire scan skipped” fidelity is required.
10. Replace newest-200 candidate truncation with a bounded persistent/queued 72h universe so older eligible candidates cannot starve.
11. Audit the FREE-vs-TRADE age-source discrepancy.
12. Refactor the giant inline DASHBOARD before further large UI changes; prior narrow string edits caused repeated source corruption.
13. After system correctness is complete, build the planned mobile “living desk” visualization driven only by real backend events/states. Do not fake agent activity or copy Savip artwork/assets.

### Process rules
- Code/deployment/DB observations outrank stale prose.
- Re-read exact branch source after every connector write before merge.
- Before deploy, ensure `app/main.py` has exactly one intended DASHBOARD closing triple quote and no orphaned JavaScript tail.
- Do not weaken security or Postgres network allowlists for inspection.
- Do not mix MT5 research into Jev Desk.
- Real execution stays OFF until a separate explicit post-validation decision.



## 2026-10-07 verified exact-X SOCIAL production checkpoint

PR #128 added the no-key FxTwitter/FxEmbed public exact-handle reader, verifies the returned handle against the dossier's exact project X handle, supplies observed profile/posts to Jev SOCIAL, and permits failed Jev claims to retry. PR #129 restored published missing-X behavior: if the project has no handle or the free public reader cannot provide an observation, SOCIAL evidence remains missing rather than fabricated, and the existing shadow sizing applies the 0.60 missing-X factor if the candidate ultimately qualifies. Real execution remains OFF. The free reader is third-party and availability/schema are not guaranteed; live evidence success and a paid TypeSafe call have NOT yet been verified.

Verified Render deployment: `dep-db3bon2jnfac739bi6dg`, commit `e25b10793804ad28f9f026e477863f4517ea4a0c`, status LIVE, finished 2026-10-07T21:41:37.628157Z. This supersedes older production and missing-X statements above. Do not claim full end-to-end validation until a genuine CHAIN survivor is seen flowing through observed/missing SOCIAL, typed Jev, PICK and shadow BOOK with evidence. Next: production evidence verification, bounded 200 pool versus cumulative SCANNED audit, multi-candidate PICK sequencing, and remaining reliability items. Do not loosen gates or claim the free reader succeeded without a verified response.


## 2026-10-07 handoff — Savip discovery throughput forensic (IN PROGRESS)

User asks why Savip reported many trades while Jev Desk has none, and why SCANNED appears stuck at 200. PRIORITY: finish evidence-based discovery/throughput audit before further strategy changes. Do not assume Savip's trade frequency or our scanner health without measured comparable time windows.

Verified code: `app/main.py` GET `/savip-shadow-data` calls `savip_candidate_pool(window_minutes=72*60)` and exposes `scanned=funnel['scanned']`, `free_cut_survivor_count`, `wait_too_young_count`, FREE kill reasons, missing fields, TRADE survivors/kills, CHAIN checked/passed/errors, Jev state, shadow BOOK. Thus 200 is a value produced by `savip_candidate_pool`, not independently verified lifetime discovery count. Inspect its actual SQL/cap and freshness; previous 200-pool-cap hypothesis is NOT YET VERIFIED. Determine unique discovered total vs 72h eligible pool vs candidate cap, discovery last success, arrivals/cycle, age at discovery, rejection stage, 429s, and network coverage. Compare published Savip collector, without loosening thresholds. Public GeckoTerminal calls ~10/min shared with qualification/outcomes; historical 429 and background discovery yielding were documented. Render free plan and one instance. Do not assume this alone explains missing trades.

Latest verified runtime: Render service `srv-db2sp7e7bikc73as8690`, workspace `tea-db2snq142hec73fp839g`, URL `https://jev-desk.onrender.com`; PR #129 code commit `e25b10793804ad28f9f026e477863f4517ea4a0c` LIVE deployment `dep-db3bon2jnfac739bi6dg`, finished 2026-10-07T21:41:37Z. PR #130 documented this checkpoint. PR #128 free exact-handle public X reader, PR #129 missing/unavailable social evidence flows to Jev and shadow ticket `missing_x_factor=0.60`; real execution OFF. Genuine complete SOCIAL→Jev→PICK→BOOK not verified. No need to wait for rare survivor to test mechanics: use isolated fixture/replay integration with clear provenance, never feed fixtures to production BOOK.

NEXT: locate definition of `savip_candidate_pool` (import in `app/main.py`), inspect source and actual database query; inspect collector and scanner scheduling, provider rate-limit logs, and production `/savip-shadow-data` counters/timestamps. Add honest cumulative vs bounded-pool vs per-cycle UI/metrics if needed. Test and deploy only after verifying fixes. Do not weaken Savip FREE/TRADE/CHAIN/Jev/PICK thresholds to manufacture trades, do not buy paid X API, do not enable real execution.


### 2026-10-07 Jev failure recovery and lifecycle verification
PRs #143-#147 improved DEX latency, Jev/PICK cadence, missing-X handling, CHAIN evidence visibility, and shadow exact-pair lookup. Next fix distinguishes `failed_once` Jev claims from completed judgments, without retrying paid model calls on the same CHAIN event; new CHAIN events remain eligible and oldest unclaimed passes are processed first. Do not assert end-to-end success until a genuine shadow entry, risk observation, and exit are observed. No real execution, no new paid APIs, published gates unchanged.
