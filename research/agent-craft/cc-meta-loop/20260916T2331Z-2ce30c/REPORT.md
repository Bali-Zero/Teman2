---
date: 2026-09-16
domain: operations
client_case: Claude Code harness self-audit (multi-seat research loop, run 20260916T2331Z-2ce30c)
sources: 4
adversarial_review: codex
adversarial_review_note: "4 proposals graded by {'codex': 4}; authored by {'claude': 4} — the grader never graded its own proposals (generator != grader). With only 2 live seats the review is RECIPROCAL, not independent, as the loop itself classifies it. Facts about this machine were re-verified on disk by the orchestrating Opus session before entering BACKLOG.md."
summary: Machine-written report of one research-loop run over this machine's Claude Code configuration — seats, proposals, verdicts.
---
> **Read with this in mind (gate finding, 2026-09-17, row L2 of BACKLOG.md):** the loop that wrote this file
> scrubbed each seat's raw answer BEFORE parsing it, and the scrubber's catch-all replaces any token of
> 24+ chars with `<REDACTED>` — proposal ids included. In this run 14 of 16 proposal ids collapsed to
> `<seat>:<REDACTED>`; proposals and verdicts are dict-keyed by id, so colliding entries overwrote each other and
> a verdict printed under a proposal below may belong to a different one. The header counts (`proposals:`,
> `graded:`) are surviving dict keys, not what the seats produced (4 verdict entries survive). The seat table
> reads `SKIPPED_PROBE` for seats that authored and graded in this very run: `--no-probe` was used, and the
> writer printed the probe status as reachability. Both defects are fixed in the loop's successor PR; this file
> is kept as the record of the run as it was written.


# Claude Code meta-configuration — multi-seat research loop

- run `20260916T2331Z-2ce30c` · machine `m5` · 2026-09-16T23:31:31+00:00
- rounds: 2 · proposals: 3 · graded: 3

## Seat reachability (empirical, this run)

| seat | status | used |
|---|---|---|
| claude | SKIPPED_PROBE | NO — evidence missing |
| codex | SKIPPED_PROBE | NO — evidence missing |

> 2 seat(s) unreachable: **codex, claude**. Their lens is a hole in this report, not a negative finding.

## OPEN — plausible, nothing settles it

_Next round's questions, or a human measurement._

### [hooks] guardrails-client.sh (PreToolUse:*, blocking) has a recorded timeout of 3000, child_workflow.py (PreToolUse:*/SubagentStop/SubagentStart) has recorded timeouts including 10000, and precompact-mnemos.py (PreCompact) has a recorded timeout of 8000 — values that look like milliseconds but Claude Code's hook 'timeout' field is specified in seconds, which would make these effective caps of 50, 166, and

- author `claude` · confidence low
- grader `codex`: **UNVERIFIABLE** — Frequent invocation and context-emission capability do not prove repeated mail injection, because unread filtering, cursor advancement and empty-output branches are unexamined.
- why: guardrails-client.sh runs on every single tool call and blocks tool execution until it returns; if its timeout is actually ~50 minutes instead of ~3 seconds, a hang in that script (network call, lock contention) stalls the entire session with no harness-level recovery until the mis-set timeout finally elapses.
- expected gain: reliability: prevents <REDACTED> session stalls from a single slow/hung blocking hook
- risk: if the timeout field is in fact milliseconds in this Claude Code version (contrary to my recollection), then these values (3s, 10s, 8s) are already correct and tightening them would cause premature timeouts on legitimately slower hooks
- verify (NOT executed by this loop): `jq '{PostToolUse: .hooks.PostToolUse, Stop: .hooks.Stop}' ~/.claude/settings.json; nl -ba ~/.claude/hooks/mailbox_inject.py`
- source: reasoning

### [hooks] cc-status is registered as a PreToolUse/PostToolUse/UserPromptSubmit/etc. hook command with matcher '*' on all 9 global events, meaning it forks a new process on nearly every harness event including every tool call, purely to update an iTerm2 status line.

