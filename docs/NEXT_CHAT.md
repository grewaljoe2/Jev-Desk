# Jev Desk — Next Chat

Continue my Jev Desk project from the latest saved project state in GitHub. First read `docs/PROJECT_HANDOFF.md` and inspect current `main` plus the live Render deployment before changing anything. Do not reset research, repeat rejected branches, or make me re-explain prior work.

Current production checkpoint: fresh-first scheduling from PR #70 is live via Render deployment `dep-db33kjflk1mc739aq29g` on main commit `13f035f6f1958a6171315c1e5777fc54f76b3864`. Fresh 1m/3m/5m/10m Fast and 15m entry evidence outranks background historical outcomes. Historical outcomes are newest-first; stale point-in-time jobs are marked missed rather than fetched late. Real trading is OFF.

First verify production after this deployment: Fast and 15m lateness, 429s, discovery continuity, active-position monitoring, and historical backlog/missed behavior. Do not change entry filters just to create trades. If provider contention remains, continue the centralized shared REST observation/batching architecture already documented in the handoff instead of another local worker sleep/priority patch. Keep Jev Desk separate from the MT5 project.
