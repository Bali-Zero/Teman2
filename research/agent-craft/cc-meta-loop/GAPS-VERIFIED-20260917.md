---
date: 2026-09-17
domain: operations
client_case: Claude Code harness self-audit (multi-seat research loop)
sources: 2
adversarial_review: codex
adversarial_review_note: "SCOPE of the key: the PROPOSALS in these files were graded by codex, which authored none of them (generator is never grader). That grading ran with 2 live seats, so by the loop's own classification it is RECIPROCAL, not independent — stated here rather than implied. Every line that asserts a fact about this machine was additionally verified on disk by the orchestrating Opus session in the same turn it was written, and the four proposals codex rejected (two of them defects in my own scanner) are kept in the file rather than deleted."
summary: Ten verified gaps in this machine's Claude Code configuration, each with the command that produced it.
---

# Claude Code harness — verified gaps, M5, 2026-09-17

Produced by `scripts/cc_meta_research_loop.py` (2 runs, 6 seats named, 2 reachable)
plus an independent on-disk check of every claim below by the orchestrating Opus
session. Nothing here is a model's opinion: each line carries the command that
produced it. Order is by cost of leaving it as it is.

## 1. The guardrails hook is fail-OPEN in the exact case it calls fail-closed

`~/.claude/hooks/guardrails-client.sh` ends its "Tier 3 — total infrastructure
failure → fail-closed" branch with `exit 1` (line 93), while its real blocking
branches use `exit 2` (lines 58, 79). For a PreToolUse hook, exit 1 is a
non-blocking error: the tool RUNS. So when the guardrails daemon AND the static
evaluator are both unreachable — the only case that branch exists for — the
protection silently disappears, on a machine whose default permission mode is
`bypassPermissions`. Scar #3 (guard that does not judge) on top of scar #2
(exists ≠ armed).

    grep -n 'exit 1\|exit 2' ~/.claude/hooks/guardrails-client.sh

## 2. Three hook timeouts are 50, 133 and 166 MINUTES

`timeout` is in SECONDS. Live values: PreToolUse `guardrails-client.sh` 3000,
PreCompact 8000, SubagentStop 10000. A hung hook therefore parks the session for
up to 2h46m with no ceiling short of the operator noticing. The numbers read like
milliseconds that were never converted.

    python3 -c "import json,pathlib;d=json.loads((pathlib.Path.home()/'.claude/settings.json').read_text());print([(e,h.get('timeout')) for e,ms in d['hooks'].items() for m in ms for h in m.get('hooks',[]) if (h.get('timeout') or 0)>600])"

## 3. One Bash call fires 16 hook handlers

Global + project settings, PreToolUse + PostToolUse, matchers that match `Bash`.
Every one is a subprocess; several read the transcript. `context_hygiene.py`
parses up to 400 KB of transcript on every Read/Bash/Grep/Glob and only THEN
throttles its own message (`NUDGE_EVERY=20`) — the work happens 20 times per
notice, not once.

## 4. Two Stop hooks spawn Python to do nothing

`stop_verify.py:15` and `seam_verify.py:34` exit immediately unless
`STOP_VERIFY_FORCE=1` / `SEAM_VERIFY_FORCE=1`. Neither variable appears anywhere
in settings.json (`grep -c` → 0). Two interpreter starts per Stop, permanently,
for a no-op — and if ever enabled, `stop_verify` treats any dirty worktree as
unfinished work with no `stop_hook_active` guard.

## 5. Headless `claude -p` answers another session's mailbox, at 90k tokens a call

MEASURED, same prompt three ways, from a scratch directory outside the repo:

| invocation | input tokens | output | answer |
|---|---|---|---|
| `claude -p "Reply with exactly: PONG" --model claude-sonnet-5` | 90,627 | 1,255 | fleet mailbox, migration 317 |
| same, `--settings '{"hooks":{}}'` | 92,216 | 1,016 | fleet mailbox |
| same, `--model haiku` | 54,906 | 2,141 | fleet mailbox |
| same, `--model haiku --restricted` | **15,511** | **46** | **PONG** |

