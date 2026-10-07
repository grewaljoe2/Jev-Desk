# Later Project Migration — MT5
Do not mix MT5 research into Jev Desk.

When the user returns to the MT5 project, create a separate durable source-of-truth structure for it using the existing MT5 Library handoffs/research and exact current source files. Preserve at minimum: authoritative EA source/build, last verified benchmark, broker/tester and real-tick configuration, frozen defaults, market architecture, validated modules, rejected branches and reasons, optimization/diagnostic results, market-specific findings, QA/diff rules, unresolved research and exact next steps.

Critical process rule: before any new EA handoff/build, compare frozen/control-critical defaults and active execution paths against the exact last verified benchmark source. Never reconstruct MT5 state from Jev Desk documentation or mix branches between projects.
