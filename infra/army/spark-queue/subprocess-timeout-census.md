# subprocess-timeout census: subprocess calls without a timeout in scripts and backend, hang-ranked

Read-only analysis — no plan to edit/commit/push anything.

Search `scripts/` and `apps/backend-rag/backend` for `subprocess.run` /
`subprocess.Popen` / `check_output` / `asyncio.create_subprocess_*` calls
WITHOUT a `timeout=` (or without any await-with-timeout wrapper), plus shell
scripts invoking network-touching or LLM CLIs without `timeout(1)`/watchdog.

Why (W118, cicatrix-superscar.md family #2): a step with no timeout of its
own ate a CI budget twice and surfaced as `cancelled` — a state no
failure-sweep looks for; the repo froze 11 hours. Cron-side, a hung
subprocess holds its whole lane hostage silently (the tick after it never
fires).

For each hit:

- file:line | what it invokes | can the callee plausibly hang (network, LLM
  CLI, DB, user-interactive prompt, `git push` over network)?
- what dies downstream while it hangs (a launchd lane? a request handler? a
  CI step?)
- HANG-RISK: HIGH (network/LLM callee inside a cron lane or request path),
  MEDIUM (local tool, bounded input), LOW (pure-CPU local, sub-second)

Output a markdown table sorted HIGH first. N of M, never a silent cap.