The global SessionStart/PostToolUse hooks inject the cross-machine mailbox into
EVERY headless invocation — cron, seat, second-army, any programmatic dispatch —
and the model answers the injected context instead of the prompt. `--settings`
does not suppress it; `--restricted` does. This is why `arsenal_probe` reports
`claude=UNKNOWN_ERR` on M5: the seat is alive, its answer is drowned.

## 6. 907 local allow rules, 429 of them wildcarded, 31 pointing at a dead user

`.claude/settings.local.json` (repo) holds 907 `allow` rules. The CLI itself
warns that 429 have "a wildcard before the rest of the command, so it also
matches any options inserted at that position and approves them without a
prompt" — they grant more than they read as granting. 31 name
`/Users/nuzantara/...`, a path that does not exist on M5 (scar #1, HOME-fork).

## 7. The arsenal is 1 seat out of 6

Probed this run: `codex=LIVE`, `nlm=LIVE`; `kimi=QUOTA_DEAD`,
`tp1-glm-5.2=QUOTA_DEAD`, `tp1-qwen3.8-max=QUOTA_DEAD` (token plan exhausted),
`agy=TIMEOUT`, `ollama=NOT_INSTALLED` on M5. Every doctrine in this repo that
says "4-LLM panel" or "council" currently resolves to one seat plus a grader that
does not exist. Generator ≠ grader cannot hold with one seat: both loop runs show
0 SUPPORTED not because the proposals are weak but because there was nobody
independent to sign them.

## 8. Never measured: /context, /usage, OTEL

`/context` and `/usage` (documented: per-model token/cost, prompt-cache hit rate,
per-skill and per-subagent breakdown) have no trace of routine use, and none of
`CLAUDE_CODE_ENABLE_TELEMETRY` / `OTEL_*` is set on any of the three machines. A
fleet with 176 daemons has no aggregate context-cost signal.

## 9. Native mechanisms reimplemented by hand

- subagent `isolation: worktree` exists natively; `scripts/agent_start.py` is a
  custom broker for the same job.
- subagent `memory:` (persistent, `.claude/agent-memory/<name>/`) exists; the MOS
  `mem save` layer covers part of it by hand, and `.claude/agent-memory/` is
  currently untracked in git status.
- hook events never used that this fleet has an obvious use for:
  `WorktreeCreate`/`WorktreeRemove`, `ConfigChange`, `PostToolBatch`.

## 10. bypassPermissions + sandbox disabled, on a real workstation

`permissions.defaultMode=bypassPermissions` with `sandbox.enabled=false` is the
combination the official docs single out as for containers/VMs only. Both loop
seats named it independently — the only claim in the run where an external seat
and the harness-native seat agreed.

## Adversarial review

Refuter: `codex` (read-only sandbox, on-disk access), grading proposals authored by
`claude --restricted`. It authored none of what it graded.

**Objections that survived and were acted on (4 of 23 proposals rejected):**
1. *"Three hooks run a bare `env` command"* — rejected: the inventory printed command
   HEADS, not full shell commands. Verified: they are `env VAR=… script`. My scanner
   was wrong, not the config; row M1.
2. *"`m5_block_heavy_brew.py` can only exit 2, so it may block every Bash call"* —
   rejected: it has six `return 0` paths including an explicit fail-open on
   unparsable input. My scanner only looked for `exit(N)`; row M1, now cured.
3. *"Two overlapping PostToolUse matchers run the same command twice"* — rejected:
   different scripts (`track-file-change.sh`, `active-context-update.sh`), both
   already `async: true`.
4. *"A hook named `null` is registered on Notification"* — rejected: artefact of my
   parser reading `2>/dev/null` as the script path.

**Objection I did not accept, with the reason:** codex graded 8 proposals with a
single repeated sentence about the sandbox, which does not address the claims it was
attached to. Those verdicts are recorded as UNVERIFIABLE rather than treated as
refutations — and the loop now states its own grading regime (row M2) so that a
2-seat round can never again read as an independent one.

**Standing limitation:** with 2 live seats this review is RECIPROCAL, not
independent. Every factual line about this machine was verified on disk by the
orchestrating session in the turn it was written; the proposals were not.
