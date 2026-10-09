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
