# Solana owner verification — offline research, 2026-10-09

## Release decision
**BLOCKED.** No PR merge or Render deployment until a consistent, complete owner map and end-to-end shadow pipeline pass are independently demonstrated offline.

## Observed research
- Helius cursor research for mint `6Mix12LiHrQFojaQEnfPUC65Qkwd6X4Y5Qg93oFbordr`: 11 pages, 10,901 token accounts, 10,846 owners, 3,131 positive holders.
- Sum of scanned balances matched reported mint supply (999,972,190,172,222 raw units), but pagination crossed slots (454983630–454983638); **not an atomic snapshot**.
- Largest owner fraction approximately 8.77%; this research mint would fail the existing top-wallet threshold even if coverage were verified.
- Public independent RPC full account scan was too large; independent supply equality does not independently certify ownership.
- Main branch Helius evidence remains diagnostic-only; public RPC cooldown can skip Solana checks entirely.

## Synthetic adversarial tests
Six isolated Python assertions previously reported passing (not an integration or production verification):
1. Mixed-slot pages can report a 100% concentrated owner when both true snapshots are 50%.
2. Repeated identical stitched scans do not prove snapshot correctness.
3. Closed accounts may be absent from a mint-filtered delta, leaving stale balances.
4. Supply conservation does not detect ownership changes.
5. Zero-balance token accounts do not count as positive holders.
6. Largest token-account concentration is only a lower bound on owner concentration.

These are synthetic counterexamples, **not proof of a functioning verifier**. Re-run as repository tests before relying on results.

## Branch and prior PR
- Research branch `research/solana-owner-snapshot-proof`, commit `3e3157f9a293e9ae70eb7f72bf3f76e389651d41`, expands allowable Helius page size to 10,000 **only on research branch**.
- PR #273 closed, unmerged: two matching scans and supply cross-check insufficient; same-slot check likely impractical for active large mints.

## Mandatory next steps
1. Verify provider contract for snapshot-stable pagination or complete changes including deletions; do not assume `minContextSlot` pins a snapshot.
2. Build a falsifiable, realistic offline fixture suite (slot drift, transfer, closure, duplicate/missing pages, rate limits, Token-2022).
3. Implement a verifier that passes the suite while retaining hard thresholds and fail-closed behavior.
4. Run CHAIN → Jev → PICK → SIZE → FILLS → RISK → BOOK shadow-only regression tests and audit controls.
5. Only then consider PR, CI, merge, deployment, and live end-to-end verification. If evidence is unavailable, report architectural blocker, not a fix.

## 2026-10-09 independent execution checkpoint
- Executed `/mnt/data/solana_owner_release_gate_tests.py` in the working Python environment: **6/6 synthetic checks PASS**. This is the locally mounted script, not the GitHub test file.
- Retrieved and inspected committed `tests/test_solana_owner_snapshot_adversarial.py`; it contains six `unittest` test methods, but its execution has **not** been verified in CI. GitHub returned no workflow runs for commit `c6dd0c93061cf37c010712ef617bb6648dcc9255`.
- The tests currently demonstrate *counterexamples only* and are not wired to exercise `collect_cursor_owner_research`, `SavipChainProvider`, or `SavipChainWorker`. The mandatory integration/offline verifier release gate is **NOT MET**.
- Do not misreport the local standalone script's pass as GitHub CI or production implementation validation.

## Offline execution checkpoint — 2026-10-09 (latest)
- Locally executed `/mnt/data/solana_owner_release_gate_tests.py`: six synthetic adversarial checks passed.
- Locally compiled `/mnt/data/jev_research/test_helius_collector_rpc.py` using `py_compile`: syntax accepted.
- Attempted `python -m unittest discover -s /mnt/data/jev_research -p 'test_helius_collector_rpc.py' -v`: **FAILED TO START** with `ModuleNotFoundError: No module named 'app'` because the working container has only the test file, not a checked-out Jev Desk repository. This is an environment/import failure, not a failing RPC assertion and not a passing integration test.
- GitHub connector has repository source, but local container cannot resolve `github.com` to clone; do not claim the mocked-RPC tests were executed until the actual app modules are present.
- Remediation: run test from a complete repository checkout or in GitHub Actions on research branch; do not merge/deploy based on standalone synthetic tests.