- author `claude` · confidence medium
- grader `codex`: **UNVERIFIABLE** — The nine event registrations are confirmed, but counting them cannot establish latency or whether statusLine preserves cc-status's event-specific behavior.
- why: a statusline update is presentation state, not something that needs to intercept the PreToolUse/PostToolUse blocking-hook pipeline; Claude Code has a dedicated statusLine mechanism (separate from the hooks array, invoked on its own cadence) that does not sit in the tool-call critical path. Running it as a PreToolUse/PostToolUse hook adds one subprocess spawn per tool call for output the model never consumes (emits_context:false, emits_decision:false for cc-status in the supplied data).
- expected gain: latency: removes 1 subprocess fork+exec per tool call (of the ~16 handlers/call the orchestrator cites, this is likely the single largest fixed contributor since it's on every event)
- risk: if cc-status also does state bookkeeping only reachable via hook firing (not just rendering), moving it to statusLine-only could break whatever state it tracks across tool calls
- verify (NOT executed by this loop): `jq '{statusLine, hooks}' ~/.claude/settings.json; nl -ba ~/.config/iterm2/cc-status`
- source: reasoning

## REJECTED

_Wrong, already true, or banned here._

### [hooks] three separate hook registrations run the bare command 'env' with no further logic: PreToolUse on Bash|Edit|Write, PostToolUse on Bash|Edit|Write|WebFetch|WebSearch|Read, and SessionEnd on '*'.

- author `claude` · confidence medium
- grader `codex`: **REJECTED** — The inventory reports command heads rather than complete shell commands, so interpreting env as a bare environment dump instead of a possible execution wrapper is unjustified.
- why: a hook command of literally 'env' forks a process and dumps the full environment to stdout on nearly every tool call; unless a downstream consumer parses that output, it is pure per-call subprocess and log-write overhead with no decision or context value.
- expected gain: latency + cost, removes 2-3 of the ~14-16 PreToolUse/PostToolUse subprocess forks per Bash/Edit/Write/Read call
- risk: if some other process tails these env dumps for audit/debugging, removing them loses that trail
- verify (NOT executed by this loop): `jq '[.hooks | to_entries[] | .key as $event | .value[].hooks[]? | select((.command // "") | test("^env( |$)")) | {event:$event,bare_env:(.command == "env")}]' ~/.claude/settings.json ~/.claude/settings.local.json`
- source: reasoning

## Loop convergence

- round 1: 8 new proposals from 1 seats (claude), 0 supported
- round 2: 8 new proposals from 1 seats (claude), 0 supported

> No verification command in this report was executed by the loop. A model-authored shell string run by the tool that requested it is an injection channel; running them is a human's or an Opus session's act.

## Adversarial review

Refuter: `codex` (graded 4 proposals it did not author). Verdicts: {'UNVERIFIABLE': 3, 'REJECTED': 1}.

- round-1 · `claude:<REDACTED>` → **UNVERIFIABLE** — The nine registrations are supported, but counting them proves neither significant overhead nor that a timer can replace the event-specific behavior.
- round-1 · `claude:env-dump-hooks-remove` → **REJECTED** — The inventory reports command heads rather than complete shell commands, so interpreting env as a bare environment dump instead of a possible execution wrapper is unjustified.
- round-2 · `claude:<REDACTED>` → **UNVERIFIABLE** — Frequent invocation and context-emission capability do not prove repeated mail injection, because unread filtering, cursor advancement and empty-output branches are unexamined.
- round-2 · `claude:cc-status-not-a-hook` → **UNVERIFIABLE** — The nine event registrations are confirmed, but counting them cannot establish latency or whether statusLine preserves cc-status's event-specific behavior.

Surviving (accepted by the refuter): 0 of 4; the rest are kept above as rejected or unverifiable, not deleted. Limitation: two live seats make this reciprocal, not independent.
