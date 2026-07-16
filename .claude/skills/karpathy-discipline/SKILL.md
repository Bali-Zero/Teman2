---
name: karpathy-discipline
description: Use BEFORE any feature implementation, refactor, bug fix, or non-trivial code change. Applies 4 Karpathy principles to reduce common LLM coding mistakes (silent assumptions, hypertrophy, collateral changes, vague success criteria).
allowed-tools: Read, Edit, Write, Bash(git diff:*), Bash(git status:*), Bash(grep:*), Bash(rg:*)
---

> **CANON**: repo `.claude/` (vendored 2026-07-17, PR process-toolkit SSOT) — shadows the `~/.claude/` HOME copy. Edit HERE, never in `$HOME`. Pro/Mini shadow it on `git pull`.

# Karpathy Discipline

Source: `forrestchang/andrej-karpathy-skills` (109K+ ⭐). Verbatim from canonical CLAUDE.md.

**Tradeoff dichiarato**: _"These guidelines bias toward caution over speed. For trivial tasks, use judgment."_

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

**The test**: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]

```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if**: fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## Nuzantara-specific applications

(Per CLAUDE.md project context)

- **Think Before Coding** → si combina con regola 2026-05-13 "4-LLM panel review BEFORE user approval" per spec ad alto stakes
- **Simplicity First** → applicato in fix MEMORY.md 60.6KB→13.8KB (2026-05-19)
- **Surgical Changes** → riflette cicatrix-scars rule "atomic commits, no `--no-verify`, no `--amend` on pushed"
- **Goal-Driven Execution** → richiede TaskCreate/TaskUpdate + acceptance criteria in spec
