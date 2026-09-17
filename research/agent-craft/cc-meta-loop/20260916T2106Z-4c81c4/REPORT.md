---
date: 2026-09-16
domain: operations
client_case: Claude Code harness self-audit (multi-seat research loop, run 20260916T2106Z-4c81c4)
sources: 1
adversarial_review: exempt-no-grader-was-live-ungraded-census
adversarial_review_note: "No verdict was produced in this run: the grader seats were unreachable, so every proposal is recorded UNGRADED and the run is a dry census, not a reviewed deliverable. Kept for the record of which seats were live at 21:06Z; the reviewed runs are 2119Z and 2331Z."
summary: Machine-written report of one research-loop run over this machine's Claude Code configuration — seats, proposals, verdicts.
---

# Claude Code meta-configuration — multi-seat research loop

- run `20260916T2106Z-4c81c4` · machine `m5` · 2026-09-16T21:06:36+00:00
- rounds: 2 · proposals: 2 · graded: 0

## Seat reachability (empirical, this run)

| seat | status | used |
|---|---|---|
| agy | TIMEOUT | NO — evidence missing |
| claude | UNKNOWN_ERR | NO — evidence missing |
| codex | LIVE | yes |
| kimi | QUOTA_DEAD | NO — evidence missing |
| tp1-glm-5.2 | QUOTA_DEAD | NO — evidence missing |
| tp1-qwen3.8-max | QUOTA_DEAD | NO — evidence missing |

> 5 seat(s) unreachable: **agy, kimi, claude, tp1-glm-5.2, tp1-qwen3.8-max**. Their lens is a hole in this report, not a negative finding.

## UNGRADED

_No grader was reachable for these._

### [hooks] Delete the global stop_verify.py and seam_verify.py registrations and invoke these checks explicitly at an appropriate delivery checkpoint.

- author `codex` · confidence high
- why: Both installed scripts exit immediately unless their respective FORCE variable equals 1, and neither variable appears in the inspected global settings environment. When enabled, stop_verify reads the entire transcript before slicing it and lacks a stop_hook_active guard, while seam_verify inspects uncommitted changes rather than the delivered branch diff.
- expected gain: latency/reliability: remove two Python launches per Stop event, or 600 launches if 300 Stop events occur, and eliminate an optional dirty-worktree stop loop.
- risk: Launchers may intentionally export the FORCE variables; preserve those workflows as explicit checks before removing registrations.
- verify (NOT executed by this loop): `rg -n 'STOP_VERIFY_FORCE|SEAM_VERIFY_FORCE|read_text|stop_hook_active|git.*diff|git.*status|sys.exit\(2\)' "$HOME/.claude/hooks/stop_verify.py" "$HOME/.claude/hooks/seam_verify.py"`
- source: reasoning

### [hooks] Delete raw tool-input persistence from <REDACTED>, remove codex-spalla-trigger.sh from PostToolUse, and remove bash_call_log.sh's raw-command fallback.

- author `codex` · confidence high
- why: The installed MOS hook stores the complete tool_input even when its sensitivity flag is set; gzip changes representation, not confidentiality. The Bash logger falls back to the original command when redaction produces nothing, while the 735-line spalla script adds another per-call parsing and logging path for an advisory suggestion.
- expected gain: reliability/cost: remove two hook invocations per Bash/Edit/Write call, corresponding SQLite/file writes, and multiple paths that can persist sensitive payloads.
- risk: Historical command replay and automatic review suggestions disappear; retain only allowlisted metadata such as event type, duration, outcome and opaque identifiers.
- verify (NOT executed by this loop): `rg -n 'osint_sensitive|tool_input|gzip.compress|INSERT INTO|LOGGED_CMD|TARGET_JSON|NO auto-spawn' "$HOME/.claude/hooks/<REDACTED>" "$HOME/.claude/hooks/bash_call_log.sh" .claude/hooks/codex-spalla-trigger.sh`
- source: reasoning

## Loop convergence

- round 1: 8 new proposals from 1 seats (codex), 0 supported
- round 2: 0 new proposals from 0 seats (none), 0 supported

> No verification command in this report was executed by the loop. A model-authored shell string run by the tool that requested it is an injection channel; running them is a human's or an Opus session's act.

## Adversarial review

None: no grader seat was reachable in this run (codex and claude both failed their probe), so nothing was refuted. Every proposal above is UNGRADED. This file is a census of what the loop could see at 21:06Z, kept for the record; the graded runs are 2119Z and 2331Z.