## Offline execution checkpoint — mocked collector (2026-10-09)
- Reconstructed the relevant collector and decoder modules locally from GitHub connector source into `/mnt/data/jev_offline/` because direct GitHub clone is unavailable in the container. Reconstructed the nine committed mocked-RPC tests locally.
- Executed `cd /mnt/data/jev_offline && python -m unittest discover -s tests -p 'test_helius_collector_rpc.py' -v`: **9 tests ran, 9 passed** (0.008s).
- Tested: same-slot still diagnostic, mixed-slot still diagnostic, duplicate account, missing cursor, page cap, 429, wrong program, Token-2022 diagnostic, 10k page-size acceptance.
- **Scope limitation:** This is a manually reconstructed copy, not a verified byte-identical Git checkout or GitHub CI run. No full worker/pipeline integration tested. No consistent complete ownership-map certification demonstrated. Production release gate remains BLOCKED.

## Collector reported-total hardening (2026-10-09)
- Identified that prior collector returned `cursor_exhausted_unverified` even when provider `totalResults` varied between pages or disagreed with unique collected account count. This was diagnostic-only but misleading.
- Research branch commits `dfda3b9` and `29815c3` now fail closed with `inconsistent_reported_total` or `reported_total_account_mismatch`, with two additional mocked-RPC tests.
- Executed 11/11 tests locally against the reconstructed collector after equivalent code edits. **Not CI or full-repo checkout verification**; no owner-map certification and no CHAIN approval.
- Potential caveat: provider `totalResults` semantics must be independently checked against Helius contract before treating mismatch as a permanent invalidity rather than a transient retryable inconsistency. No production deployment.

## 13-case offline collector rerun (2026-10-09)
- Executed `cd /mnt/data/jev_offline && python -m unittest discover -s tests -p 'test_helius_collector_rpc.py' -v` after adding local equivalents of the two new GitHub tests. Result: **13 tests run, 13 passed** (0.009 seconds).
- **Important provenance limitation:** local collector and test files were manually reconstructed from connector-fetched repository source; the local test names/format differ from the committed GitHub test file. This is **not** a byte-identical Git checkout or GitHub CI run, and does not validate the full CHAIN worker or prove a complete consistent owner snapshot.
- No merge or deployment; release gate remains blocked.

## Independent RPC owner-correlation slot guard
- Source audit found `collect_independently_confirmed_owner_evidence` accepted identical owner digests from different `accounts_slot` values, and `SavipChainProvider.fetch_independent_owner_evidence` could then mark `owner_coverage_complete=True`. This is an actual possible false-positive route (matching digest does not certify simultaneous snapshot).
- Research commit `00706bbc` now rejects different account slots with `cross_provider_slot_mismatch` before promoting correlation. Regression test file `tests/test_solana_independent_owner_slots.py` committed as `d238ba67` with 3 mocked scenarios. **These 3 tests are not yet execution-verified.**
- Important remaining gap: `collect_owner_evidence` reads mint at a prior slot and only checks account/supply slot equality; `minContextSlot` is not snapshot pinning. Provider independence and completeness also remain unresolved. No release authorization.

## CHAIN provider defense in depth
- Commit `9a6263d` requires `cross_provider_same_slot=True`, integer primary snapshot slot, and equal primary/secondary snapshot slots at the `SavipChainProvider` acceptance boundary; protects against forged/incomplete correlation result.
- Commit `445cb31` adds five mocked provider-boundary tests (positive control and four fail-closed scenarios). **Tests committed, not executed in this turn.**
- This still does not prove actual RPC completeness or atomicity. No production release approval.

## Cross-provider and CHAIN boundary offline execution (2026-10-09)
- Executed reconstructed local versions of `tests/test_solana_independent_owner_slots.py` and `tests/test_solana_provider_owner_boundary.py` with Python `unittest`: **3/3 + 5/5 passed**.
- First attempt failed at import because local decoder reconstruction lacked `SUPPORTED`; resolved by removing unused imports from local testing shim (no GitHub source change), then reran successfully.
- **Provenance caveat:** locally simplified copies of pipeline/provider functions were used, not exact GitHub module bytes. Therefore this validates the slot-check logic in isolation, not the actual full application import graph or integration. CI remains unverified.
- Combined earlier mocked collector tests: 13/13 passed separately. No owner snapshot certification, no production merge or deploy.

## Three-way slot alignment
- Audit identified `getAccountInfo` mint slot could be earlier than `getProgramAccounts` token-account slot, while code only checked that account slot was not older. Reconciliation could then compare mint supply from an earlier state with later token accounts.
- Research commit `5f6bc3c` rejects this with `mint_accounts_slot_mismatch`. Commit `2d9f78f` includes this mismatch in existing bounded per-provider retry path. Commit `cfe6f68` adds two mocked tests for retry failure and recovery; **not execution-verified**.
- All three observations now must have equal slots before reconciliation, but a slot equality check alone is not proof of provider snapshot completeness or independence. No merge/deploy.

