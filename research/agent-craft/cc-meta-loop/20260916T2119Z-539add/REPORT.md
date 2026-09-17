---
date: 2026-09-16
domain: operations
client_case: Claude Code harness self-audit (multi-seat research loop, run 20260916T2119Z-539add)
sources: 2
adversarial_review: codex
adversarial_review_note: "2 proposals graded by {'codex': 2}; authored by {'claude': 2} — the grader never graded its own proposals (generator != grader). With only 2 live seats the review is RECIPROCAL, not independent, as the loop itself classifies it. Facts about this machine were re-verified on disk by the orchestrating Opus session before entering BACKLOG.md."
summary: Machine-written report of one research-loop run over this machine's Claude Code configuration — seats, proposals, verdicts.
---

# Claude Code meta-configuration — multi-seat research loop

- run `20260916T2119Z-539add` · machine `m5` · 2026-09-16T21:19:47+00:00
- rounds: 1 · proposals: 3 · graded: 2

## Seat reachability (empirical, this run)

| seat | status | used |
|---|---|---|
| claude | SKIPPED_PROBE | NO — evidence missing |
| codex | SKIPPED_PROBE | NO — evidence missing |

> 2 seat(s) unreachable: **codex, claude**. Their lens is a hole in this report, not a negative finding.

## OPEN — plausible, nothing settles it

_Next round's questions, or a human measurement._

### [hooks] Three separate PreCompact hooks (bash, <REDACTED>, python3) plus a manual CONTEXT_WINDOW_TOKENS env override sit alongside the harness's native auto-compaction, suggesting compaction is being manually re-implemented/backed-up rather than tuned through the native summarization path.

- author `claude` · confidence low
- grader `codex`: **UNVERIFIABLE** — The native sandbox is disabled, but deny-list-only protection and unrestricted host access are unproven given the additional guards, and the Python pipeline incorrectly parses JSON line by line.
- why: PreCompact hooks fire immediately before the harness's own summarization pass; stacking three of them (one purely for transcript backup) to run at every compaction event, on top of a hardcoded token-window override, indicates the native auto-compaction's summary is not trusted as the sole record and is being defended against with manual scaffolding.
- expected gain: reliability: clarifies whether native compaction summaries are actually being relied on for continuity across the long 100k-400k token sessions this fleet runs, or whether the backup script is the rea
- risk: if the backup script is the only durable record used to recover context after compaction (i.e. native summaries are treated as lossy), removing or reordering these hooks could lose session continuity on the next compaction
- verify (NOT executed by this loop): `grep -n 'PreCompact' -A6 ~/.claude/settings.json .claude/settings*.json 2>/dev/null; ls -la $(grep -rn '<REDACTED>' ~/.claude 2>/dev/null | head -1 | cut -d: -f1 | xargs dirname 2>/dev/null) 2>/dev/null`
- source: reasoning

## REJECTED

_Wrong, already true, or banned here._

### [model-routing] <REDACTED> is set as an env var, but the current Agent tool schema states team_name is deprecated and ignored because 'the session has a single implicit team', so this flag now toggles a no-op.

- author `claude` · confidence medium
- grader `codex`: **REJECTED** — Deprecating an explicit team_name argument does not imply that the flag enabling agent teams is obsolete, and a prompted model self-report cannot establish that implication.
- why: An env flag that gates a code path the runtime has since collapsed does nothing but occupy an env slot and mislead anyone reading the config into thinking multi-team agent orchestration is active.
- expected gain: capability clarity: removes a dead knob, no runtime effect either way
- risk: if a specific claude_code build on one of the three machines still honors team_name, removing the flag could silently disable working multi-team behavior on that machine only
- verify (NOT executed by this loop): `claude --version; echo | claude -p 'call Agent with team_name=test and report if it errors or is ignored' 2>&1 | head -20`
- source: reasoning

## UNGRADED

_No grader was reachable for these._

### [hooks] Delete the standalone context_hygiene PostToolUse registration and reuse the existing context guard's usage calculation for advisory notices.

- author `codex` · confidence high
- why: context_hygiene reads and parses up to 400000 transcript bytes on every Read/Bash/Grep/Glob event; its 20-call throttle limits notices only after that work. The existing PreToolUse context guard already imports the same usage reader, so eligible calls repeat the scan and maintain an additional counter.
- expected gain: cost + latency: remove up to 900 Python launches and 360 MB of repeated transcript reading/parsing per 900 eligible calls; cached filesystem reads mean this is not necessarily physical disk traffic
- risk: Removing the module itself would break the guard's import; remove only the registration and retain or relocate the useful oversized-Read warning.
- verify (NOT executed by this loop): `rg -n '400_000|NUDGE_EVERY|last_context_tokens|_estimate_tokens|context_hygiene.py|open\(sf' "$HOME/.tokenaudit/hooks/context_hygiene.py" "$HOME/.claude/hooks/context_window_guard.py"`
- source: reasoning

## Loop convergence

- round 1: 15 new proposals from 2 seats (codex, claude), 0 supported

> No verification command in this report was executed by the loop. A model-authored shell string run by the tool that requested it is an injection channel; running them is a human's or an Opus session's act.

## Adversarial review

Refuter: `codex` (graded 2 proposals it did not author). Verdicts: {'UNVERIFIABLE': 1, 'REJECTED': 1}.

- round-1 · `claude:<REDACTED>` → **UNVERIFIABLE** — The native sandbox is disabled, but deny-list-only protection and unrestricted host access are unproven given the additional guards, and the Python pipeline incorrectly parses JSON line by line.
- round-1 · `claude:stale-agent-teams-flag` → **REJECTED** — Deprecating an explicit team_name argument does not imply that the flag enabling agent teams is obsolete, and a prompted model self-report cannot establish that implication.

Surviving (accepted by the refuter): 0 of 2; the rest are kept above as rejected or unverifiable, not deleted. Limitation: two live seats make this reciprocal, not independent.
