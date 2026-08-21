# hardcoded model-id census: every literal LLM model id outside the SSOT files

Read-only analysis — no plan to edit/commit/push anything.

Find every literal LLM model identifier in the tree — patterns like
`claude-*`, `gpt-*`, `gemini-*`, `qwen*`, `glm-*`, `deepseek-*`, `kimi-*`,
`haiku`, `sonnet`, `opus` used as a model argument/pin — EXCLUDING the SSOT
and doctrine files themselves (`MODEL_ROSTER.md`, `FLEET_TOPOLOGY.json`,
`MODEL_TOPOLOGY.json`, `CLAUDE.md`, `AGENTS.md`, `.claude/skills/`,
`research/`, `docs/`).

Why: the workhorse-first routing doctrine (Zero 2026-08-15, intensified
2026-08-19) migrates implementer/batch work to TP1/Gemini doors, and cure G1
of the token-consumption plan wants a pinned prod model manifest — neither
can land safely without knowing every place a model id is hardcoded today.

For each hit report: file:line | the literal id | what invokes that code path
(cron/plist/CI/prod request/dev-only, judged from the file's location and its
callers where greppable) | whether the id is current per MODEL_ROSTER.md or a
stale/legacy pin.

Output as a markdown table sorted by: prod paths first, then cron, then
dev/test. State the total count explicitly (N of M — never a silently capped
list).