## Offline rerun after bounded mint-slot retry (2026-10-09)
- Executed `python -m unittest discover -s tests -v` in `/mnt/data/jev_offline` after updating local equivalents of both newly committed retry cases and the local retry allowlist. Result: **23 tests, 23 passed**.
- **Provenance:** local files are reconstructed/minimal equivalents, not exact GitHub checkout; this does not establish full repository integration, real provider consistency, or wallet ownership completeness.
- Remaining concern: `SavipChainProvider` promotes `independently_correlated_research` to `owner_coverage_complete=True` despite research collector returning `chain_pass_allowed=False`. Before production release, the evidence trust boundary needs an explicit, independently substantiated approval contract rather than treating correlation alone as certification. No merge or deploy.

## Research-to-production approval boundary
- Commit `848778b` hardens `SavipChainProvider.fetch_independent_owner_evidence`: `owner_coverage_complete=True` now additionally requires explicit `chain_pass_allowed=True` **and** `owner_coverage_complete=True` from the evidence collector, not merely `independently_correlated_research`.
- Current `collect_independently_confirmed_owner_evidence` intentionally returns both flags False, so this change **blocks** the former research-only promotion. This is safety correction, **not a working verification solution**.
- Commit `8f4c55c` updates mocked provider tests: research correlation denied, one approval flag insufficient, explicit flags + valid evidence positive control. **New test expectations not execution-verified.**
- Do not merge until real independent owner-coverage contract is established and full-source integration passes.

## Offline approval-boundary rerun
- Executed 25 isolated reconstructed local unittest cases after adapting local provider logic and tests to research approval-boundary commits `848778b` and `8f4c55c`: **25/25 passed**. An initial run failed two tests because local provider copy was stale; synchronized the local approval checks and reran successfully.
- No full GitHub checkout, live RPC snapshot certification, or end-to-end CHAIN pass was performed. Production remains unchanged.

## CHAIN worker infrastructure cooldown
- Commit `7e6a082` classifies `mint_accounts_slot_mismatch` and `cross_provider_slot_mismatch` alongside existing `snapshot_slot_mismatch` infrastructure statuses, so affected candidates receive the worker's 3600-second cooldown rather than 120 seconds. This avoids repeating costly checks during provider inconsistency.
- Source-level change is committed but no exact-source worker integration test has been executed. No production merge/deploy and no complete owner proof.

## Root-cause review: impossible-to-rely-on sequential slot equality
- Inspected exact `app/research/solana_owner_evidence_pipeline.py` on branch. `collect_owner_evidence` issues sequential `getAccountInfo`, `getProgramAccounts`, `getTokenSupply`, demanding `mint_slot == accounts_slot == supply_slot`; `collect_independently_confirmed_owner_evidence` then demands both providers return identical account slots. On live Solana this is a stringent temporal coincidence, not a reproducible snapshot contract. `minContextSlot` only sets a lower bound, not an exact slot pin.
- Current research collector explicitly denies `chain_pass_allowed` and `owner_coverage_complete`; provider now correctly refuses promotion. As written, **no positive CHAIN authorization path exists**. This is safer than a false pass but is not a functional wallet verifier.
- Recommended next engineering design: select a provider/API that explicitly supports a single coherent snapshot of mint supply plus full token-account owner map (or verifiable historical state at a chosen slot); validate completeness and provider trust, and test with actual full-source integration. Do not weaken concentration limits, invent slot pinning via `minContextSlot`, or reinterpret cursor page totals as completeness proof.
- No production rollout or live verification performed during this review.

## Solana RPC contract verification (official docs review)
- Official Solana `getProgramAccounts` documentation confirms `withContext` exposes the query's evaluated slot and `minContextSlot` only specifies a **minimum**, not an exact historical snapshot slot: https://solana.com/docs/rpc/http/getprogramaccounts . The current three sequential reads cannot be made atomic by supplying `minContextSlot`.
- Standard `getProgramAccounts` returns a single filtered result rather than a paginated stable historical snapshot; its size and public-RPC limits are operational constraints. Solana Cookbook notes no standard pagination and potentially truncated/failed large responses: https://solanacookbook.com/guides/get-program-accounts.html .
- Therefore: stop treating repeated slot equality retries as the primary solution. Evaluate an actual coherent indexed/historical snapshot contract, or a small-mint one-response owner-map strategy with separately demonstrated supply consistency; neither currently grants CHAIN authorization.
- No Helius API key, paid subscription, deployment, or altered risk threshold required for this documentation audit.
