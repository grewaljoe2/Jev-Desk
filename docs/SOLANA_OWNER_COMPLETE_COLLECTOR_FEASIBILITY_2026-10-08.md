# Solana owner-complete collector: feasibility gate (research only)

Status: **NOT IMPLEMENTED / NOT DEPLOYABLE**. No RPC traffic, subscriptions, worker wiring or threshold changes authorized by this document.

## Exact claim to establish
For a mint at a single coherent ledger snapshot, every token account belonging to that mint must be enumerated, its **token-account authority/owner** resolved, and raw balances aggregated by owner. A token account is not a wallet. A mint's top 20 token accounts do not bound the largest owner's aggregate if one owner controls many accounts. The 5% rule remains frozen.

## Free RPC approach: conditional, not yet proven operational
1. Resolve the mint account and **actual token program** (classic SPL Token vs Token-2022). A mint may not be queried under an assumed program.
2. Obtain all mint-matching token accounts from the owning token program, with a correct mint filter, using a context-bearing response. **Do not filter by fixed dataSize=165** for Token-2022: account extensions alter lengths. No native cursor pagination exists in standard getProgramAccounts.
3. Parse each account's mint, owner authority, raw amount and account identity. For Token-2022, account extensions and withheld-fee balances require explicit treatment; never guess an extension layout. Do not confuse RPC account's *program owner* with the *token account's authority*.
4. Require a coherent context slot for enumeration and supply. A later getTokenSupply result cannot by itself establish same-slot supply. An RPC minContextSlot is a lower bound, **not** a snapshot pin. If same-state evidence cannot be established, result is unverified.
5. Deduplicate by token-account address and fail closed on duplicate/missing owner, inconsistent mint/program/slot, malformed amount, truncated/limited RPC response, timeout, 429, or uncertain coverage. Distinguish provider claim of completeness from a caller's boolean flag.
6. Confirm supply accounting, including frozen/escrow/LP and Token-2022-specific accounting; do not silently exclude any owner. An exact observed sum is necessary for this proposed proof but not sufficient on its own to establish coverage.
7. Only then pass raw owner balances to the offline verifier. Any concentration >5% can reject, but a <=5% pass **requires all evidence**.

## Feasibility / provider decision
- Public Solana RPC currently rate-limits even small requests in the live worker. A large unpaginated mint scan may be unsupported, expensive, or rejected. Do **not** run a production getProgramAccounts scan as a probe.
- Before integration, obtain documentation and a bounded test environment demonstrating: complete response, response size/time limits, Token-2022 support, coherent slot, retries/429 behavior, and acceptable request budget.
- Paginated indexed endpoints may help but need documented coverage guarantees and verified **existing free-tier** access. Do not buy or subscribe.
- If no collector satisfies the contract, leave Solana as **unverified/retry_pending**, not pass. Keep other networks progressing and measure separate Jev/CHAIN handoff issues.

## Acceptance fixtures for future collector (not covered by current 14 verifier tests)
- Missing page with apparently plausible totals; duplicate account across pages; overlapping or inconsistent snapshot slots.
- Token-2022 account with extension and withheld-fee behavior; wrong mint/program; authority vs program-owner confusion.
- Public RPC 429, partial/truncated response, timeout and account-limit errors.
- LP/escrow ambiguous classification: never silently exclude.
- Explicit evidence that a <=5% pass was computed from complete owner-aware distribution at a coherent state.

## Next step
Evaluate available free provider capabilities **without making paid or live scanning calls**; then build a mock collector adapter and fixtures for the above before connecting any provider to the worker.
