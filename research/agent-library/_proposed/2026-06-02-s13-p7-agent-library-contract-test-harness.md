# S13-P7 — agent-library-contract-test-harness

> **Status**: PROPOSED (S13 evolution cycle, 2026-06-02). Draft only — Antonello approves graduation.
> **Kind**: new-capability · **Priority**: P1
> **Adversarial verdict**: ✅ KEEP — adversary-demanded, ships as the meta-fix

## Problem

MISSED GAP (surfaced independently by BOTH adversaries): there is no executable enforcement for any agent-library invariant. Skills are loaded as GUIDANCE, not enforced. Nothing verifies: frontmatter `skills:` actually load, WR3 NB-exclusivity (Contract 2) holds, reviewer!=author, 01-inventory count matches reality (it drifted 16->34 undetected), provider health before cascade, required output artifacts exist.

## Proposal (as originally drafted)

A contract-test/audit harness (pytest or scripts/) run in CI + pre-commit that asserts the library's invariants AS CODE. This is the meta-fix the adversaries demand: 'duplication of words is not duplication of behavior; without executable checks, a loaded skill changes nothing.' Tests: (1) every agent frontmatter parses + declared skills exist; (2) grep WR3 non-brief-interpreter agents for NB MCP calls = 0; (3) inventory count == ls ~/.claude/agents/\*.md; (4) review-gate agents are never their own author; (5) provider health-ping smoke.

## Agents served

- ALL (library-wide invariant enforcement)

## Evidence

DeepSeek missed_gap + Codex missed_gap (independent convergence); 01-inventory drift 16->34 undetected for 17 days; reflexion/voyager/evoskill all silently non-functional

## Cross-vendor adversarial review

- adversary-demanded (both red-teamers) → `KEEP-by-construction`

## Disposition (post-adversarial)

**KEEP (adversary-demanded) — PRIMARY.** Both red-teamers independently surfaced this as the missed gap and the real fix. Ship an executable contract-test/audit harness (pytest + pre-commit/CI) that asserts library invariants AS CODE: frontmatter+skills load, WR3 NB-exclusivity, reviewer≠author, inventory count == disk, provider health-ping, required output artifacts. This is where S13-P3 and S13-P5 land.
