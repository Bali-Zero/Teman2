# Claude Code harness — intervention backlog

One row per intervention, born from `scripts/cc_meta_research_loop.py` runs plus
on-disk verification. This file is the LIST: append, never rewrite history.
Status values: `OPEN` · `ARMED` (PR open) · `SHIPPED` (merged + proven live) ·
`DROPPED` (with the reason). A row may only move to SHIPPED with the observation
that proves it, not with the merge SHA alone.

Machine of record: M5. Verified: 2026-09-17.

| id | surface | intervention | risk | status | proof required |
|---|---|---|---|---|---|
| H1 | hooks | `guardrails-client.sh` Tier 3 must `exit 2`, not `exit 1` — today its "fail-closed" branch lets the tool run | none (1 line) | OPEN | with daemon + static evaluator both unreachable, a denied tool is actually blocked |
| H2 | settings | hook timeouts 3000/8000/10000 s (50/133/166 min) → second-scale budgets | none | OPEN | `settings.json` has no hook `timeout` > 600 |
| H3 | hooks | drop `cc-status` from PreToolUse/PostToolUse (keep lifecycle events) — 16 handlers fire per Bash call | low | OPEN | handler count per Bash call measurably below 16 |
| H4 | hooks | unregister `stop_verify.py` + `seam_verify.py` — they exit immediately, `*_FORCE` appears nowhere | none | OPEN | `grep -c` STOP_VERIFY_FORCE in settings = 0 and the registrations are gone |
| H5 | hooks | `context_hygiene.py` must sample BEFORE reading up to 400 KB of transcript | low | OPEN | the 400 KB read happens once per notice, not 20× |
| C1 | context | every programmatic `claude -p` (cron, seat, second-army, dispatch scripts) gets `--restricted` | low | OPEN | a headless PONG probe costs ≤20k input tokens and answers PONG |
| C1b | hooks | CAUSE OF C1, corrected 2026-09-17: `mailbox_inject.py` is registered on `PostToolUse` with an EMPTY matcher (= every tool) and on `Stop:*`, not on SessionStart as first written — it re-injects fleet mail as `additionalContext` after every single tool call | low | OPEN | one tool call adds no mail to context; mail still reaches a session that asks for it |
| C2 | permissions | `.claude/settings.local.json`: 907 allow rules → reviewed list; 429 wildcarded rules re-anchored; 31 `/Users/nuzantara/...` rules deleted | medium | OPEN | `claude -p` emits no wildcard warning; 0 dead-user paths |
| S1 | sandbox | `sandbox.enabled: true` with scoped filesystem/network, keeping unattended flow via `autoAllowBashIfSandboxed` | medium — can break cron | OPEN | a cron lane still runs unattended AND a write outside the worktree is refused by the OS |
| A1 | arsenal | kimi + all `tp1-*` + `qwen-cloud-code` are QUOTA_DEAD; agy TIMEOUT; ollama absent on M5 → the "4-LLM panel" doctrine is one seat | owner decision (spend) | OPEN | `arsenal_probe` shows ≥3 independent live seats, or the doctrine is rewritten to say so |
| O1 | observability | `/context` + `/usage` in the routine; `CLAUDE_CODE_ENABLE_TELEMETRY` + OTEL export per machine | low | OPEN | a per-machine token/cost number exists without asking a model |
| N1 | subagents | evaluate native `isolation: worktree` and `memory:` against `agent_start.py` + MOS — either adopt or write down why not | low | OPEN | a decision on disk, with the measurement behind it |
| N2 | hooks | unused events with an obvious use here: `WorktreeCreate`/`WorktreeRemove`, `ConfigChange`, `PostToolBatch` | low | OPEN | one of them wired, with the consumer that reads it |


## Round 2 — hook layer (2026-09-17)

Sources: `cc_meta_research_loop.py --lens-set hooks` (seat `claude --restricted`
proposing, `codex` grading) + the official hook contract (code.claude.com/docs/en/hooks,
hooks-guide, agent-sdk/hooks) + my own on-disk verification of every row below.
Measured base: **48 registered handlers**, all of `type: command`, **42 synchronous
on the critical path**, **33 with no explicit timeout** (⇒ 600 s default each).

