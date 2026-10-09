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
