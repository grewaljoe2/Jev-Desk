# Jev Desk — Next Chat

Continue my Jev Desk project from the latest saved project state in GitHub. First read `docs/PROJECT_HANDOFF.md` and inspect current `main` plus the live Render deployment before changing anything. Do not reset research, repeat rejected branches, or make me re-explain prior work.

Current verified production checkpoint: PR #126 / main commit `2791d58c971d6ce5236b64fa9bf42289bf68ada0` is LIVE on Render deployment `dep-db3bd58m7kps73dn6skg` (finished 2026-10-07T21:16:54.240874Z). Production is SHADOW ONLY and real execution is OFF.

The active Savip published-reference path is COLLECT -> FREE CUT -> TRADE CUT -> CHAIN/dossier -> typed Jev -> soft gates -> PICK -> PRICE/SIZE -> FILLS -> BOOK -> RISK -> exit/re-entry. PR #124 changed the downstream handoff to event-driven without loosening thresholds: one completed DEX cycle wakes CHAIN once, CHAIN pass wakes Jev immediately, and Jev soft-pass wakes PICK immediately. Dossier cap remains 3. The entry worker already blocks a second Savip position while one is held.

PR #123 fixed the orphaned dashboard JavaScript tail that caused startup failures. PR #126 restored the missing Savip shadow-trades DOM container, fixing the false “Savip shadow data unavailable” UI error and exposing BOOK trade details.

Do not loosen filters to manufacture a trade. A genuine CHAIN pass has been observed previously, while a later cycle correctly showed CHAIN checked 1 / passed 0 with Jev/PICK armed. Actual exact-X collection is not yet active. Do not claim a paid Jev call completed without production evidence.

Next engineering priority: persist the Savip RISK data-failure retry state across restarts and verify third-failure close behavior without fabricating a price. Then audit DexScreener 429 handling, Jev failed-claim retry semantics, PICK fingerprint/idempotency, shadow bank source, stale readiness reporting, re-entry uniqueness, held-position earliest-scan fidelity, 72h candidate starvation, and the observed FREE-vs-TRADE age discrepancy. Refactor the giant inline dashboard before further large UI work.

After correctness/reliability work, implement the planned mobile living-desk visualization from real backend state/events only. Preserve token identity, chain, contract and activity provenance; do not fake animations or copy Savip artwork.

Always re-read source after connector writes, verify the intended Render commit is actually LIVE, keep Jev Desk separate from MT5, and keep real execution OFF.
