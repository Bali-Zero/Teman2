---
date: 2026-05-12
domain: symbiosis
client_case: SYMBIOSIS gap-closure loop · Step 4 · Gap 2 Consiglio v1 quarantine decision matrix
sources: 5
status: draft
loop_step: 4
loop_branch: feat/symbiosis-loop-2026-05-12
mode: doc-only
verdict: KILL (recommendation, user confirms in PR review)
---

# Consiglio v1 — v2 OR kill decision matrix

**Generated**: 2026-05-12 03:25 WITA · Step 4 of SYMBIOSIS gap-closure loop · branch `feat/symbiosis-loop-2026-05-12`.

## Context

`SYMBIOSIS.md` Pilastro 4 (Confronto) promised: "Il Consiglio è una sessione periodica dove un LLM moderatore ha accesso a tutti i report e può fare le domande che ogni agente farebbe agli altri." PR #468 (commit `6c8f0284c`, merged 2026-05-06 03:23 UTC) quarantined the Council v1 implementation to `apps/mata-garuda/.disabled-2026-05-06/council/` with the rationale:

> The multi-LLM deliberation system (SYMBIOSIS Pillar 4, PR #68 from 2026-04-16) never produced a single deliberation: council.db was never created on either Pro or Mini, no log entries match council, the weekly LaunchAgent was meant for Air which was decommissioned 2026-05-05 before any cron landed, and shared/escalations.json (one of two intended Council inputs) stayed empty from creation through today.
>
> The 5 multi-LLM patterns the system uses in practice (wave-orchestrator, tri-LLM panel review, bipolar verifier with NB ground truth, ad-hoc cross-LLM brainstorm, MOS auto-save) all overlap with what the Council promised, and none of them touch this code.

## The 5 existing multi-LLM patterns (per PR #468 commit message)

1. **Wave-orchestrator**: parallel agents on independent tasks (e.g. 3 sessions Claude Opus on worktree isolati per SYMBIOSIS_TURNON_PLAN.md FASE 1)
2. **Tri-LLM panel review**: Claude + Gemini + DeepSeek on critical PRs (used in this very loop's Step 0 brainstorm)
3. **Bipolar verifier**: LLM main + 1 NB ground-truth specialistico (e.g. Claude implementa, NB-INTEL-Tax verifica facts)
4. **Ad-hoc cross-LLM brainstorm**: invocato quando serve decisione multi-prospettiva (e.g. SYMBIOSIS_TURNON_PLAN.md HALT decisions)
5. **MOS auto-save**: memory operating system records decisions across sessions (~/.claude/scripts/mem save ...)

## What Pilastro 4 (Confronto) actually promised

From `SYMBIOSIS.md` Pilastro 4:

> Il confronto è many-to-many. L'intelligenza non nasce dal consenso di un LLM che si dà ragione da solo, ma dallo scontro tra prospettive diverse. [...] La diversità deve essere architettonica.

Operational promises:

- **P4.1** Periodic deliberation (weekly cadence assumed for v1)
- **P4.2** Moderator LLM with access to all agent reports
- **P4.3** Multi-LLM architectural diversity (Claude, Gemini, DeepSeek, Llama)
- **P4.4** Output: new rules, cross-tasks via Redis, shared insights, escalation to Zero only when human needed
- **P4.5** Groupthink detection (if too-fast consensus, moderator hunts for the flaw)
- **P4.6** Devil's advocate gate

## Decision matrix

| Pilastro 4 promise                                           | Existing pattern that delivers                               | Verdict     | Notes                                                                                                                                   |
| ------------------------------------------------------------ | ------------------------------------------------------------ | ----------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| P4.1 — Periodic deliberation                                 | Pattern 1 (wave-orchestrator) on a cron + Pattern 4 (ad-hoc) | **COVERED** | Wave triggered by Antonello/cron events; ad-hoc when needed. Periodic without trigger = solution looking for problem.                   |
| P4.2 — Moderator with access to all reports                  | Pattern 1 (orchestrator agent in wave)                       | **COVERED** | This loop's design-architect (Step 0 of THIS document) is exactly a moderator pattern.                                                  |
| P4.3 — Architectural diversity (Claude/Gemini/DeepSeek/etc.) | Pattern 2 (tri-LLM panel)                                    | **COVERED** | Used 3× in this loop alone (briefing brainstorm, Step 1 DA, future steps DA).                                                           |
| P4.4 — New rules/cross-tasks/insights/escalation             | Pattern 5 (MOS) + research/symbiosis/ + Telegram escalation  | **COVERED** | Patterns 1-4 produce, Pattern 5 persists, research/ git-tracks, Telegram alerts when human needed.                                      |
| P4.5 — Groupthink detection                                  | Pattern 2 explicit role: DeepSeek as devils-advocate         | **COVERED** | DeepSeek's job description is exactly "destroy the consensus". Verified live in this loop Step 1 (DA verdict BLOCK on first iteration). |
| P4.6 — Devil's advocate gate                                 | Pattern 2 DeepSeek + explicit `devils-advocate` subagent     | **COVERED** | Already a documented subagent type in `~/.claude/agents/`.                                                                              |

**Verdict**: every Pilastro 4 promise is DELIVERED today by patterns 1-5. Column C (gap) is **empty**.

## Recommendation: KILL

Per the design spec's veto criterion: "BLOCK if v2 spec is proposed but column C is empty/contrived". Column C is empty → no v2 spec is justified.

**Recommended action**: keep the `.disabled-2026-05-06/council/` quarantine permanently, mark it as RESOLVED in `cicatrix-scars.md` (alongside the other quarantined channels like Twitter/Slack), and document this decision matrix as the canonical reference.

### Why not v2

Building Consiglio v2 would require:

- Re-implementing 10 files (orchestrator, agents, consensus, delivery, models, moderator, prompts, store, council_weekly) that have empirical proof of zero historical use
- Adding a new SQLite DB (`council.db`) with no current writers/readers
- Adding a new weekly LaunchAgent that competes with existing cron infrastructure
- Solving the "no escalation source" problem (shared/escalations.json was empty for the entire Consiglio v1 lifetime — what would v2's input be?)

The 5 existing patterns achieve the SAME goal with:

- Zero new code (already running daily)
- Zero new infrastructure (uses existing claude/gemini/codex CLIs)
- Zero new DB (uses MOS SQLite + research/ git-tracked files)
- Empirically successful (this very loop is a working multi-LLM deliberation in progress)

## Action: cicatrix-scars.md archival

The `.disabled-2026-05-06/council/` directory should be referenced as "RESOLVED via 5-pattern equivalence" in `.claude/rules/cicatrix-scars-archive.md`. Proposed entry (operator adds in follow-up PR — `.claude/rules/` is operator-controlled territory, NOT touched by this autonomous loop):

```
### ✅ RESOLVED: Consiglio v1 quarantine confirmed permanent (2026-05-12)

_Quarantined 2026-05-06 PR #468 · Permanent decision 2026-05-12 via SYMBIOSIS gap-closure loop Step 4_

PR #468 quarantined the multi-LLM deliberation system that never produced
a deliberation (council.db never created, weekly LaunchAgent for Air which
was decommissioned, escalations.json empty). The 2026-05-12 gap-closure
loop decision matrix confirms KILL: all 6 Pilastro 4 promises (periodic
deliberation, moderator, architectural diversity, output channels,
groupthink detection, devil's advocate gate) are already delivered by
5 existing patterns (wave-orchestrator, tri-LLM panel, bipolar verifier,
ad-hoc brainstorm, MOS auto-save).

Reference: research/symbiosis/2026-05-12-consiglio-v2-or-kill.md
```

## Refusals enforced this loop

1. NO un-quarantine of `apps/mata-garuda/.disabled-2026-05-06/council/`
2. NO new `council.db` schema or LaunchAgent
3. NO v2 spec drafting (column C empty)
4. NO direct edit of `.claude/rules/cicatrix-scars*.md` (operator-controlled)
5. NO edit of `SYMBIOSIS.md` Pilastro 4 table (operator-controlled)

## Sources

1. PR #468 commit message `6c8f0284c` (verified via `git log -1 6c8f0284c --format=%b`)
2. `apps/mata-garuda/.disabled-2026-05-06/council/` directory listing (10 files: \_\_init\_\_.py, agents, consensus, delivery, models, moderator, orchestrator, prompts, store, plus tests-council/ + council_weekly.py)
3. `apps/mata-garuda/.disabled-2026-05-06/council/orchestrator.py:1-45` (Consiglio v1 flow: validate→dispatch→filter→score→detect-groupthink→identify-dissents→synthesize→escalate→persist)
4. `SYMBIOSIS.md` Pilastro 4 (Confronto) text
5. `CLAUDE.md` "Multi-LLM deliberation pattern" enumeration (the 5 patterns)