| id | surface | intervention | risk | status | proof required |
|---|---|---|---|---|---|
| H6 | hooks | telemetry-only handlers (`cc-status` ×9, `bash_call_log.sh`, `context_hygiene.py`, `mailbox_inject.py`) must carry `async: true` — only `type: command` supports it, and it is the documented way off the critical path; today 6 of 48 use it | low | OPEN | the handlers that nobody waits for no longer sit on a blocking event |
| H7 | settings | 33 handlers inherit the 600 s default timeout; give each event a budget in seconds that matches what it does | low | OPEN | no handler can stall its event for minutes |
| H8 | hooks | `guardrails-client.sh` is fail-open TWICE: `exit 1` in its Tier-3 branch (H1) AND, per the contract, a `PreToolUse` hook of type `command` that hits its timeout does NOT block — the call proceeds. Either accept it is an advisor, or move the gate to an Agent-SDK callback (where a timeout does block) | medium | OPEN | a denied action is refused both when the evaluator is down and when the hook hangs |
| H9 | hooks | `mailbox_inject.py`: emit a POINTER (unread count + path) instead of mail bodies, and stop firing it on `PostToolUse`. `additionalContext` is capped at 10,000 chars and charged as input tokens on the next turn | low | OPEN | mail is readable on demand and a tool call costs no mail tokens |
| H10 | hooks | 11 registered hooks read the session transcript on `PreToolUse`/`PostToolUse`, each in its own process, on a file that reaches 2.9 MB here — one reader/dispatcher instead of eleven | medium — merging independent gates couples their failures | OPEN | one transcript read per tool call, and each gate still fails on its own guilt test |
| H11 | hooks | five hook types exist (`command`, `http`, `mcp_tool`, `prompt`, `agent`); we use `command` only. A guard that today guesses intent with `grep -E` is a candidate for `type: prompt` (Haiku by default) | medium | OPEN | one guard converted, with its guilt/innocence pair still passing |
| H12 | hooks | events never used that have an obvious consumer here: `WorktreeCreate`/`WorktreeRemove` (an entire broker, `agent_start.py`, does that job from outside), `ConfigChange` (scar #1 IS config drift), `PostToolUseFailure`, `PostToolBatch`, `PreModelSwitch` (model routing is currently a `PreToolUse:Agent` gate), `PostCompact`, `FileChanged` | low | OPEN | one wired, with the consumer that reads it |
| H13 | hooks · security | `prompt-injection-scan.sh`'s matcher names MCP tools of servers that are absent or disabled here (`mcp__brave-search__*`, `mcp__exa__*`, `mcp__filesystem__*`, `mcp__claude-in-chrome__*`, `mcp__notebooklm-mcp__*`) and does NOT name the web tools actually live in this session (`mcp__claude_ai_Exa__*`) — the injection scan does not run on the tools that fetch the web today | none to fix | OPEN | the scan fires on a live web-fetching tool call (observed, not assumed) |
| H14 | hooks | handler dedup covers the same handler repeated across settings FILES only; a plugin's or skill's copy stays separate. With 13 plugins enabled, 48 is a floor, not a total — census the hooks contributed by plugins | none (measurement) | OPEN | a count that includes plugin-contributed handlers |
| H15 | hooks | `Stop` fires 4 `python3` handlers + `cc-status` at every turn end, two of them no-ops (see H4) — and `Stop` is a blocking event | low | OPEN | turn end spawns what it needs and nothing else |
| M1 | tooling | `build_hook_inventory()` produced two false positives that the external grader correctly rejected: it read `env A=1 python3 x.py` as a hook named `env`, and reported `exit_codes=[2]` for a script that returns 0 via `return 0`. Teach it compound commands and Python `return`/`sys.exit` | none | OPEN | the two rows report the real script and the real exit paths |
| M2 | tooling | with 1-2 live seats the cross-grading collapses: codex emitted one reason and it was stamped onto 8 verdicts. The loop must either refuse to grade below 3 independent seats or label the verdict non-independent | none | OPEN | a run with 2 seats says so in the report instead of printing verdicts that look earned |

### Rejected this round (kept so nobody re-proposes them)

- *Three hooks run a bare `env` command* — REJECTED by codex: the inventory showed
  command heads, not full shell commands. Verified: they are `env VAR=… script`.
- *Two overlapping `PostToolUse` matchers run the same `bash` command twice* —
  REJECTED: they are different scripts (`track-file-change.sh`, `active-context-update.sh`),
  both already `async: true`.
- *A hook named `null` is registered on `Notification`* — REJECTED: artefact of my
  own parser reading `2>/dev/null` as the script. Cured (M1's sibling).
- *`m5_block_heavy_brew.py` can only exit 2, so it may block every Bash call* —
  REJECTED: it has six `return 0` paths, including an explicit fail-open on
  unparsable input. My scanner only looked for `exit(N)`.

### Contract facts worth keeping (they change how the rows above must be fixed)

- For most events **only `exit 2` blocks through the code alone**; `exit 1` without
  valid JSON on stdout is a non-blocking error and the action proceeds.
- **If stdout is valid JSON, the exit code is ignored** and only the JSON counts.
- `WorktreeCreate` blocks on ANY non-zero exit; `StopFailure` ignores both JSON and
  exit code.
- **All matching hooks run in parallel**, so a tool call spawns them concurrently.
- `timeout` is in **seconds**; default 600 for `command`, and on `PreToolUse` a
  timed-out `command` hook does NOT block.
- `suppressOutput` is accepted and does nothing (documented no-op). We do not use it.
- stdout of a plain hook reaches the model's context only on `UserPromptSubmit`,
  `UserPromptExpansion`, `SessionStart`, `PostModelSwitch`; elsewhere it goes to the
  debug log. `additionalContext` must sit inside `hookSpecificOutput` or it is
  silently ignored.
